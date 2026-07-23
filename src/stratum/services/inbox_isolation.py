"""Run process_inbox_substrate in an isolated subprocess + attempt/quarantine ledger.

Why a subprocess: native libs on the parse path (PyMuPDF/fitz's MuPDF C core,
lancedb's Rust runtime) can HARD-crash the whole process on a malformed input.
On 2026-07-09 one arXiv PDF (2607.07313) crash-looped stratum-sl 103 times — the
child died with a clean exit(0) right after detect_pdf_features. A Python thread
cannot contain a native segfault/exit(); a subprocess can.

Because the crash exits 0 *silently*, the return code is untrustworthy — the child
writes a sentinel result file on success; "process ended but no sentinel" == crashed.

Outcome classification (critical): infra failures (embed 5xx, PG down, GPU absent)
must NOT consume an item's retry budget — otherwise a transient dependency outage
would auto-quarantine perfectly good books. Only item-intrinsic failures (native
crash, parse error, hang) count toward the quarantine threshold.

This module is BOTH the parent-side API (run_isolated / ledger helpers) and the
child entrypoint (``python -m stratum.services.inbox_isolation --run job result``).
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# item_fail-class outcomes consume the retry budget; infra_fail / completed do not.
_BUDGET_CONSUMING = {"crashed", "item_fail", "timeout"}
_QUARANTINE_THRESHOLD = 3

# Substrings that mark a dependency/infra failure (not the item's fault).
_INFRA_MARKERS = (
    "embed",
    "aii_remote",
    "connection",
    "operationalerror",
    "psycopg",
    "timed out",
    "timeout",
    "502",
    "503",
    "504",
    "econnrefused",
    "gpu",
    "cuda",
    "no devices",
    "unreachable",
)


def _is_infra_error(err: str) -> bool:
    e = (err or "").lower()
    return any(m in e for m in _INFRA_MARKERS)


# ── parent-side: run one item in an isolated subprocess ───────────────────────


def run_isolated(job: dict, timeout_sec: float) -> dict:
    """Run process_inbox_substrate for *job* in a subprocess.

    Returns {outcome, status, substrate_id, error}. outcome ∈
    completed | item_fail | infra_fail | timeout | crashed.
    """
    with tempfile.TemporaryDirectory(prefix="inboxjob_") as td:
        jobf = Path(td) / "job.json"
        resf = Path(td) / "result.json"
        jobf.write_text(json.dumps(job))
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "stratum.services.inbox_isolation",
                "--run",
                str(jobf),
                str(resf),
            ],
            start_new_session=True,  # own process group so we can SIGKILL the whole tree
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            _, stderr = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            # native libs ignore SIGTERM; kill the group hard, then reap.
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            return {
                "outcome": "timeout",
                "status": "failed",
                "substrate_id": None,
                "error": f"timeout after {timeout_sec:.0f}s",
            }

        if resf.exists():
            try:
                res = json.loads(resf.read_text())
            except Exception as exc:
                return {
                    "outcome": "crashed",
                    "status": "failed",
                    "substrate_id": None,
                    "error": f"unreadable sentinel: {exc}",
                }
            if res.get("status") == "completed":
                return {"outcome": "completed", **res}
            outcome = "infra_fail" if _is_infra_error(res.get("error") or "") else "item_fail"
            return {"outcome": outcome, **res}

        # process ended with no sentinel → native crash / clean-exit death. Poison signal.
        tail = (stderr.decode("utf-8", "replace")[-800:] if stderr else "").strip()
        return {
            "outcome": "crashed",
            "status": "failed",
            "substrate_id": None,
            "error": tail or f"no sentinel, exit={proc.returncode}",
        }


# ── ledger: attempts + quarantine (aii-postgres stratum schema) ───────────────


def is_quarantined(item_key: str) -> bool:
    from stratum.db import get_conn

    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM ingest_quarantine WHERE item_key=?", (item_key,)
            ).fetchone()
        return bool(row)
    except Exception as exc:
        log.warning("ingest_ledger: quarantine check failed key=%s: %s", item_key, exc)
        return False


def record_attempt(item_key: str, source_type: str | None, outcome: str, error: str | None) -> bool:
    """Log an attempt; auto-quarantine when budget-consuming failures reach the
    threshold. Returns True if the item is (now) quarantined."""
    from stratum.db import get_conn

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO ingest_attempts (item_key, source_type, outcome, error) VALUES (?,?,?,?)",
                (item_key, source_type, outcome, (error or "")[:2000]),
            )
            if outcome not in _BUDGET_CONSUMING:
                return False
            n = conn.execute(
                "SELECT count(*) FROM ingest_attempts WHERE item_key=? AND outcome = ANY(?)",
                (item_key, list(_BUDGET_CONSUMING)),
            ).fetchone()[0]
            if n >= _QUARANTINE_THRESHOLD:
                conn.execute(
                    "INSERT INTO ingest_quarantine (item_key, source_type, reason, fail_count) "
                    "VALUES (?,?,?,?) ON CONFLICT (item_key) DO UPDATE SET fail_count=EXCLUDED.fail_count",
                    (
                        item_key,
                        source_type,
                        f"{n} budget-consuming failures (last outcome={outcome}): {(error or '')[:200]}",
                        n,
                    ),
                )
                log.error(
                    "ingest_ledger: QUARANTINED key=%s after %d failures (last=%s)",
                    item_key,
                    n,
                    outcome,
                )
                return True
        return False
    except Exception as exc:
        log.warning("ingest_ledger: record_attempt failed key=%s: %s", item_key, exc)
        return False


# ── child entrypoint ──────────────────────────────────────────────────────────


def _child_run(jobfile: str, resultfile: str) -> None:
    job = json.loads(Path(jobfile).read_text())
    from omodul.process_inbox_substrate import InboxConfig, InboxInput, process_inbox_substrate

    config = InboxConfig(
        file_path=Path(job["file_path"]),
        file_checksum=job["file_checksum"],
        user_id_hash=job["user_id_hash"],
        medium_hint=job.get("medium_hint"),
        auto_classify=job.get("auto_classify", True),
        llm_provider=job.get("llm_provider", "qwen3_dashscope"),
        llm_model=job.get("llm_model", "qwen-plus"),
    )
    res = process_inbox_substrate(
        config=config, input_data=InboxInput(), output_dir=Path(job["output_dir"])
    )
    findings = res.get("findings")
    err = res.get("error")
    err_msg = err.get("error_message") if isinstance(err, dict) else err
    out = {
        "status": res.get("status"),
        "substrate_id": getattr(findings, "substrate_id", None) if findings else None,
        "error": err_msg,
    }
    # sentinel: its very existence is the "did not crash" proof
    Path(resultfile).write_text(json.dumps(out))


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--run":
        _child_run(sys.argv[2], sys.argv[3])
    else:  # pragma: no cover
        sys.exit("usage: python -m stratum.services.inbox_isolation --run <job.json> <result.json>")
