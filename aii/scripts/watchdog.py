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

# ── P2b 自愈相关 ──
ACTIONS_LOG = WATCHDOG_DIR / "health_actions.jsonl"  # append-only 修复动作审计
ACTION_STATE = WATCHDOG_DIR / "action_state.json"  # 限速用: {action_key: [ts,...]}
MAINTENANCE_FLAG = WATCHDOG_DIR / "MAINTENANCE"  # 内容必须是ISO过期时间(裸flag被无视)
RATE_PER_HOUR = 1  # 同一动作+目标 ≤1次/小时
RATE_PER_DAY = 3  # ≤3次/天, 超过则升级人工(不再自动)

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


def check_stuck_pulls() -> list[dict]:
    """卡死的拉料/分类进程(正常一轮<3min; >900s=可疑, 源自真实9h19m卡死教训)。"""
    rc, txt = _sh(["ps", "-eo", "pid,etimes,args", "--no-headers"])
    stuck = []
    for line in txt.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid, etimes, args = parts
        try:
            et = int(etimes)
        except ValueError:
            continue
        if et > 900 and ("pull_ingest.sh" in args or "classify_md.py" in args):
            stuck.append({"pid": int(pid), "etimes": et, "args": args[:80]})
    if not stuck:
        return [
            {"name": "stuck-pulls", "status": "ok", "severity": "info", "detail": "无卡死拉料进程"}
        ]
    return [
        {
            "name": "stuck-pull",
            "status": "stuck",
            "severity": "warn",
            "pid": s["pid"],
            "detail": f"pid={s['pid']} 已运行 {s['etimes']}s: {s['args']}",
        }
        for s in stuck
    ]


# ── assemble + write ──────────────────────────────────────────────────────────


def build_report(state: dict) -> dict:
    checks: list[dict] = []
    for fn in (check_services, check_gpu, check_embed, check_backlog, check_stuck_pulls):
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


# ── P2b 自愈层(默认 WATCHDOG_REMEDIATE=0: 只决策+审计"本会做什么", 不执行)────────────
#
# 设计要点(压力测试 H5):
#   - 关闭时也跑决策逻辑并把意图写进 health_actions.jsonl —— 观察期就能验证修复逻辑对不对,
#     再翻开关, 绝不"检查+动作同天上线"。
#   - 崩溃环不无脑重启(会给 Restart=always 的循环加油): 只隔离肇事条目, 隔离即断环, 不追加重启。
#   - 维护 flag 必须内嵌 ISO 过期时间; 无过期/解析失败一律无视(裸 flag 被遗忘=看门狗永久失效,
#     等于 8.5h 静默零产出事故换装重演)。
#   - 每动作限速(≤1/hr/目标, ≤3/天则升级人工)。


def _load_action_state() -> dict:
    try:
        return json.loads(ACTION_STATE.read_text())
    except Exception:
        return {}


def _save_action_state(astate: dict) -> None:
    WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ACTION_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(astate, indent=2))
    tmp.replace(ACTION_STATE)


def _audit(rec: dict) -> None:
    WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _now(), **rec}
    with open(ACTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _maintenance_active() -> tuple[bool, str]:
    """维护模式: flag 文件内容须是未来的 ISO 时间; 过期/无法解析一律当未激活(并留痕)。"""
    if not MAINTENANCE_FLAG.exists():
        return False, ""
    content = ""
    try:
        content = MAINTENANCE_FLAG.read_text().strip()
        expiry = datetime.fromisoformat(content)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < expiry:
            return True, content
        _audit({"event": "maintenance-expired-ignored", "expiry": content})
        return False, ""
    except Exception:
        # 无有效过期时间 → 拒绝把看门狗永久关掉, 无视这个 flag 并告警。
        _audit({"event": "maintenance-flag-invalid-ignored", "content": content[:60]})
        return False, ""


def _rate_ok(key: str, astate: dict) -> bool:
    now = time.time()
    hist = [t for t in astate.get(key, []) if now - t < 86400]
    astate[key] = hist
    return sum(1 for t in hist if now - t < 3600) < RATE_PER_HOUR and len(hist) < RATE_PER_DAY


def _record_action(key: str, astate: dict) -> None:
    astate.setdefault(key, []).append(time.time())


def _actions_for(report: dict) -> list[dict]:
    """从 checks 推出待执行修复动作。"""
    acts = []
    for c in report["checks"]:
        if c["name"].startswith("svc:") and c["status"] == "inactive":
            acts.append({"action": "restart-service", "target": c["name"][4:], "why": c["detail"]})
        elif c["name"] == "stratum-sl" and c["status"] == "crash-loop":
            acts.append({"action": "quarantine-poison", "target": "stratum-sl", "why": c["detail"]})
        elif c["name"] == "stuck-pull" and c.get("pid"):
            acts.append({"action": "kill-process", "target": str(c["pid"]), "why": c["detail"]})
    return acts


def _quarantine_crash_loop_item() -> tuple[bool, str]:
    """崩溃环止损: 把最近崩溃最多、尚未隔离的入库条目写进 stratum.ingest_quarantine(断环)。"""

    async def _run():
        import asyncpg

        conn = await asyncpg.connect(DSN, timeout=10)
        try:
            row = await conn.fetchrow(
                "SELECT item_key, source_type, count(*) n FROM stratum.ingest_attempts "
                "WHERE outcome IN ('crashed','timeout') AND attempted_at > NOW() - interval '30 min' "
                "AND item_key NOT IN (SELECT item_key FROM stratum.ingest_quarantine) "
                "GROUP BY item_key, source_type ORDER BY n DESC LIMIT 1"
            )
            if not row:
                return False, "无未隔离的崩溃条目可锁定"
            await conn.execute(
                "INSERT INTO stratum.ingest_quarantine (item_key, source_type, reason, fail_count) "
                "VALUES ($1,$2,$3,$4) ON CONFLICT (item_key) DO NOTHING",
                row["item_key"],
                row["source_type"],
                f"watchdog crash-loop auto-quarantine ({row['n']} crashes/30min)",
                row["n"],
            )
            return True, f"已隔离肇事条目 {row['item_key']} ({row['n']}次崩溃)"
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    except Exception as e:
        return False, f"隔离失败: {str(e)[:80]}"


def _execute(action: str, target: str) -> tuple[bool, str]:
    if action == "restart-service":
        rc, out = _sh(["systemctl", "--user", "start", target], timeout=30)
        return rc == 0, out[:200] or "started"
    if action == "kill-process":
        rc, out = _sh(["kill", "-9", target])
        return rc == 0, out[:120] or "killed"
    if action == "quarantine-poison":
        return _quarantine_crash_loop_item()
    return False, f"unknown action {action}"


def remediate(report: dict, astate: dict) -> None:
    remediate_on = os.getenv("WATCHDOG_REMEDIATE", "0") == "1"
    maint, maint_until = _maintenance_active()
    for a in _actions_for(report):
        key = f"{a['action']}:{a['target']}"
        base = {"action": a["action"], "target": a["target"], "why": a["why"]}
        if maint:
            _audit({**base, "executed": False, "blocked": f"maintenance until {maint_until}"})
            continue
        if not _rate_ok(key, astate):
            _audit(
                {**base, "executed": False, "blocked": "rate-limited (≤1/hr, ≤3/day → 升级人工)"}
            )
            continue
        if not remediate_on:
            _audit({**base, "executed": False, "blocked": "observe-only (WATCHDOG_REMEDIATE=0)"})
            continue
        ok, detail = _execute(a["action"], a["target"])
        _record_action(key, astate)
        _audit({**base, "executed": True, "result": ("ok" if ok else "failed") + ": " + detail})


def main() -> int:
    state = _load_state()
    report = build_report(state)
    write_report(report)
    _save_state(state)
    try:
        update_pipeline_status(report)
    except Exception:
        pass
    try:
        astate = _load_action_state()
        remediate(report, astate)
        _save_action_state(astate)
    except Exception as e:
        _audit({"event": "remediate-crashed", "error": str(e)[:120]})
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
