import pytest

from stratum.services.credit_meter import CreditIdempotencyConflict, consume_credits


class _Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _IdempotentConnection:
    def __init__(self, used=0):
        self.event_exists = False
        self.event_status = "pending"
        self.used = used
        self.aggregate_writes = 0
        self._inserted_period: str | None = None

    def execute(self, sql, params):
        if sql.startswith("INSERT INTO stratum.usage_credit_events"):
            if self.event_exists:
                return _Cursor(None)
            self.event_exists = True
            # params[2] is the period (idempotency_key, user_id, period, capability, units, credits, status)
            self._inserted_period = params[2] if len(params) > 2 else "2026-08"
            return _Cursor(("pending", params[5], params[3], params[4], self._inserted_period))
        if sql.startswith(
            "SELECT status, credits, capability, units, period FROM stratum.usage_credit_events"
        ):
            # Return the period that was actually inserted, or the current period if none was
            from datetime import datetime, timezone

            period = self._inserted_period or datetime.now(timezone.utc).strftime("%Y-%m")
            return _Cursor((self.event_status, 10, "deep_research", 1, period))
        if sql.startswith("SELECT credits_used"):
            return _Cursor((self.used,))
        if sql.startswith("INSERT INTO stratum.usage_credits"):
            self.aggregate_writes += 1
            self.used += 10
            return _Cursor((self.used,))
        if sql.startswith("UPDATE stratum.usage_credit_events"):
            self.event_status = params[0]
            return _Cursor(None)
        raise AssertionError(f"unexpected SQL: {sql}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_consume_credits_is_retry_safe_with_idempotency_key(monkeypatch):
    connection = _IdempotentConnection()
    monkeypatch.setattr("stratum.db.get_conn", lambda: connection)

    first = consume_credits("user-1", "free", "deep_research", idempotency_key="op-1")
    replay = consume_credits("user-1", "free", "deep_research", idempotency_key="op-1")

    assert first.used == 10
    assert first.outcome == "charged"
    assert replay.used == 10
    assert replay.requested == 10
    assert replay.outcome == "replayed"
    assert connection.aggregate_writes == 1


def test_consume_credits_rejects_blank_idempotency_key():
    with pytest.raises(ValueError, match="idempotency_key"):
        consume_credits("user-1", "free", "deep_research", idempotency_key=" ")


def test_denied_idempotent_charge_transitions_event_without_delete(monkeypatch):
    connection = _IdempotentConnection(used=25)
    monkeypatch.setattr("stratum.db.get_conn", lambda: connection)

    decision = consume_credits("user-1", "free", "deep_research", idempotency_key="op-denied")

    assert decision.allowed is False
    assert decision.outcome == "denied"
    assert connection.event_status == "denied"
    assert connection.aggregate_writes == 0


def test_pending_idempotent_charge_is_reported_as_in_flight(monkeypatch):
    connection = _IdempotentConnection()
    connection.event_exists = True
    connection.event_status = "pending"
    monkeypatch.setattr("stratum.db.get_conn", lambda: connection)

    decision = consume_credits("user-1", "free", "deep_research", idempotency_key="op-pending")

    assert decision.allowed is False
    assert decision.outcome == "in_flight"
    assert connection.aggregate_writes == 0


def test_reusing_idempotency_key_for_different_operation_is_rejected(monkeypatch):
    connection = _IdempotentConnection()
    connection.event_exists = True
    monkeypatch.setattr("stratum.db.get_conn", lambda: connection)

    with pytest.raises(CreditIdempotencyConflict, match="different credit operation"):
        consume_credits("user-1", "free", "image_generation", idempotency_key="op-1")


def test_usage_snapshot_reads_schema_qualified_ledger(monkeypatch):
    seen: dict[str, object] = {}

    def fake_query(sql, params):
        seen["sql"] = sql
        seen["params"] = params
        return [{"credits_used": 7}]

    monkeypatch.setattr("stratum.db.query", fake_query)
    from stratum.services.credit_meter import usage_snapshot

    snapshot = usage_snapshot("user-1", "free", now=None)

    assert snapshot.used == 7
    assert snapshot.remaining == 18
    assert "stratum.usage_credits" in str(seen["sql"])
