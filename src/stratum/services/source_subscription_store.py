from stratum.db import get_conn


class SourceSubscriptionStore:
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id

    def get_processed_ids(self) -> set[str]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT external_id FROM source_processed_items WHERE subscription_id = ?",
                (self.subscription_id,),
            ).fetchall()
        return {r[0] for r in rows}

    def mark_processed(self, external_ids: str | list[str]) -> None:
        ids = [external_ids] if isinstance(external_ids, str) else external_ids
        with get_conn() as conn:
            for eid in ids:
                conn.execute(
                    "INSERT INTO source_processed_items (subscription_id, external_id) "
                    "VALUES (?, ?) ON CONFLICT DO NOTHING",
                    (self.subscription_id, eid),
                )
