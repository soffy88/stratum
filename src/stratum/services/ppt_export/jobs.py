"""Owner-scoped asynchronous PPT export jobs.

A request inserts a ``queued`` row and hands ``run_job`` to the API's
background tasks (the same pattern as OCR and bundle split). The runner moves
the row through ``running`` stages with a progress percentage and ends in
``succeeded`` (file on disk) or ``failed`` (error message). Every read filters
on the hashed owner id, so another user's job id resolves to "not found".

Files live under ``STRATUM_DATA_DIR/ppt_exports/<owner>/<job_id>/`` next to the
other derived artefacts (translations, visual tiles).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from stratum.common import generate_ulid
from stratum.services.ppt_export.styles import DEFAULT_STYLE, style_ids
from stratum.utils.user_id_hash import hash_user_id

log = logging.getLogger(__name__)

TABLE = "stratum.ppt_export_jobs"
STALE_AFTER = timedelta(minutes=int(os.environ.get("PPT_JOB_STALE_MIN", "20")))
HEARTBEAT_S = 60.0
_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get("PPT_MAX_CONCURRENT", "2"))))
_COLUMNS = (
    "id, user_id, substrate_id, run_id, chapter_id, style, pages, options_json, status, stage, "
    "progress, title, language, file_path, file_size, slide_count, preview_count, qa_json, "
    "model, error, created_at, updated_at, started_at, finished_at"
)

# Stage -> (start %, end %) of the overall bar.
STAGES = {
    "collecting": (2, 8),
    "writing": (8, 70),
    "checking": (70, 76),
    "designing": (76, 96),
    "finishing": (96, 99),
}


def owner_of(user_id: str) -> str:
    return hash_user_id(user_id)


def exports_root() -> Path:
    from stratum.config import DATA_DIR

    return Path(os.environ.get("STRATUM_DATA_DIR", str(DATA_DIR))) / "ppt_exports"


class _DB:
    def query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        from stratum.db import query

        return query(sql, params)

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        from stratum.db import execute

        execute(sql, params)


db: Any = _DB()


# ── ownership ────────────────────────────────────────────────────────────────


def owned_substrate(user_id: str, substrate_id: str) -> dict[str, Any] | None:
    """The substrate when the caller owns it (raw or hashed owner id), else None."""
    rows = db.query(
        "SELECT id, title FROM stratum.substrates "
        "WHERE id=%(sid)s AND user_id IN (%(uid)s, %(huid)s) LIMIT 1",
        {"sid": substrate_id, "uid": user_id, "huid": owner_of(user_id)},
    )
    return rows[0] if rows else None


def owned_run(user_id: str, run_id: str) -> dict[str, Any] | None:
    """Resolve a BU2 run id to its substrate when the caller owns the book."""
    rows = db.query(
        "SELECT bu.substrate_id AS id, s.title FROM stratum.book_understandings_v2 bu "
        "JOIN stratum.substrates s ON s.id = bu.substrate_id "
        "WHERE bu.run_id=%(rid)s AND s.user_id IN (%(uid)s, %(huid)s) LIMIT 1",
        {"rid": run_id, "uid": user_id, "huid": owner_of(user_id)},
    )
    return rows[0] if rows else None


# ── repository ───────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def create_job(
    user_id: str,
    substrate_id: str,
    *,
    style: str = DEFAULT_STYLE,
    pages: int = 12,
    chapter_id: str | None = None,
    run_id: str | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if style not in style_ids():
        raise ValueError(f"unknown style {style!r}")
    job_id = generate_ulid()
    db.execute(
        f"INSERT INTO {TABLE} (id, user_id, substrate_id, run_id, chapter_id, style, pages, "
        "options_json, status, stage, progress) VALUES (%(id)s, %(owner)s, %(sid)s, %(rid)s, "
        "%(cid)s, %(style)s, %(pages)s, %(opts)s::jsonb, 'queued', 'queued', 0)",
        {
            "id": job_id,
            "owner": owner_of(user_id),
            "sid": substrate_id,
            "rid": run_id,
            "cid": chapter_id,
            "style": style,
            "pages": pages,
            "opts": json.dumps(options or {}, ensure_ascii=False),
        },
    )
    job = get_job(user_id, job_id)
    assert job is not None
    return job


def _expire_if_stale(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("status") not in ("queued", "running"):
        return job
    updated = job.get("updated_at")
    if isinstance(updated, datetime):
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        limit = STALE_AFTER if job.get("status") == "running" else STALE_AFTER * 6
        if _now() - updated > limit:
            _update(job["id"], status="failed", error="interrupted (no progress)", stage="failed")
            job = {**job, "status": "failed", "error": "interrupted (no progress)"}
    return job


def get_job(user_id: str, job_id: str) -> dict[str, Any] | None:
    """The job when it belongs to ``user_id``; None for unknown *or foreign* ids."""
    rows = db.query(
        f"SELECT {_COLUMNS} FROM {TABLE} WHERE id=%(id)s AND user_id=%(owner)s LIMIT 1",
        {"id": job_id, "owner": owner_of(user_id)},
    )
    return _expire_if_stale(rows[0]) if rows else None


def list_jobs(
    user_id: str, substrate_id: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    rows = db.query(
        f"SELECT {_COLUMNS} FROM {TABLE} WHERE user_id=%(owner)s "
        "AND (%(sid)s::text IS NULL OR substrate_id=%(sid)s) "
        "ORDER BY created_at DESC LIMIT %(limit)s",
        {"owner": owner_of(user_id), "sid": substrate_id, "limit": int(limit)},
    )
    return [_expire_if_stale(r) for r in rows]


def _update(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = []
    params: dict[str, Any] = {"id": job_id}
    for k, v in fields.items():
        if k in ("qa_json", "options_json"):
            sets.append(f"{k} = %({k})s::jsonb")
            params[k] = json.dumps(v, ensure_ascii=False, default=str)
        else:
            sets.append(f"{k} = %({k})s")
            params[k] = v
    sets.append("updated_at = NOW()")
    db.execute(f"UPDATE {TABLE} SET {', '.join(sets)} WHERE id=%(id)s", params)


def _progress_cb(job_id: str):
    last = {"pct": -1}

    def cb(stage: str, fraction: float) -> None:
        lo, hi = STAGES.get(stage, (0, 99))
        pct = int(lo + (hi - lo) * max(0.0, min(1.0, fraction)))
        if pct != last["pct"]:
            last["pct"] = pct
            _update(job_id, stage=stage, progress=pct)

    return cb


def job_dir(owner: str, job_id: str) -> Path:
    return exports_root() / owner / job_id


# ── runner ───────────────────────────────────────────────────────────────────


def run_job(job_id: str, owner: str) -> None:
    """Execute one job end to end. Never raises; failures land on the row."""
    rows = db.query(
        f"SELECT {_COLUMNS} FROM {TABLE} WHERE id=%(id)s AND user_id=%(owner)s LIMIT 1",
        {"id": job_id, "owner": owner},
    )
    if not rows:
        log.warning("ppt export job %s vanished before it ran", job_id)
        return
    job = rows[0]
    with _SLOTS:
        stop = threading.Event()
        beat = threading.Thread(target=_heartbeat, args=(job_id, stop), daemon=True)
        beat.start()
        try:
            _execute(job)
        except Exception as exc:  # report, never crash the worker
            log.exception("ppt export job %s failed", job_id)
            _update(
                job_id,
                status="failed",
                stage="failed",
                error=str(exc)[:800] or exc.__class__.__name__,
                finished_at=_now(),
            )
        finally:
            stop.set()


def _heartbeat(job_id: str, stop: threading.Event) -> None:
    """Keep ``updated_at`` fresh while a long model call is in flight.

    A job whose row stops moving for ``STALE_AFTER`` is reported as interrupted
    (the process died); a slow gateway must not look like that.
    """
    while not stop.wait(HEARTBEAT_S):
        try:
            db.execute(
                f"UPDATE {TABLE} SET updated_at = NOW() WHERE id=%(id)s AND status='running'",
                {"id": job_id},
            )
        except Exception:  # best effort
            log.debug("heartbeat failed for %s", job_id, exc_info=True)


def _execute(job: dict[str, Any]) -> None:
    from stratum.services.ppt_export.deck_builder import DeckOptions, build_deck
    from stratum.services.ppt_export.engine import render_deck
    from stratum.services.ppt_export.llm import ppt_provider_config, resolve_ppt_provider
    from stratum.services.ppt_export.material import load_material

    job_id = job["id"]
    progress = _progress_cb(job_id)
    _update(job_id, status="running", stage="collecting", progress=2, started_at=_now())
    material = load_material(job["substrate_id"], run_id=job.get("run_id"))
    _update(job_id, language=material.language, run_id=material.run_id)
    progress("collecting", 1.0)

    opts_raw = job.get("options_json") or {}
    if isinstance(opts_raw, str):
        opts_raw = json.loads(opts_raw or "{}")
    opts = DeckOptions(
        pages=int(job["pages"]),
        chapter_id=job.get("chapter_id"),
        audience=str(opts_raw.get("audience") or ""),
        notes=bool(opts_raw.get("notes", True)),
    )
    provider = resolve_ppt_provider()
    deck, report = build_deck(material, opts, provider, progress=progress)

    work = job_dir(job["user_id"], job_id) / "work"
    result = render_deck(deck, job["style"], work, progress=progress)
    progress("finishing", 0.0)

    final_dir = job_dir(job["user_id"], job_id)
    out = final_dir / "deck.pptx"
    shutil.copyfile(result.pptx, out)
    previews_dir = final_dir / "previews"
    previews_dir.mkdir(exist_ok=True)
    for i, p in enumerate(result.previews, 1):
        shutil.copyfile(p, previews_dir / f"slide-{i:02d}.png")

    qa = {
        "counts": result.qa.get("counts", {}),
        "errors": [i for i in result.qa.get("issues", []) if i.get("level") == "ERROR"][:20],
        "warnings": [i for i in result.qa.get("issues", []) if i.get("level") == "WARN"][:20],
        "outline_warnings": [m for lvl, _n, m in result.outline if lvl == "WARN"][:20],
        "fixes": result.fixes,
        "renderer": result.renderer,
        "model_calls": report.model_calls,
        "language_retries": report.language_retries,
        "fallback_slides": report.fallback_slides,
        "titles_polished": report.titles_polished,
        "notes": report.warnings[:20],
    }
    cfg = ppt_provider_config()
    _update(
        job_id,
        status="succeeded",
        stage="done",
        progress=100,
        title=deck["meta"].get("title") or "",
        file_path=str(out),
        file_size=out.stat().st_size,
        slide_count=len(deck["slides"]),
        preview_count=len(result.previews),
        qa_json=qa,
        model=f"{cfg['provider']}:{cfg['model']}",
        finished_at=_now(),
        error=None,
    )
    # Keep deck.json/plan.json for debugging; drop the bulky intermediate assets.
    shutil.rmtree(work / "assets", ignore_errors=True)
