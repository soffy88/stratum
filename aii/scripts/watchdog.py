#!/usr/bin/env python3
"""AII 看门狗 — 结构化健康报告 (P2a: 只观察, 不自愈)。

每5分钟由 systemd timer 跑一次, 原子写 aii/watchdog/health_report.json:
  - /api/health/watchdog 直接读这个文件对外暴露(零耦合)
  - PIPELINE_STATUS.md 的 "🚨 Needs Human" 段由它自动重写

本阶段(P2a)刻意零自动修复动作——先跑3天观察窗口, 确认检查项不误报, 再在 P2b 逐个接
修复动作(见 rippling-splashing-spring.md)。这些检查里"入库新鲜度>24h"这条, 正是能在
2026-07-09 那次 PG 持久化猝死22小时之前就报警的哨兵。

设计原则: 每个检查独立 try/except(一个炸不影响整张报告); "空闲≠故障"(飞轮没书可读是
正常, 只有'该出料却卡住'才告警); infra 类降级(GPU Xid79)只报一次不当严重故障。
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_DIR = ROOT / "watchdog"
REPORT = WATCHDOG_DIR / "health_report.json"
STATE = WATCHDOG_DIR / "state.json"
PIPELINE_STATUS = ROOT / "PIPELINE_STATUS.md"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "aii" / ".env", override=False)
except Exception:
    pass

DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
AII_EMBED_URL = os.getenv("AII_EMBED_URL", "http://100.68.226.13:8102")
SHARED_INBOX = Path("/home/soffy/shared/stratum-to-aii")

FLYWHEELS = {
    "aii-flywheel-econ-zh": {
        "prefixes": ["econ_zh_", "econ_en_"],
        "booklist": ROOT / "econ_pipeline/flywheel_zh_booklist.txt",
    },
    "aii-flywheel-misc": {
        "prefixes": ["misc_zh_", "misc_en_"],
        "booklist": ROOT / "misc_pipeline/flywheel_misc_booklist.txt",
    },
    "aii-flywheel-math-prog": {"prefixes": ["math_prog_"], "booklist": None},
    "aii-flywheel-advmath": {"prefixes": ["advmath_zh_", "advmath_en_"], "booklist": None},
}

SEV = {"info": 0, "warn": 1, "crit": 2}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def _sh(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 255, str(e)


# ── individual checks (each returns a list of check dicts) ─────────────────────


def check_services() -> list[dict]:
    out = []
    rc, txt = _sh(["systemctl", "--user", "list-unit-files", "aii-*"])
    for line in txt.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].endswith(".service"):
            continue
        unit, enabled_state = parts[0], parts[1]
        if enabled_state != "enabled":
            continue  # disabled 服务(aii-embed已迁笔记本/ocr-daemon)不算异常
        active_rc, _ = _sh(["systemctl", "--user", "is-active", "--quiet", unit])
        if active_rc == 0:
            out.append(
                {"name": f"svc:{unit}", "status": "active", "severity": "info", "detail": ""}
            )
        else:
            out.append(
                {
                    "name": f"svc:{unit}",
                    "status": "inactive",
                    "severity": "crit",
                    "detail": f"enabled但未运行 → systemctl --user start {unit}",
                }
            )
    if not out:
        out.append(
            {
                "name": "svc:*",
                "status": "unknown",
                "severity": "warn",
                "detail": "无法枚举 aii-* units",
            }
        )
    return out


def check_stratum_sl(state: dict) -> list[dict]:
    rc, txt = _sh(["docker", "inspect", "-f", "{{.State.Status}}|{{.RestartCount}}", "stratum-sl"])
    if rc != 0:
        return [
            {
                "name": "stratum-sl",
                "status": "missing",
                "severity": "crit",
                "detail": "容器不存在/无法inspect",
            }
        ]
    status, _, restarts = txt.strip().partition("|")
    restarts = int(restarts or 0)
    prev = state.get("stratum_sl_restarts")
    state["stratum_sl_restarts"] = restarts
    if status != "running":
        return [
            {
                "name": "stratum-sl",
                "status": status,
                "severity": "crit",
                "detail": f"容器状态={status}",
            }
        ]
    delta = (restarts - prev) if isinstance(prev, int) else 0
    if delta >= 3:
        return [
            {
                "name": "stratum-sl",
                "status": "crash-loop",
                "severity": "crit",
                "detail": f"本检查周期内重启 {delta} 次(累计{restarts}) — 疑似崩溃环",
            }
        ]
    return [
        {
            "name": "stratum-sl",
            "status": "running",
            "severity": "info",
            "detail": f"restarts累计={restarts}",
        }
    ]


async def _fetch(conn_sql: list[tuple[str, tuple]]) -> list:
    import asyncpg

    conn = await asyncpg.connect(DSN, timeout=10)
    try:
        return [await conn.fetchval(sql, *args) for sql, args in conn_sql]
    finally:
        await conn.close()


def check_ingestion_and_flywheels(state: dict) -> list[dict]:
    """入库新鲜度 + 隔离增长 + 各飞轮产出心跳(靠真实DB, 空闲≠故障)。"""
    out = []
    try:
        queries = [
            ("SELECT max(created_at) FROM stratum.substrates", ()),
            ("SELECT count(*) FROM stratum.ingest_quarantine", ()),
            ("SELECT count(*) FROM stratum.source_subscriptions WHERE status='active'", ()),
        ]
        # 每个飞轮: 该前缀最新KU时间
        fw_keys = list(FLYWHEELS.keys())
        for name in fw_keys:
            prefs = FLYWHEELS[name]["prefixes"]
            like = " OR ".join(f"substrate_id LIKE ${i + 1}" for i in range(len(prefs)))
            queries.append(
                (
                    f"SELECT max(created_at) FROM aii.ku_onto WHERE {like}",
                    tuple(p + "%" for p in prefs),
                )
            )
        results = asyncio.run(_fetch(queries))
    except Exception as e:
        return [
            {
                "name": "db-checks",
                "status": "error",
                "severity": "warn",
                "detail": f"DB查询失败: {str(e)[:80]}",
            }
        ]

    now = datetime.now(timezone.utc)
    newest_sub, quar_count, active_subs = results[0], results[1], results[2]

    # 入库新鲜度(哨兵: 22小时PG猝死本可在此报警)
    if newest_sub is not None:
        age_h = (now - newest_sub).total_seconds() / 3600
        if age_h > 24 and (active_subs or 0) > 0:
            out.append(
                {
                    "name": "ingestion-freshness",
                    "status": "stale",
                    "severity": "crit",
                    "detail": f"最新substrate已 {age_h:.1f}h 前, 但有{active_subs}个活跃订阅 — 入库可能已停摆",
                }
            )
        elif age_h > 6 and (active_subs or 0) > 0:
            out.append(
                {
                    "name": "ingestion-freshness",
                    "status": "aging",
                    "severity": "warn",
                    "detail": f"最新substrate {age_h:.1f}h 前(>6h留意)",
                }
            )
        else:
            out.append(
                {
                    "name": "ingestion-freshness",
                    "status": "fresh",
                    "severity": "info",
                    "detail": f"最新substrate {age_h:.1f}h 前",
                }
            )

    # 隔离增长
    prev_quar = state.get("quarantine_count")
    state["quarantine_count"] = quar_count
    if isinstance(prev_quar, int) and (quar_count - prev_quar) > 5:
        out.append(
            {
                "name": "quarantine-growth",
                "status": "growing",
                "severity": "warn",
                "detail": f"隔离项周期内新增 {quar_count - prev_quar}(累计{quar_count})",
            }
        )
    else:
        out.append(
            {
                "name": "quarantine",
                "status": "ok",
                "severity": "info",
                "detail": f"隔离累计={quar_count}",
            }
        )

    # 各飞轮心跳: active + (近产出 或 无书可读=空闲正常)
    for i, name in enumerate(fw_keys):
        latest_ku = results[3 + i]
        active_rc, _ = _sh(["systemctl", "--user", "is-active", "--quiet", name])
        if active_rc != 0:
            continue  # 服务状态已在 check_services 覆盖
        booklist = FLYWHEELS[name]["booklist"]
        booklist_len = 0
        if booklist and booklist.exists():
            try:
                booklist_len = len([l for l in booklist.read_text().splitlines() if l.strip()])
            except Exception:
                booklist_len = 0
        ku_age_h = ((now - latest_ku).total_seconds() / 3600) if latest_ku else 9999
        if booklist_len == 0:
            out.append(
                {
                    "name": f"flywheel:{name}",
                    "status": "idle",
                    "severity": "info",
                    "detail": f"无新书(空闲, 正常); 最近KU {ku_age_h:.1f}h前",
                }
            )
        elif ku_age_h > 2:
            out.append(
                {
                    "name": f"flywheel:{name}",
                    "status": "stuck",
                    "severity": "warn",
                    "detail": f"书单{booklist_len}本待处理但 {ku_age_h:.1f}h 无新KU — 疑似卡住",
                }
            )
        else:
            out.append(
                {
                    "name": f"flywheel:{name}",
                    "status": "producing",
                    "severity": "info",
                    "detail": f"书单{booklist_len}本; 最近KU {ku_age_h:.1f}h前",
                }
            )
    return out


def check_embed() -> list[dict]:
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{AII_EMBED_URL}/embed",
            data=json.dumps({"texts": ["体检"]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            # urlopen raises on 4xx/5xx, so reaching here means 2xx.
            has_vec = b"embedding" in resp.read(400).lower()
        detail = "真实/embed调用200" + ("" if has_vec else "(200但响应无embeddings字段)")
        return [{"name": "aii-embed", "status": "ok", "severity": "info", "detail": detail}]
    except Exception as e:
        return [
            {
                "name": "aii-embed",
                "status": "unreachable",
                "severity": "warn",
                "detail": f"embed服务不可达: {str(e)[:80]}(嵌入会退回本机CPU兜底)",
            }
        ]


def check_gpu() -> list[dict]:
    rc, txt = _sh(["nvidia-smi", "--query-gpu=name,memory.used", "--format=csv,noheader"])
    if rc == 0 and txt.strip():
        return [
            {
                "name": "gpu",
                "status": "ok",
                "severity": "info",
                "detail": txt.strip().split(chr(10))[0],
            }
        ]
    return [
        {
            "name": "gpu",
            "status": "absent",
            "severity": "info",
            "detail": "nvidia-smi无设备(Xid79间歇故障, 已知; OCR/VLM降级不重试)",
        }
    ]


def check_backlog() -> list[dict]:
    try:
        mds = list(SHARED_INBOX.glob("*.md"))
        if not mds:
            return [
                {
                    "name": "inbox-backlog",
                    "status": "empty",
                    "severity": "info",
                    "detail": "收件箱空",
                }
            ]
        oldest = min(m.stat().st_mtime for m in mds)
        age_h = (time.time() - oldest) / 3600
        sev = "warn" if age_h > 24 else "info"
        return [
            {
                "name": "inbox-backlog",
                "status": "backlog" if age_h > 24 else "ok",
                "severity": sev,
                "detail": f"{len(mds)}个MD待分类, 最老 {age_h:.1f}h(>24h说明分类/飞轮没消化)",
            }
        ]
    except Exception as e:
        return [
            {"name": "inbox-backlog", "status": "error", "severity": "info", "detail": str(e)[:60]}
        ]


# ── assemble + write ──────────────────────────────────────────────────────────


def build_report(state: dict) -> dict:
    checks: list[dict] = []
    for fn in (check_services, check_gpu, check_embed, check_backlog):
        try:
            checks += fn()
        except Exception as e:
            checks.append(
                {"name": fn.__name__, "status": "error", "severity": "warn", "detail": str(e)[:80]}
            )
    try:
        checks += check_stratum_sl(state)
    except Exception as e:
        checks.append(
            {"name": "stratum-sl", "status": "error", "severity": "warn", "detail": str(e)[:80]}
        )
    try:
        checks += check_ingestion_and_flywheels(state)
    except Exception as e:
        checks.append(
            {"name": "db-checks", "status": "error", "severity": "warn", "detail": str(e)[:80]}
        )

    worst = max((SEV.get(c["severity"], 0) for c in checks), default=0)
    overall = ["ok", "degraded", "critical"][worst]
    needs_human = [f"{c['name']}: {c['detail']}" for c in checks if c["severity"] == "crit"]
    return {
        "generated_at": _now(),
        "overall": overall,
        "checks": checks,
        "needs_human": needs_human,
        "mode": "observe-only (P2a, no auto-remediation)",
    }


def write_report(report: dict) -> None:
    WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    tmp.replace(REPORT)


def update_pipeline_status(report: dict) -> None:
    """把 needs_human 自动写进 PIPELINE_STATUS.md 的标记段(不存在则追加)。"""
    if not PIPELINE_STATUS.exists():
        return
    START, END = "<!-- WATCHDOG:START -->", "<!-- WATCHDOG:END -->"
    lines = [f"{START}", f"## 🚨 Needs Human (看门狗自动维护, {report['generated_at'][:19]}Z)", ""]
    if report["needs_human"]:
        lines += [f"- {x}" for x in report["needs_human"]]
    else:
        lines.append(f"- ✅ 无严重项 (overall={report['overall']})")
    lines += ["", END]
    block = "\n".join(lines)
    txt = PIPELINE_STATUS.read_text(encoding="utf-8", errors="replace")
    if START in txt and END in txt:
        pre = txt[: txt.index(START)]
        post = txt[txt.index(END) + len(END) :]
        txt = pre + block + post
    else:
        txt = txt.rstrip() + "\n\n" + block + "\n"
    tmp = PIPELINE_STATUS.with_suffix(".md.tmp")
    tmp.write_text(txt, encoding="utf-8")
    tmp.replace(PIPELINE_STATUS)


def main() -> int:
    state = _load_state()
    report = build_report(state)
    write_report(report)
    _save_state(state)
    try:
        update_pipeline_status(report)
    except Exception:
        pass
    if "--human" in sys.argv:
        print(f"overall={report['overall']}")
        for c in report["checks"]:
            mark = {"info": "  ", "warn": "⚠ ", "crit": "🚨"}.get(c["severity"], "  ")
            print(f"{mark} [{c['status']}] {c['name']}: {c['detail']}")
        # 交互/监控用: 退出码反映健康(0绿/1降级/2严重)。
        return (
            2 if report["overall"] == "critical" else (1 if report["overall"] == "degraded" else 0)
        )
    # systemd 服务(默认): 只要成功产出报告就退0——"degraded/critical"是健康结论, 不是运行失败,
    # 否则 Type=oneshot 会把每次降级都标成服务failed。健康严重度在报告文件里, 不在退出码。
    return 0


if __name__ == "__main__":
    sys.exit(main())
