"""Unit tests for aii/aii/aii/embedding_client.py (EmbeddingGemma2 / BGE switch).

The module is stdlib-only, so it is loaded straight from its file: the root
test environment does not need the AII package installed.  A local
http.server stub plays the EG2 OpenAI-compatible gateway.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "aii" / "aii" / "aii" / "embedding_client.py"


def _load():
    spec = importlib.util.spec_from_file_location("eg2_embedding_client_under_test", _PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _Stub:
    def __init__(self):
        self.requests: list[dict] = []
        self.fail_first = 0  # number of 503 responses before success
        self.status = 200  # forced status (e.g. 400)
        self.dim = 768
        self.health_hits = 0

    def handler(self):
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def do_GET(self):
                if self.path == "/health":
                    stub.health_hits += 1
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append(body)
                if stub.fail_first > 0:
                    stub.fail_first -= 1
                    self.send_response(503)
                    self.end_headers()
                    return
                if stub.status != 200:
                    self.send_response(stub.status)
                    self.end_headers()
                    return
                data = [
                    {"index": i, "embedding": [0.01 * (i + 1)] * stub.dim}
                    for i in range(len(body["input"]))
                ]
                out = json.dumps({"data": list(reversed(data))}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out)

        return H


@pytest.fixture()
def eg2(monkeypatch):
    stub = _Stub()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), stub.handler())
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    # a dead proxy: the client must bypass it for the gateway
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("AII_EMBED_BACKEND", "eg2")
    monkeypatch.delenv("AII_EMBED_DIM", raising=False)
    mod = _load()
    monkeypatch.setattr(mod, "EG2_BASE_URL", f"http://127.0.0.1:{srv.server_address[1]}/v1")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    yield mod, stub
    srv.shutdown()


def test_query_and_document_models_and_dimensions(eg2):
    mod, stub = eg2
    q = mod.embed_queries(["什么是边际效用"])
    d = mod.embed_documents(["标题\n正文"])
    assert len(q[0]) == 768 and len(d[0]) == 768
    assert stub.requests[0]["model"] == mod.EG2_QUERY_MODEL == "embeddinggemma-2-query"
    assert stub.requests[1]["model"] == mod.EG2_DOC_MODEL == "embeddinggemma-2-document"
    assert all(r["dimensions"] == 768 for r in stub.requests)


def test_batches_at_most_four_and_keeps_order(eg2):
    mod, stub = eg2
    vecs = mod.embed_documents([f"t{i}" for i in range(9)])
    assert [len(r["input"]) for r in stub.requests] == [4, 4, 1]
    # stub returns data reversed; client must re-sort by index
    assert vecs[0][0] == pytest.approx(0.01) and vecs[1][0] == pytest.approx(0.02)
    assert vecs[4][0] == pytest.approx(0.01)


def test_5xx_is_retried_then_succeeds(eg2):
    mod, stub = eg2
    stub.fail_first = 2
    assert len(mod.embed_queries(["x"])[0]) == 768
    assert len(stub.requests) == 3


def test_persistent_failure_raises_unavailable(eg2, monkeypatch):
    mod, stub = eg2
    stub.fail_first = 10**6
    times = iter(range(0, 10**6, 10))
    monkeypatch.setattr(mod.time, "monotonic", lambda: next(times))  # +10s per call
    with pytest.raises(mod.EmbeddingUnavailable):
        mod.embed_queries(["x"])


def test_4xx_is_not_retried(eg2):
    mod, stub = eg2
    stub.status = 400
    with pytest.raises(mod.EmbeddingUnavailable):
        mod.embed_documents(["x"])
    assert len(stub.requests) == 1


def test_wrong_dimension_raises(eg2):
    mod, stub = eg2
    stub.dim = 1024
    with pytest.raises(mod.EmbeddingUnavailable):
        mod.embed_documents(["x"])
    assert len(stub.requests) == 1


def test_health_probe_and_cache(eg2):
    mod, stub = eg2
    h1 = mod.health()
    h2 = mod.health()
    assert h1["ok"] is True and h1["backend"] == "eg2"
    assert h2 == h1
    assert stub.health_hits == 1


def test_eg2_thresholds_differ_from_bge_and_env_override(eg2, monkeypatch):
    mod, _ = eg2
    assert mod.dim() == 768
    assert mod.threshold("dedup_semantic") > 0.86
    assert mod.threshold("synthesis_max_distance") < 0.75
    monkeypatch.setenv("AII_EMBED_THRESHOLD_DEDUP__SEMANTIC", "0.5")
    assert mod.threshold("dedup_semantic") == 0.5


def test_doc_text_convention():
    mod = _load()
    assert mod.doc_text("标题", "正文") == "标题\n正文"
    assert mod.doc_text("", "正文") == "正文"
    assert mod.doc_text("标题", None) == "标题"
    assert len(mod.doc_text("t", "x" * 5000)) == 1800


def test_bge_backend_keeps_legacy_values(monkeypatch):
    monkeypatch.setenv("AII_EMBED_BACKEND", "bge")
    mod = _load()
    assert mod.backend() == "bge"
    assert mod.dim() == 1024
    assert mod.threshold("dedup_semantic") == 0.86
    assert mod.threshold("synthesis_max_distance") == 0.75
    assert mod.health()["backend"] == "bge"
    assert mod.embed_documents([]) == []
