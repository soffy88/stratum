#!/usr/bin/env python3
"""AII flywheel health checker — every 30 min (aii-flywheel-health.timer).

Per flywheel it detects:
  * unit dead / restarting (ActiveState != active, NRestarts grew)
  * log not growing (no bytes for > LOG_STALE_H hours while unit is active)
  * hot loop (> HOT_CYCLES_PER_H cycles/hour with 0 books ingested in the window)
  * high LLM error rate (>= LLM_ERR_PER_H matching error lines per hour)
  * KU output zero for 24h (aii.ku_onto rows by substrate prefix)
  * log size > LOG_MAX_MB (rotated: gzip copy + in-place truncate)
plus pipeline-level checks: aii-* timers that will never fire again (bad
OnCalendar / elapsed OnBootSec) and the feeder's staged-markdown freshness.

Safe auto-remediation only: restart a dead / stale unit (max RESTART_MAX per
RESTART_WINDOW_H, so a crash loop is alerted instead of hammered), rotate an
oversized log, and add an idle-sleep backoff drop-in for a hot-looping unit.
It never edits code, LLM config or the database.

Outputs (machine-readable):
  /home/soffy/shared/aii-health/status.json   current state per flywheel
  /home/soffy/shared/aii-health/alerts.log    one JSON line per anomaly
  /home/soffy/shared/aii-health/state.json    private bookkeeping (offsets, history)

Usage: flywheel_health.py [--dry-run] [--no-remediate]
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

AII = Path(os.getenv("AII_ROOT", "/data/soffy/projects/stratum/aii"))
OUT = Path(os.getenv("AII_HEALTH_DIR", "/home/soffy/shared/aii-health"))
STATUS = OUT / "status.json"
ALERTS = OUT / "alerts.log"
STATE = OUT / "state.json"
DROPIN_DIR = Path.home() / ".config/systemd/user"

LOG_STALE_H = float(os.getenv("AII_HEALTH_LOG_STALE_H", "3"))
# a normal idle loop sleeps 120s (~30 cycles/h); the econ-zh incident was ~420/h
HOT_CYCLES_PER_H = float(os.getenv("AII_HEALTH_HOT_CYCLES_PER_H", "90"))
MIN_RATE_WINDOW_MIN = float(os.getenv("AII_HEALTH_MIN_RATE_WINDOW_MIN", "20"))
LLM_ERR_PER_H = float(os.getenv("AII_HEALTH_LLM_ERR_PER_H", "60"))
LOG_MAX_MB = float(os.getenv("AII_HEALTH_LOG_MAX_MB", "200"))
RESTART_MAX = int(os.getenv("AII_HEALTH_RESTART_MAX", "3"))
RESTART_WINDOW_H = float(os.getenv("AII_HEALTH_RESTART_WINDOW_H", "6"))
BACKOFF_SLEEP = int(os.getenv("AII_HEALTH_BACKOFF_SLEEP", "900"))
SCAN_MAX_BYTES = 64 * 1024 * 1024  # never read more than this per run
ROTATE_KEEP = 3

# name -> unit, log, KU/ingest substrate prefix, idle-sleep env var of its run script
FLYWHEELS: dict[str, dict[str, str]] = {
    "advmath": {
        "log": "advmath_pipeline/flywheel.log",
        "prefix": "advmath_",
        "idle": "ADVMATH_IDLE_SLEEP",
    },
    "cs": {"log": "cs_pipeline/flywheel_cs.log", "prefix": "cs_", "idle": "ECON_IDLE_SLEEP"},
    "econ-zh": {
        "log": "econ_pipeline/flywheel_zh.log",
        "prefix": "econ_zh",
        "idle": "ECON_IDLE_SLEEP",
    },
    "edu": {"log": "edu_pipeline/flywheel_edu.log", "prefix": "edu_", "idle": "ECON_IDLE_SLEEP"},
    "math-prog": {
        "log": "math_pipeline/flywheel_prog.log",
        "prefix": "math_prog",
        "idle": "MATH_IDLE_SLEEP",
    },
    "misc": {
        "log": "misc_pipeline/flywheel_misc.log",
        "prefix": "misc_",
        "idle": "ECON_IDLE_SLEEP",
    },
    "paper": {"log": "paper_pipeline/flywheel.log", "prefix": "paper_", "idle": "PAPER_IDLE_SLEEP"},
}
OTHER_LOGS = {"feeder": "econ_pipeline/feeder.log", "pull_ingest": ".logs/pull_ingest.out"}
STAGE = AII / "gdrive_staging" / "MD"

CYCLE_RE = re.compile(rb"\xe9\xa3\x9e\xe8\xbd\xae\xe5\xae\x8c\xe6\x88\x90")  # "飞轮完成"
IDLE_CYCLE_RE = re.compile("飞轮完成[:：]\\s*无新".encode())
LLM_ERR_RE = re.compile(
    rb"HTTP Error (?:5\d\d|429|412)|\b50[234]\b[^\n]{0,40}(?:Bad Gateway|Service Unavailable|Gateway Time)"
    rb"|Bad Gateway|Service Unavailable|Gateway Timeout|Precondition Failed|[Rr]ate ?limit"
    rb"|LLM[^\n]{0,60}(?:\xe5\xa4\xb1\xe8\xb4\xa5|fail|error|Error)"  # 失败
)


def now() -> float:
    return time.time()


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def sh(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 99, str(exc)


def unit_show(unit: str) -> dict[str, str]:
    rc, out = sh(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "NRestarts",
            "-p",
            "ActiveEnterTimestampMonotonic",
            "-p",
            "LoadState",
        ]
    )
    info = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def psql(sql: str) -> list[list[str]]:
    rc, out = sh(
        [
            "docker",
            "exec",
            "aii-postgres",
            "psql",
            "-U",
            "aii",
            "-d",
            "aii_kg",
            "-tA",
            "-F",
            "\t",
            "-c",
            sql,
        ],
        timeout=60,
    )
    if rc != 0:
        raise RuntimeError(out.strip()[:300])
    return [line.split("\t") for line in out.splitlines() if line.strip()]


def db_metrics() -> tuple[dict[str, dict], str | None]:
    """Per-prefix KU/book counts. One query per table; prefix match done in SQL."""
    out: dict[str, dict] = {n: {} for n in FLYWHEELS}
    vals = ",".join(f"('{n}','{c['prefix']}')" for n, c in FLYWHEELS.items())
    try:
        for name, ku24, ku1h in psql(
            f"WITH p(name,pre) AS (VALUES {vals}) SELECT p.name,"
            " count(k.ku_id) FILTER (WHERE k.created_at > now()-interval '24 hours'),"
            " count(k.ku_id) FILTER (WHERE k.created_at > now()-interval '1 hour')"
            " FROM p LEFT JOIN aii.ku_onto k ON k.substrate_id LIKE p.pre || '%'"
            " AND k.created_at > now()-interval '24 hours' GROUP BY p.name"
        ):
            out[name].update(ku_24h=int(ku24), ku_1h=int(ku1h))
        for name, b24, last in psql(
            f"WITH p(name,pre) AS (VALUES {vals}) SELECT p.name,"
            " count(i.substrate_id) FILTER (WHERE i.ingested_at > now()-interval '24 hours'),"
            " coalesce(to_char(max(i.ingested_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS+00:00'),'')"
            " FROM p LEFT JOIN aii.ingested_substrate i ON i.substrate_id LIKE p.pre || '%'"
            " GROUP BY p.name"
        ):
            out[name].update(books_24h=int(b24), last_ingest=last or None)
        return out, None
    except Exception as exc:  # noqa: BLE001
        return out, str(exc)


def books_since(prefix: str, since_ts: float) -> int | None:
    try:
        rows = psql(
            "SELECT count(*) FROM aii.ingested_substrate WHERE substrate_id LIKE "
            f"'{prefix}%' AND ingested_at > to_timestamp({int(since_ts)})"
        )
        return int(rows[0][0])
    except Exception:  # noqa: BLE001
        return None


def scan_log(path: Path, st: dict) -> dict:
    """Read bytes appended since last run; return counts. Handles truncation."""
    res = {
        "exists": path.exists(),
        "size": 0,
        "mtime": None,
        "new_bytes": 0,
        "cycles": 0,
        "idle_cycles": 0,
        "llm_errors": 0,
        "baseline": False,
    }
    if not path.exists():
        return res
    s = path.stat()
    res["size"], res["mtime"] = s.st_size, s.st_mtime
    off = st.get("offset")
    if off is None or off > s.st_size:  # first run or truncated/rotated
        res["baseline"] = off is None
        off = 0 if off is not None else s.st_size
    start = max(off, s.st_size - SCAN_MAX_BYTES)
    if s.st_size > start:
        with path.open("rb") as fh:
            fh.seek(start)
            data = fh.read(s.st_size - start)
        res["new_bytes"] = len(data)
        res["cycles"] = len(CYCLE_RE.findall(data))
        res["idle_cycles"] = len(IDLE_CYCLE_RE.findall(data))
        res["llm_errors"] = sum(1 for line in data.splitlines() if LLM_ERR_RE.search(line))
    st["offset"] = s.st_size
    if res["new_bytes"] > 0:
        st["last_growth"] = now()
    st.setdefault("last_growth", s.st_mtime)
    return res


def rotate_log(path: Path, dry: bool) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d%H%M")
    dst = path.with_name(f"{path.name}.{stamp}.gz")
    if dry:
        return f"would rotate {path} -> {dst}"
    with path.open("rb") as src, gzip.open(dst, "wb", compresslevel=3) as out:
        shutil.copyfileobj(src, out, 4 * 1024 * 1024)
    with path.open("r+b") as fh:  # writers use O_APPEND, so in-place truncate is safe
        fh.truncate(0)
    olds = sorted(path.parent.glob(f"{path.name}.*.gz"))
    for old in olds[:-ROTATE_KEEP]:
        old.unlink(missing_ok=True)
    return f"rotated {path.name} -> {dst.name}"


def restart_unit(unit: str, st: dict, dry: bool) -> tuple[bool, str]:
    hist = [t for t in st.get("restarts", []) if now() - t < RESTART_WINDOW_H * 3600]
    if len(hist) >= RESTART_MAX:
        st["restarts"] = hist
        return False, f"restart suppressed ({len(hist)} in {RESTART_WINDOW_H:g}h) — needs a human"
    if dry:
        return True, f"would restart {unit}"
    rc, out = sh(["systemctl", "--user", "restart", unit], timeout=120)
    hist.append(now())
    st["restarts"] = hist
    return rc == 0, f"restart {unit}: {'ok' if rc == 0 else out.strip()[:200]}"


def add_backoff(unit: str, var: str, dry: bool) -> tuple[bool, str]:
    d = DROPIN_DIR / f"{unit}.service.d"
    f = d / "zz-health-backoff.conf"
    if f.exists():
        return False, f"backoff already present ({f})"
    body = (
        "# written by aii flywheel_health.py: hot loop detected, idle sleep raised\n"
        f"[Service]\nEnvironment={var}={BACKOFF_SLEEP}\n"
    )
    if dry:
        return True, f"would write {f} ({var}={BACKOFF_SLEEP}) and restart"
    d.mkdir(parents=True, exist_ok=True)
    f.write_text(body)
    sh(["systemctl", "--user", "daemon-reload"])
    rc, out = sh(["systemctl", "--user", "restart", unit], timeout=120)
    return (
        rc == 0,
        f"backoff {var}={BACKOFF_SLEEP} + restart: {'ok' if rc == 0 else out.strip()[:200]}",
    )


def broken_timers() -> list[str]:
    """aii-* timers with no next elapse (they will never fire again)."""
    rc, out = sh(
        ["systemctl", "--user", "list-timers", "--all", "--no-pager", "--no-legend", "aii-*.timer"]
    )
    bad = []
    for line in out.splitlines():
        cols = line.split()
        if cols and cols[0] == "-" and len(cols) >= 2:
            m = re.search(r"(aii-[\w.-]+\.timer)", line)
            if not m:
                continue
            # while the triggered service is still running systemd shows no next elapse
            svc = m.group(1)[: -len(".timer")] + ".service"
            rc2, st = sh(["systemctl", "--user", "is-active", svc])
            if st.strip() not in ("active", "activating", "reloading"):
                bad.append(m.group(1))
    return bad


def stage_summary() -> dict:
    out = {}
    if STAGE.is_dir():
        for d in sorted(p for p in STAGE.iterdir() if p.is_dir()):
            mds = list(d.glob("*.md"))
            newest = max((m.stat().st_mtime for m in mds), default=None)
            out[d.name] = {
                "md": len(mds),
                "newest": iso(newest),
                "new_24h": sum(1 for m in mds if now() - m.stat().st_mtime < 86400),
            }
    return out


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    remediate = "--no-remediate" not in argv and not dry
    OUT.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    prev_run = state.get("last_run")
    t_now = now()
    window_h = max((t_now - prev_run) / 3600, 1 / 12) if prev_run else None
    db, db_err = db_metrics()
    alerts: list[dict] = []
    flywheels: dict[str, dict] = {}

    def alert(name: str, kind: str, detail: str, action: str | None = None) -> dict:
        a = {"ts": iso(t_now), "flywheel": name, "anomaly": kind, "detail": detail}
        if action:
            a["action"] = action
        alerts.append(a)
        return a

    for name, cfg in FLYWHEELS.items():
        unit = f"aii-flywheel-{name}"
        st = state.setdefault("flywheels", {}).setdefault(name, {})
        info = unit_show(unit)
        logp = AII / cfg["log"]
        scan = scan_log(logp, st)
        anomalies: list[dict] = []
        m = db.get(name, {})
        # 24h rolling history of per-run log counts
        hist = [h for h in st.get("hist", []) if t_now - h[0] < 86400]
        if not scan["baseline"]:
            hist.append([t_now, scan["cycles"], scan["llm_errors"]])
        st["hist"] = hist
        errors_24h = sum(h[2] for h in hist)

        active = info.get("ActiveState")
        nrest = int(info.get("NRestarts") or 0)
        if active != "active":
            act = None
            if remediate or dry:
                _, act = restart_unit(unit, st, dry)
            anomalies.append(
                alert(
                    name, "unit_dead", f"ActiveState={active} SubState={info.get('SubState')}", act
                )
            )
        elif nrest > st.get("nrestarts", nrest):
            anomalies.append(
                alert(name, "unit_restarting", f"NRestarts {st.get('nrestarts')} -> {nrest}")
            )
        st["nrestarts"] = nrest

        stale_h = (t_now - st.get("last_growth", t_now)) / 3600
        if active == "active" and stale_h > LOG_STALE_H:
            act = None
            if remediate or dry:
                _, act = restart_unit(unit, st, dry)
            anomalies.append(alert(name, "log_stale", f"log not growing for {stale_h:.1f}h", act))

        cycles_h = errs_h = None
        if window_h and not scan["baseline"]:
            cycles_h = scan["cycles"] / window_h
            errs_h = scan["llm_errors"] / window_h
            if cycles_h > HOT_CYCLES_PER_H and window_h * 60 >= MIN_RATE_WINDOW_MIN:
                got = books_since(cfg["prefix"], prev_run)
                if got == 0:
                    act = None
                    if remediate or dry:
                        _, act = add_backoff(unit, cfg["idle"], dry)
                    anomalies.append(
                        alert(
                            name,
                            "hot_loop",
                            f"{cycles_h:.0f} cycles/h ({scan['idle_cycles']} idle of {scan['cycles']}) with 0 books ingested",
                            act,
                        )
                    )
            if errs_h >= LLM_ERR_PER_H and window_h * 60 >= MIN_RATE_WINDOW_MIN:
                anomalies.append(alert(name, "llm_errors_high", f"{errs_h:.0f} LLM error lines/h"))

        if m.get("ku_24h") == 0:
            anomalies.append(
                alert(name, "ku_zero_24h", "no aii.ku_onto rows in 24h for prefix " + cfg["prefix"])
            )

        if scan["size"] > LOG_MAX_MB * 1024 * 1024:
            act = rotate_log(logp, dry) if (remediate or dry) else None
            if act and act.startswith("rotated"):
                st["offset"] = 0
            anomalies.append(
                alert(
                    name, "log_oversize", f"{scan['size'] / 1048576:.0f}MB > {LOG_MAX_MB:g}MB", act
                )
            )

        kinds = {a["anomaly"] for a in anomalies}
        if "unit_dead" in kinds:
            state_s = "dead"
        elif kinds & {"hot_loop", "log_stale", "llm_errors_high", "unit_restarting"}:
            state_s = "degraded"
        elif (
            m.get("books_24h", 0) == 0
            and scan["idle_cycles"]
            and scan["idle_cycles"] == scan["cycles"]
        ):
            state_s = "idle"  # healthy loop, simply no new input
        elif "ku_zero_24h" in kinds:
            state_s = "stalled"
        else:
            state_s = "ok"
        flywheels[name] = {
            "state": state_s,
            "unit": unit,
            "active": active,
            "last_ingest": m.get("last_ingest"),
            "books_24h": m.get("books_24h"),
            "ku_24h": m.get("ku_24h"),
            "errors_24h": errors_24h,
            "cycles_per_h": None if cycles_h is None else round(cycles_h, 1),
            "llm_errors_per_h": None if errs_h is None else round(errs_h, 1),
            "log_mb": round(scan["size"] / 1048576, 1),
            "log_last_write": iso(scan["mtime"]),
            "baseline": scan["baseline"],
            "anomalies": [
                {k: v for k, v in a.items() if k not in ("ts", "flywheel")} for a in anomalies
            ],
        }

    # pipeline-level
    pipeline_anoms = []
    for t in broken_timers():
        pipeline_anoms.append(
            alert("pipeline", "timer_never_fires", f"{t} has no next elapse (bad OnCalendar?)")
        )
    for name, rel in OTHER_LOGS.items():
        p = AII / rel
        if p.exists() and p.stat().st_size > LOG_MAX_MB * 1024 * 1024:
            act = rotate_log(p, dry) if (remediate or dry) else None
            pipeline_anoms.append(
                alert("pipeline", "log_oversize", f"{rel} {p.stat().st_size / 1048576:.0f}MB", act)
            )
    feeder = unit_show("aii-feeder")
    if feeder.get("ActiveState") != "active":
        pipeline_anoms.append(
            alert("pipeline", "feeder_dead", f"aii-feeder ActiveState={feeder.get('ActiveState')}")
        )
    stage = stage_summary()
    if db_err:
        pipeline_anoms.append(alert("pipeline", "db_unreachable", db_err))

    state["last_run"] = t_now
    status = {
        "generated_at": iso(t_now),
        "window_minutes": None if window_h is None else round(window_h * 60, 1),
        "thresholds": {
            "hot_cycles_per_h": HOT_CYCLES_PER_H,
            "llm_err_per_h": LLM_ERR_PER_H,
            "log_stale_h": LOG_STALE_H,
            "log_max_mb": LOG_MAX_MB,
        },
        "flywheels": flywheels,
        "pipeline": {
            "feeder_active": feeder.get("ActiveState"),
            "staged_md": stage,
            "anomalies": [
                {k: v for k, v in a.items() if k not in ("ts", "flywheel")} for a in pipeline_anoms
            ],
        },
        "dry_run": dry,
    }
    if not dry:
        tmp = STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
        tmp.replace(STATUS)
        STATE.write_text(json.dumps(state))
        if alerts:
            with ALERTS.open("a", encoding="utf-8") as fh:
                for a in alerts:
                    fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {n: (f["state"], [a["anomaly"] for a in f["anomalies"]]) for n, f in flywheels.items()},
            ensure_ascii=False,
        )
    )
    print(json.dumps({"pipeline": [a["anomaly"] for a in pipeline_anoms]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
