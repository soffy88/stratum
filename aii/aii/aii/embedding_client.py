"""AII embedding client — BGE-M3 (legacy) or EmbeddingGemma2 (768-d).

Unified entry point for every embedding call in the AII + stratum-sl
stacks.  The active backend is selected with ``AII_EMBED_BACKEND``
(``bge`` = legacy behavior, default; ``eg2`` = EmbeddingGemma2 via the
OpenAI-compatible gateway).

eg2 contract (validated by the AII retrieval A/B):
  * POST ``{AII_EMBED_BASE_URL}/embeddings`` with
    ``{"model": ..., "input": [...], "dimensions": 768}``
  * query texts use ``AII_EMBED_QUERY_MODEL`` (server adds the
    ``SearchQuery`` prefix), document texts use
    ``AII_EMBED_DOC_MODEL`` (server adds the ``Document`` prefix)
  * document text convention: ``doc_text(title, body) =
    (f"{title}\\n{body}" if title and body else title or body)[:1800]``
  * shared laptop GPU: at most 4 texts per request, larger lists are
    batched serially
  * HTTP must bypass the corporate proxy (the machine sets http_proxy)
  * connection failures / 5xx / timeouts retry with exponential
    backoff; query calls give up after 30s of total waiting, document
    writes after 120s, both raising :class:`EmbeddingUnavailable`
  * wrong response count or wrong dimension raises (never persist a
    bad vector)

bge backend keeps the existing behavior exactly: embedding calls go
through the ``ProviderRegistry`` ``("embedding", "default")`` provider
(``AII_EMBED_URL`` remote embedder, or in-process BGE-M3).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

__all__ = [
    "EmbeddingUnavailable",
    "backend",
    "dim",
    "doc_text",
    "embed_documents",
    "embed_queries",
    "health",
    "threshold",
]


class EmbeddingUnavailable(RuntimeError):
    """Embedding backend failed (after retries) or returned bad shapes."""


# ── Backend selection / configuration ─────────────────────────────────


def backend() -> str:
    """Active embedding backend: "bge" (default, legacy) or "eg2"."""
    return os.getenv("AII_EMBED_BACKEND", "bge").strip().lower() or "bge"


def dim() -> int:
    """Embedding dimension: bge=1024, eg2=$AII_EMBED_DIM (default 768)."""
    if backend() == "eg2":
        return int(os.getenv("AII_EMBED_DIM", "768"))
    return 1024


EG2_BASE_URL = os.getenv("AII_EMBED_BASE_URL", "http://100.68.226.13:8790/v1")
EG2_QUERY_MODEL = os.getenv("AII_EMBED_QUERY_MODEL", "embeddinggemma-2-query")
EG2_DOC_MODEL = os.getenv("AII_EMBED_DOC_MODEL", "embeddinggemma-2-document")
EG2_BATCH = 4  # shared laptop GPU: >4 concurrent texts OOM the service
EG2_MAX_CHARS = 1800

# EmbeddingGemma2 thresholds, calibrated 2026-10-13 on production data
# (/data/soffy/tmp/aii_eg2/calibration*.json): doc-doc thresholds by quantile
# mapping of within-substrate KU pair similarities measured on the SAME rows in
# both spaces (t_eg2 = Q_eg2(F_bge(t_bge)) keeps the share of pairs above the
# threshold); query-doc gates from the gold/irrelevant similarity distribution
# of the 104-query AII A/B set.  EG2 similarities sit higher than BGE-M3's
# (median KU pair 0.76 vs 0.61), so the BGE values must not be reused.
EG2_THRESHOLDS: dict[str, float] = {
    "dedup_semantic": 0.92,
    "chapter_dedup": 0.90,
    "concept_screen": 0.92,
    "cross_chunk": 0.89,
    "cooccurrence": 0.89,
    "context_recall": 0.72,
    # cosine *distance* gate for "no grounding" (+ HyDE retry).  BGE's 0.75
    # (sim < 0.25) sat far below even the irrelevant-doc mean (sim 0.39), i.e. it
    # only fired when retrieval returned essentially nothing.  Same position in
    # the EG2 distribution (irrelevant mean 0.60, gold mean 0.81) is sim ~0.49 →
    # distance 0.50; keep that parity rather than a stricter gate that would
    # change answer behaviour (judgment call, see calibration notes).
    "synthesis_max_distance": 0.50,
}

# BGE-calibrated originals (behavior parity when backend() == "bge").
_BGE_THRESHOLDS: dict[str, float] = {
    "dedup_semantic": 0.86,
    "chapter_dedup": 0.82,
    "concept_screen": 0.85,
    "cross_chunk": 0.80,
    "cooccurrence": 0.80,
    "synthesis_max_distance": 0.75,
    "context_recall": 0.55,
}


def threshold(name: str) -> float:
    """Cosine threshold by site name.  bge → original values; eg2 →
    EG2_THRESHOLDS (calibrated on production data).

    Env overrides still win: a caller-side ``AII_EMBED_THRESHOLD_<NAME>``
    (underscore→double underscore, e.g. ``AII_EMBED_THRESHOLD_DEDUP__SEMANTIC``
    for name ``dedup_semantic``) beats the backend defaults, and the legacy
    per-site vars (``DEDUP_SEMANTIC_SIM_THRESHOLD`` etc.) keep their own
    precedence where they already exist."""
    env_key = "AII_EMBED_THRESHOLD_" + name.upper().replace("_", "__")
    raw = os.getenv(env_key, "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            logger.warning("%s=%r is not a number, ignoring", env_key, raw)
    if backend() == "eg2":
        return EG2_THRESHOLDS.get(name, _BGE_THRESHOLDS.get(name, 0.8))
    return _BGE_THRESHOLDS.get(name, 0.8)


# ── Document text convention (must match scripts/eg2_backfill.py) ─────


def doc_text(title: str | None, body: str | None) -> str:
    """Unified document text: ``title\\nbody`` when both present, else
    whichever exists, truncated to 1800 chars.  body prefers Chinese
    (caller passes ``natural_text_zh or natural_text``)."""
    title = (title or "").strip()
    body = (body or "").strip()
    text = f"{title}\n{body}" if title and body else (title or body)
    return text[:EG2_MAX_CHARS]


# ── eg2 HTTP transport (stdlib only, proxy bypassed, retried) ─────────

# Bypass the machine's http_proxy: the gateway is on the LAN.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _eg2_post(model: str, texts: list[str], budget_s: float) -> list[list[float]]:
    """POST one batch of ≤4 texts; returns vectors in request order."""
    payload = json.dumps({"model": model, "input": texts, "dimensions": dim()}).encode()
    req = urllib.request.Request(
        f"{EG2_BASE_URL.rstrip('/')}/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    attempt = 0
    delay = 1.0
    while True:
        attempt += 1
        try:
            with _OPENER.open(req, timeout=30) as resp:
                status_code = resp.status
                body = json.loads(resp.read())
            if 400 <= status_code < 500:
                raise EmbeddingUnavailable(
                    f"eg2 client error (HTTP {status_code}), not retrying: {body}"
                )
            data = sorted(body.get("data") or [], key=lambda d: d.get("index", 0))
            vecs = [d.get("embedding") for d in data]
            if len(vecs) != len(texts):
                raise EmbeddingUnavailable(
                    f"eg2 returned {len(vecs)} vectors for {len(texts)} texts"
                )
            for v in vecs:
                if not isinstance(v, list) or len(v) != dim():
                    raise EmbeddingUnavailable(
                        f"eg2 returned bad dimension {None if v is None else len(v)} "
                        f"(expected {dim()})"
                    )
            return [[float(x) for x in v] for v in vecs]
        except EmbeddingUnavailable:
            raise  # shape errors and client errors are not transient
        except urllib.error.HTTPError as e:
            # 5xx or connection errors: retry with backoff
            if 500 <= e.code < 600:
                waited = time.monotonic() - started
                if waited >= budget_s:
                    raise EmbeddingUnavailable(
                        f"eg2 embedding unavailable after {waited:.1f}s "
                        f"({attempt} attempts): HTTP {e.code} {e.reason}"
                    )
                time.sleep(min(delay, max(0.0, budget_s - waited)))
                delay = min(delay * 2, 8.0)
            else:  # 4xx: bad request / unknown model — retrying cannot help
                raise EmbeddingUnavailable(
                    f"eg2 rejected the request: HTTP {e.code} {e.reason}"
                ) from e
        except Exception as e:  # timeout / bad json / other
            waited = time.monotonic() - started
            if waited >= budget_s:
                raise EmbeddingUnavailable(
                    f"eg2 embedding unavailable after {waited:.1f}s "
                    f"({attempt} attempts): {e!r:.160}"
                )
            time.sleep(min(delay, max(0.0, budget_s - waited)))
            delay = min(delay * 2, 8.0)


def _eg2_embed(texts: list[str], model: str, budget_s: float) -> list[list[float]]:
    """Batch serially in groups of 4, total-budget retry per batch."""
    out: list[list[float]] = []
    for i in range(0, len(texts), EG2_BATCH):
        batch = [t[:EG2_MAX_CHARS] if t else "" for t in texts[i : i + EG2_BATCH]]
        out.extend(_eg2_post(model, batch, budget_s))
    return out


# ── bge transport (existing ProviderRegistry path, unchanged) ─────────


def _bge_embed(texts: list[str]) -> list[list[float]]:
    """Existing default embedding provider (remote AII_EMBED_URL service
    or in-process BGE-M3).  Registered by aii.api._provider.register_providers."""
    from obase import ProviderRegistry

    embed_fn = ProviderRegistry.get()._generic.get("embedding", {}).get("default")
    if embed_fn is None:
        raise EmbeddingUnavailable(
            'no ("embedding", "default") provider registered — '
            "call aii.api._provider.register_providers() first"
        )
    vecs = embed_fn(list(texts))
    return [[float(x) for x in v] for v in vecs]


# ── Public API ────────────────────────────────────────────────────────


def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed search/query texts (eg2 adds the SearchQuery prefix)."""
    if not texts:
        return []
    if backend() == "eg2":
        return _eg2_embed(list(texts), EG2_QUERY_MODEL, budget_s=30.0)
    return _bge_embed(list(texts))


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document texts (eg2 adds the Document prefix).  Write path
    gets a longer retry budget (120s) so transient GPU hiccups don't
    drop vectors."""
    if not texts:
        return []
    if backend() == "eg2":
        return _eg2_embed(list(texts), EG2_DOC_MODEL, budget_s=120.0)
    return _bge_embed(list(texts))


# ── Health ────────────────────────────────────────────────────────────

_HEALTH_CACHE: dict[str, object] = {"at": 0.0, "value": None}
_HEALTH_TTL = 30.0


def health() -> dict:
    """Embedding backend health (cached 30s; eg2 probes {base}/health
    with a 3s timeout so a down service never blocks the caller)."""
    now = time.monotonic()
    if _HEALTH_CACHE["value"] is not None and now - _HEALTH_CACHE["at"] < _HEALTH_TTL:
        return dict(_HEALTH_CACHE["value"])  # type: ignore[arg-type]
    value = _health_uncached()
    _HEALTH_CACHE["at"] = now
    _HEALTH_CACHE["value"] = value
    return dict(value)


def _health_uncached() -> dict:
    base = EG2_BASE_URL.rstrip("/")
    if backend() != "eg2":
        return {"backend": "bge", "base_url": os.getenv("AII_EMBED_URL", ""), "ok": True}
    started = time.monotonic()
    try:
        req = urllib.request.Request(base.replace("/v1", "", 1) + "/health")
        with _OPENER.open(req, timeout=3) as resp:
            resp.read()
        return {
            "backend": "eg2",
            "base_url": base,
            "ok": True,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as e:
        return {
            "backend": "eg2",
            "base_url": base,
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": f"{type(e).__name__}: {e}",
        }
