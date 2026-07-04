"""程序化飞轮 状态 + 控制(2026-07-04 三飞轮架构: econ_zh合并版全语言 / math_prog B范式 / misc其它).
飞轮监控 /home/soffy/books/MD/{经济学,中文数学,英文数学,其它} 的 *.md, 连续处理+入库(A仓).
运行检测: 飞轮 runner 进程(<runner>.sh)cmdline. 入库数: DB ku_onto(按 channel substrate 前缀集合).
控制: start(启 runner)/stop(killpg). 归一: ROOT=stratum/aii(原 /AII 已并入 stratum)。

★旧4飞轮架构(econ/econ_zh/math_en/math_zh)已废弃: econ(英文经济)并入 econ_zh(合并版,
吃全语言); math_en/math_zh(旧LLM讲透)被 math_prog(程序抠陈述+证明, 0LLM)取代; 新增
misc(其它学科, 心理/哲学/科普等). 旧 runner 脚本文件仍在磁盘但对应 systemd 服务已删除,
不再在此暴露, 避免前端误触发孤儿进程.
"""

import os
import re
import json
import glob
import signal
import hashlib
import subprocess
from pathlib import Path

import asyncpg
from fastapi import APIRouter, HTTPException

router = APIRouter()
ROOT = Path("/home/soffy/projects/stratum/aii")
MD_BASE = Path("/home/soffy/books/MD")
DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")

# 已知书名→substrate(与 econ_discover_all.py 的 KNOWN 一致), 其余 <prefix>_<md5前10>
_KNOWN = {
    "Principles of Economics 10e": "mankiw_principles_econ_10e",
    "Principles of Microeconomics The Way We": "microecon_en_full_v2",
    "Principles of Microeconomics The Way We Live": "microecon_en_full_v2",
}


def _is_chinese(text: str) -> bool:
    samp = text[:120000]
    zh = len(re.findall(r"[一-鿿]", samp))
    en = len(re.findall(r"[A-Za-z]", samp))
    return zh > en


CHANNELS = {
    "econ_zh": {
        "name": "程序化经济学(合并版,全语言)",
        "folder": ["经济学"],
        "needs_key": True,
        "key_id": "econ_zh",
        "runner": "econ_flywheel_zh_run.sh",
        "prefixes": ["econ_zh_", "econ_en_"],
        "by_lang": True,
        "known": ["mankiw_principles_econ_10e", "microecon_en_full_v2"],
        "log": ROOT / "econ_pipeline/flywheel_zh.log",
    },
    "math_prog": {
        "name": "程序化数学(B范式, 程序抠陈述+证明, 0 LLM)",
        "folder": ["中文数学", "英文数学"],
        "needs_key": False,  # 0-LLM 设计, 不需要 NIM key
        "key_id": None,
        "runner": "math_flywheel_prog_run.sh",
        "prefixes": ["math_prog_"],
        "by_lang": False,
        "known": [],
        "log": ROOT / "math_pipeline/flywheel_prog.log",
    },
    "misc": {
        "name": "程序化其它(心理/哲学/科普等有章节教材)",
        "folder": ["其它"],
        "needs_key": True,
        "key_id": "econ",  # ★复用 econ 的 key(见 misc_flywheel.sh), 不是独立配置项
        "runner": "misc_flywheel_run.sh",
        "prefixes": ["misc_zh_", "misc_en_"],
        "by_lang": True,
        "known": [],
        "log": ROOT / "misc_pipeline/flywheel_misc.log",
    },
}


def _keys() -> dict:
    try:
        return json.loads((ROOT / ".pipeline_keys.json").read_text())
    except Exception:
        return {}


def _resolve(c: dict, stem: str, text: str) -> str:
    """按 channel 的真实 substrate 生成规则解析(须与各飞轮 discover 脚本一致, 见 econ_discover_all.py
    / misc_discover.py 的 _sid() / math_flywheel_prog.sh 的 md5(stem)前10)."""
    if stem in _KNOWN:
        return _KNOWN[stem]
    h = hashlib.md5(stem.encode("utf-8")).hexdigest()[:10]
    if not c["by_lang"]:
        return f"{c['prefixes'][0]}{h}"
    pref = c["prefixes"][0] if _is_chinese(text) else c["prefixes"][1]
    return f"{pref}{h}"


def _running_pids(cid: str) -> list[int]:
    runner = CHANNELS[cid]["runner"]
    pids = []
    for cl in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            data = open(cl, "rb").read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except Exception:
            continue
        if runner in data:
            try:
                pids.append(int(cl.split("/")[2]))
            except Exception:
                pass
    return pids


def _last_log(p: Path) -> str:
    try:
        lines = [l.strip() for l in p.read_text(errors="replace").splitlines() if l.strip()]
        for l in reversed(lines):
            if not any(x in l for x in ("INFO", "WARNING", "huggingface", "tokenizer")):
                return l[:160]
        return lines[-1][:160] if lines else ""
    except Exception:
        return ""


@router.get("/pipelines")
async def list_pipelines():
    conn = await asyncpg.connect(DSN)
    try:
        out = []
        for cid, c in CHANNELS.items():
            folders = [MD_BASE / f for f in c["folder"]]
            books = []
            # 频道总KU: 按全部 substrate prefix(可能横跨中英两种) + 已知自定义名
            like_clauses = " OR ".join(
                f"substrate_id LIKE ${i + 1}" for i in range(len(c["prefixes"]))
            )
            total_ku = (
                await conn.fetchval(
                    f"SELECT count(*) FROM aii.ku_onto WHERE ({like_clauses}) "
                    f"OR substrate_id = ANY(${len(c['prefixes']) + 1}::text[])",
                    *[p + "%" for p in c["prefixes"]],
                    c.get("known", []),
                )
                or 0
            )
            for folder in folders:
                for md in sorted(glob.glob(str(folder / "*.md"))):
                    stem = Path(md).stem
                    try:
                        text = open(md, encoding="utf-8", errors="replace").read()
                    except Exception:
                        continue
                    sub = _resolve(c, stem, text)
                    ku = (
                        await conn.fetchval(
                            "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sub
                        )
                        or 0
                    )
                    books.append(
                        {"title": stem, "substrate": sub, "ku": ku, "in_db": ku > 0, "done": ku > 0}
                    )
            has_key = (not c["needs_key"]) or bool(_keys().get(c["key_id"]))
            out.append(
                {
                    "id": cid,
                    "name": c["name"],
                    "folder": " + ".join(str(f) for f in folders),
                    "running": len(_running_pids(cid)) > 0,
                    "has_key": has_key,
                    "books_total": len(books),
                    "books_done": sum(1 for b in books if b["done"]),
                    "ku_count": total_ku,
                    "books": books,
                    "last_log": _last_log(c["log"]),
                }
            )
        return {"status": "ok", "data": out}
    finally:
        await conn.close()


@router.post("/pipelines/{cid}/start")
async def start_pipeline(cid: str):
    c = CHANNELS.get(cid)
    if not c:
        raise HTTPException(404, "unknown channel")
    if _running_pids(cid):
        return {"status": "ok", "msg": "already running"}
    if c["needs_key"] and not _keys().get(c["key_id"]):
        raise HTTPException(400, f"通道 {cid} 未配置 NIM key")
    c["log"].parent.mkdir(parents=True, exist_ok=True)
    logf = open(c["log"], "ab")
    subprocess.Popen(
        ["bash", f"scripts/{c['runner']}"],
        cwd=str(ROOT),
        env={**os.environ, "DATABASE_URL": DSN},
        stdout=logf,
        stderr=logf,
        start_new_session=True,
    )
    return {"status": "ok", "msg": f"{cid} flywheel started"}


@router.post("/pipelines/{cid}/stop")
async def stop_pipeline(cid: str):
    if cid not in CHANNELS:
        raise HTTPException(404, "unknown channel")
    killed = []
    for pid in _running_pids(cid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            killed.append(pid)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(pid)
            except Exception:
                pass
    return {"status": "ok", "msg": f"stopped {len(killed)} proc", "killed": killed}
