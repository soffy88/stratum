#!/usr/bin/env python3
"""断料主动找料协调器 — watchdog 供料不足时调用。

动作链(每步独立 flock/限速, 一个失败不阻塞其余):
  1. OAPEN 按需一轮(不等 6h timer): 10 主题 × 10 本开放教材 PDF → books/{Economic,数学}
  2. veya headless 异步派活(≥6h 限速, nohup 不阻塞): 让 veya agent 联网找教材源并下载,
     结果写 watchdog/veya_find_books_result.json, 由后续轮次读回记录
  3. 每轮先读回 veya 上轮结果 → source_hunt.json 历史

用法:
  .venv/bin/python scripts/source_hunt.py            # 全链(OAPEN + veya 派活 + 读回结果)
  .venv/bin/python scripts/source_hunt.py --oapen-only
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "watchdog" / "source_hunt.json"
STATE = ROOT / "watchdog" / "source_hunt_state.json"
VEYA_DIR = Path("/data/soffy/projects/veya")
VEYA_RESULT = ROOT / "watchdog" / "veya_find_books_result.json"
VEYA_CMD = ROOT / "watchdog" / "veya_find_books_cmd.json"
VEYA_LOG = ROOT / "watchdog" / "veya_hunt.log"
VEYA_MIN_INTERVAL_S = 6 * 3600  # veya 找料任务 ≥6h 一次(重任务)

VEYA_PYTHONPATH = (
    f"{VEYA_DIR}/platform/3O:{VEYA_DIR}/platform/3O/obase:{VEYA_DIR}/platform/3O/oskill:"
    f"{VEYA_DIR}/platform/3O/oprim:{VEYA_DIR}/platform/3O/oservi:{VEYA_DIR}/platform/3O/omodul"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def _log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    hist = []
    if LOG.exists():
        try:
            hist = json.loads(LOG.read_text())
        except Exception:
            pass
    hist.append({"ts": _now(), **entry})
    LOG.write_text(json.dumps(hist[-50:], ensure_ascii=False, indent=2))


def check_veya_result() -> None:
    """读回 veya 上轮结果 → 记录 + 删除(避免重复报告)。"""
    if not VEYA_RESULT.exists():
        return
    try:
        data = json.loads(VEYA_RESULT.read_text())
        _log({"stage": "veya", "result": data})
        VEYA_RESULT.unlink()
        print(f"[source_hunt] veya 结果: {json.dumps(data, ensure_ascii=False)[:200]}")
    except Exception as e:
        _log({"stage": "veya", "result_read_error": str(e)[:80]})


def run_oapen() -> None:
    """OAPEN 按需一轮 — 异步派发(flock 命令包裹: timer/其它实例在跑则跳过, 不排队)。"""
    lock = ROOT / ".locks" / "oapen_on_demand.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    logf = ROOT / "watchdog" / "oapen_ondemand.log"
    logf.parent.mkdir(parents=True, exist_ok=True)
    cmd = (
        f"flock -n {lock} sh -c 'nohup {ROOT / '.venv/bin/python'} oapen_fetch.py --do "
        f"--max 10 >> {logf} 2>&1 &'"
    )
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        _log({"stage": "oapen", "skipped": "oapen 已在跑(timer/手动), flock 未获得"})
        print("[source_hunt] OAPEN 已在跑, 跳过")
    else:
        _log({"stage": "oapen", "started": True})
        print("[source_hunt] OAPEN 按需轮已派发(异步)")


def run_veya() -> None:
    """veya headless 异步找料(≥6h 限速; 已有 headless 在跑则跳过; nohup 不阻塞本进程)。"""
    st = _load_state()
    last = st.get("veya_last")
    if last and time.time() - last < VEYA_MIN_INTERVAL_S:
        mins = int((time.time() - last) // 60)
        _log({"stage": "veya", "skipped": f"距上次 {mins}min < 6h 限速"})
        return
    r = subprocess.run(["pgrep", "-f", "cli.headless"], capture_output=True, text=True)
    if r.stdout.strip():
        _log({"stage": "veya", "skipped": "veya headless 已在跑"})
        return
    cmd = {
        "text": (
            "你是AII知识飞轮系统的教材供料员。任务: 为中文经济学与数学知识库补充可下载的开放教材PDF。"
            "请:(1)用你能用的网络能力/工具搜索开放教材(如 OAPEN library.oapen.org 的 rest/search API、"
            "Project Gutenberg、openstax、其他你可达的开放书源)的主题: microeconomics, macroeconomics, "
            "linear algebra, calculus, probability theory, differential equations;"
            "(2)对找到的真PDF(可直连下载)用 curl 下载到 /home/soffy/books/Economic/ 或 /home/soffy/books/数学/, "
            "优先小文件(<5MB), 最多下载 3 本;"
            "(3)结束时输出JSON: {\"downloaded\": [\"文件名\"], \"failed\": [\"原因\"], \"sources_used\": [\"源名\"]}。"
            "若无法下载, 输出 {\"downloaded\": [], \"failed\": [\"具体原因\"], \"sources_used\": [\"尝试过的源\"]}。"
        )
    }
    VEYA_CMD.write_text(json.dumps(cmd, ensure_ascii=False))
    env = dict(os.environ, PYTHONPATH=VEYA_PYTHONPATH)
    logf = open(VEYA_LOG, "a")
    try:
        subprocess.Popen(
            ["nohup", str(VEYA_DIR / "venv/bin/python"), "-m", "cli.headless",
             "--input", str(VEYA_CMD), "--output", str(VEYA_RESULT)],
            cwd=VEYA_DIR, env=env, stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        st["veya_last"] = time.time()
        _save_state(st)
        _log({"stage": "veya", "started": True})
        print("[source_hunt] veya 找料任务已派发(异步)")
    except Exception as e:
        _log({"stage": "veya", "start_failed": str(e)[:80]})


def snapshot() -> None:
    pools = {}
    for name, d in (
        ("经济", "/home/soffy/books/MD/经济学"),
        ("中文数学", "/home/soffy/books/MD/中文数学"),
        ("英文数学", "/home/soffy/books/MD/英文数学"),
        ("其它", "/home/soffy/books/MD/其它"),
    ):
        p = Path(d)
        pools[name] = len(list(p.glob("*.md"))) if p.exists() else 0
    _log({"stage": "snapshot", "books_md_pools": pools})


def main() -> int:
    check_veya_result()
    if len(sys.argv) > 1 and sys.argv[1] == "--oapen-only":
        run_oapen()
        return 0
    run_oapen()
    run_veya()
    snapshot()
    return 0


if __name__ == "__main__":
    sys.exit(main())
