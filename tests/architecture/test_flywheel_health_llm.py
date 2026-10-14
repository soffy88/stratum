"""AII flywheel_health: local LLM service probes (freellmapi :3001, veya-llm-gateway :8791)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "aii" / "scripts" / "flywheel_health.py"
    spec = importlib.util.spec_from_file_location("flywheel_health_llm", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flywheel_health_llm"] = mod
    spec.loader.exec_module(mod)
    return mod


fh = _load()


def test_assess_llm_service():
    assert fh.assess_llm_service(False, False, None, 0) == "degraded"  # jammed /health
    assert fh.assess_llm_service(True, True, 0.0, 500) == "ok"
    assert fh.assess_llm_service(True, False, 0.05, 100) == "degraded"  # router collapsed
    assert fh.assess_llm_service(True, False, 0.5, 100) == "slow"  # slow upstream, router fine
    assert fh.assess_llm_service(True, False, 0.0, 3) == "slow"  # too few requests to judge


def test_restart_cap(monkeypatch):
    calls = []
    monkeypatch.setattr(fh, "sh", lambda cmd, timeout=30: calls.append(cmd) or (0, ""))
    st: dict = {}
    for _ in range(3):
        fh.restart_unit("veya-llm-gateway", st, False, 2, 6)
    assert len(calls) == 2
    ok, msg = fh.restart_unit("veya-llm-gateway", st, False, 2, 6)
    assert not ok and "suppressed" in msg


def test_gateway_success_parses_access_log(monkeypatch):
    log = "\n".join(
        [
            'INFO:     127.0.0.1:1 - "POST /v1/chat/completions HTTP/1.1" 200 OK',
            'INFO:     127.0.0.1:2 - "POST /v1/chat/completions HTTP/1.1" 503 Service Unavailable',
            'INFO:     127.0.0.1:3 - "GET /health HTTP/1.1" 200 OK',
            'INFO:     127.0.0.1:4 - "POST /v1/chat/completions HTTP/1.1" 504 Gateway Timeout',
            'INFO:     127.0.0.1:5 - "POST /v1/chat/completions HTTP/1.1" 200 OK',
        ]
    )
    monkeypatch.setattr(fh, "sh", lambda cmd, timeout=30: (0, log))
    rate, n = fh.gateway_success_1h("veya-llm-gateway")
    assert n == 4 and rate == 0.5


def test_gateway_not_restarted_when_freellmapi_is_the_problem(monkeypatch):
    restarted = []
    monkeypatch.setattr(fh, "_freellmapi_key", lambda: "")
    monkeypatch.setattr(fh, "http_health", lambda base: (True, "HTTP 200"))
    monkeypatch.setattr(
        fh,
        "probe_completion",
        lambda base, model, key="": {"ok": False, "seconds": 60.0, "routed": None, "detail": "t/o"},
    )
    monkeypatch.setattr(fh, "freellmapi_success_1h", lambda: (0.01, 200))
    monkeypatch.setattr(fh, "gateway_success_1h", lambda unit: (0.0, 50))
    monkeypatch.setattr(
        fh,
        "restart_unit",
        lambda unit, st, dry, max_n=None, window_h=None: restarted.append(unit) or (True, "ok"),
    )
    alerts = []

    def alert(name, kind, detail, action=None):
        a = {"flywheel": name, "anomaly": kind, "detail": detail, "action": action}
        alerts.append(a)
        return a

    out = fh.check_llm_services({}, True, False, alert)
    assert out["freellmapi"]["state"] == "degraded"
    assert out["veya-llm-gateway"]["state"] == "slow"
    assert restarted == ["freellmapi"]
