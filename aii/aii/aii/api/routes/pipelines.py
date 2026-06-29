"""程序化飞轮 状态 + 控制(4飞轮: 英文经济 econ / 中文经济 econ_zh / 英文数学 math_en / 中文数学 math_zh).
飞轮监控 /home/soffy/books/MD/{经济学,英文数学,中文数学} 的 *.md, 连续处理+入库(A仓).
运行检测: 飞轮 runner 进程(<runner>.sh)cmdline. 入库数: DB ku_onto(按 channel substrate 集合).
控制: start(启 runner)/stop(killpg). 归一: ROOT=stratum/aii(原 /AII 已并入 stratum)。
"""
import os
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

# 已知书名→substrate(与 *_discover_*.py 的 KNOWN 一致),其余 <prefix>_<md5前10>
_KNOWN = {
    "Principles of Economics 10e": "mankiw_principles_econ_10e",
    "Principles of Microeconomics The Way We": "microecon_en_full_v2",
    "Principles of Microeconomics The Way We Live": "microecon_en_full_v2",
    "Calculus Volume 1": "openstax_calculus_v1",
}

CHANNELS = {
    "econ":    {"name": "程序化英文经济学", "folder": "经济学", "lang": "en", "key_id": "econ",
                "runner": "econ_flywheel_en_run.sh", "prefix": "econ_en",
                "log": ROOT / "econ_pipeline/flywheel_en.log"},
    "econ_zh": {"name": "程序化中文经济学", "folder": "经济学", "lang": "zh", "key_id": "econ_zh",
                "runner": "econ_flywheel_zh_run.sh", "prefix": "econ_zh",
                "log": ROOT / "econ_pipeline/flywheel_zh.log"},
    "math_en": {"name": "程序化英文数学", "folder": "英文数学", "lang": "en", "key_id": "math_en",
                "runner": "math_flywheel_en_run.sh", "prefix": "math_en",
                "log": ROOT / "math_pipeline/flywheel_en.log"},
    "math_zh": {"name": "程序化中文数学", "folder": "中文数学", "lang": "zh", "key_id": "math_zh",
                "runner": "math_flywheel_zh_run.sh", "prefix": "math_zh",
                "log": ROOT / "math_pipeline/flywheel_zh.log"},
}


def _keys() -> dict:
    try:
        return json.loads((ROOT / ".pipeline_keys.json").read_text())
    except Exception:
        return {}


def _is_lang(text: str, lang: str) -> bool:
    import re
    samp = text[:120000]
    zh = len(re.findall(r'[一-鿿]', samp)); en = len(re.findall(r'[A-Za-z]', samp))
    return (zh < en) if lang == "en" else (zh > en)


def _resolve(prefix: str, stem: str) -> str:
    if stem in _KNOWN:
        return _KNOWN[stem]
    return f"{prefix}_{hashlib.md5(stem.encode('utf-8')).hexdigest()[:10]}"


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
            folder = MD_BASE / c["folder"]
            books, total_ku = [], 0
            for md in sorted(glob.glob(str(folder / "*.md"))):
                stem = Path(md).stem
                try:
                    text = open(md, encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                if not _is_lang(text, c["lang"]):     # 经济学文件夹混中英 → 按 channel 语言筛
                    continue
                sub = _resolve(c["prefix"], stem)
                ku = await conn.fetchval(
                    "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sub) or 0
                total_ku += ku
                books.append({"title": stem, "substrate": sub, "ku": ku, "in_db": ku > 0, "done": ku > 0})
            out.append({
                "id": cid, "name": c["name"], "folder": str(folder),
                "running": len(_running_pids(cid)) > 0,
                "has_key": bool(_keys().get(c["key_id"])),
                "books_total": len(books), "books_done": sum(1 for b in books if b["done"]),
                "ku_count": total_ku, "books": books,
                "last_log": _last_log(c["log"]),
            })
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
    if not _keys().get(c["key_id"]):
        raise HTTPException(400, f"通道 {cid} 未配置 NIM key")
    c["log"].parent.mkdir(parents=True, exist_ok=True)
    logf = open(c["log"], "ab")
    subprocess.Popen(["bash", f"scripts/{c['runner']}"], cwd=str(ROOT),
                     env={**os.environ, "DATABASE_URL": DSN},
                     stdout=logf, stderr=logf, start_new_session=True)
    return {"status": "ok", "msg": f"{cid} flywheel started"}


@router.post("/pipelines/{cid}/stop")
async def stop_pipeline(cid: str):
    if cid not in CHANNELS:
        raise HTTPException(404, "unknown channel")
    killed = []
    for pid in _running_pids(cid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL); killed.append(pid)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL); killed.append(pid)
            except Exception:
                pass
    return {"status": "ok", "msg": f"stopped {len(killed)} proc", "killed": killed}
