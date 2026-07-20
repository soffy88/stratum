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
import time
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

OCR_LOG = ROOT / "math_pipeline/ocr_daemon.log"
OCR_CACHE = ROOT / "math_pipeline/ocr_cache"
_OCR_BOOK_RE = re.compile(r"── OCR: (.+?) \((\d+)页\) ──")

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
    "advmath": {
        "name": "高级数学经济专用(讲透至高中生可懂, 深度不减)",
        # ★用户自己维护的单一文件夹(源PDF+转换出的MD都在这, 方便自己抽查), 不在
        # MD_BASE(books/MD/)下面, 用 folder_abs 走绝对路径(见下面 folders 的取法)。
        "folder_abs": ["/mnt/d/books/高级数学经济专用"],
        "needs_key": True,
        "key_id": "math_en",  # ★闲置key(旧math_flywheel_en.sh已废弃, 见文件头注释)
        "runner": "advmath_flywheel_run.sh",
        "prefixes": ["advmath_zh_", "advmath_en_"],
        "by_lang": True,
        "known": [],
        "log": ROOT / "advmath_pipeline/flywheel.log",
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


def _ocr_status() -> dict:
    """当前 ocr-vllm 在转哪本书 + 进度。日志用 \\r 覆写进度行(并发4线程, 完成顺序非严格递增),
    真正可靠的"已完成页数"取该书在 ocr_cache/ 下最近写入的子目录里 page_*.txt 计数, 而不是解析
    日志里的 i/n(那个只是"曾经打印过的最大序号", 并发下会乱序)。"""
    try:
        size = OCR_LOG.stat().st_size
        with open(OCR_LOG, "rb") as f:
            f.seek(max(0, size - 65536))
            tail = f.read().decode("utf-8", "replace")
    except Exception:
        return {"active": False}

    segs = [s for s in re.split(r"[\r\n]", tail) if s.strip()]
    book, total_pages, book_idx = None, 0, -1
    for i, s in enumerate(segs):
        m = _OCR_BOOK_RE.search(s)
        if m:
            book, total_pages, book_idx = m.group(1), int(m.group(2)), i
    if book is None:
        return {"active": False}

    if any("OCR完成" in s or "OCR失败" in s for s in segs[book_idx + 1 :]):
        return {"active": False, "last_book": book, "total_pages": total_pages}

    pages_done = 0
    try:
        subdirs = [d for d in OCR_CACHE.iterdir() if d.is_dir()]
        if subdirs:
            newest = max(subdirs, key=lambda d: d.stat().st_mtime)
            if time.time() - newest.stat().st_mtime < 600:
                pages_done = len(list(newest.glob("page_*.txt")))
    except Exception:
        pass

    return {
        "active": True,
        "book": book,
        "total_pages": total_pages,
        "pages_done": pages_done,
        "percent": round(pages_done / total_pages * 100, 1) if total_pages else 0.0,
    }


_ECON_BOOK_START_RE = re.compile(r"★ 经济学管道 \[.+?\]: (.+)")
_MATH_BOOK_START_RE = re.compile(r"── 抽取: (.+?) \(sub=(\S+)\) ──")


def _flywheel_progress(cid: str) -> dict | None:
    """当前飞轮正在处理哪本书 + 进度。econ_zh/misc 共用底层 econ_batch_run.sh(起始行
    "★ 经济学管道 [...]: 标题"+下一行 SUBSTRATE=xxx), 单本的细粒度章节进度在
    econ_pipeline/{substrate}_run.log 里([1/5]逐章讲透阶段耗时占大头, 有 "N/M chapters done"
    可解析; 2-5 阶段快、只报步骤号)。math_prog 是 0-LLM 规则抽取, 单本几秒内完成, 没有
    细粒度进度, 只报"正在抽取哪本"。"""
    if not _running_pids(cid):
        return None
    c = CHANNELS[cid]
    try:
        size = c["log"].stat().st_size
        with open(c["log"], "rb") as f:
            f.seek(max(0, size - 65536))
            tail = f.read().decode("utf-8", "replace")
    except Exception:
        return None
    lines = tail.splitlines()

    if cid == "math_prog":
        book, idx = None, -1
        for i, l in enumerate(lines):
            m = _MATH_BOOK_START_RE.search(l)
            if m:
                book, idx = m.group(1), i
        if book is None:
            return None
        if any(("本轮处理" in l or "飞轮完成" in l) for l in lines[idx + 1 :]):
            return None
        return {
            "book": book,
            "step": None,
            "total_steps": None,
            "chapters_done": None,
            "chapters_total": None,
            "percent": None,
        }

    # econ_zh / misc
    book, sub, idx = None, None, -1
    for i, l in enumerate(lines):
        m = _ECON_BOOK_START_RE.search(l)
        if m:
            book, idx = m.group(1).strip(), i
            for j in range(i, min(i + 4, len(lines))):
                sm = re.search(r"SUBSTRATE=(\S+)", lines[j])
                if sm:
                    sub = sm.group(1)
                    break
    if book is None:
        return None
    after = lines[idx + 1 :]
    if any(_ECON_BOOK_START_RE.search(l) for l in after) or any(
        ("✓ 移动" in l or "飞轮完成" in l) for l in after
    ):
        return None

    result = {
        "book": book,
        "step": None,
        "total_steps": 5,
        "chapters_done": None,
        "chapters_total": None,
        "percent": None,
    }
    if not sub:
        return result
    try:
        rl = (ROOT / "econ_pipeline" / f"{sub}_run.log").read_text(errors="replace")
    except Exception:
        return result

    step = None
    for m in re.finditer(r"\[(\d)/5\]", rl):
        step = int(m.group(1))
    result["step"] = step

    if step in (None, 1):
        chap_done, chap_total = 0, None
        m0 = re.search(rf"\[{re.escape(sub)}\] (\d+)/(\d+) chapters done", rl)
        if m0:
            chap_done, chap_total = int(m0.group(1)), int(m0.group(2))
        for m in re.finditer(r"ch\d+:.*\[(\d+)/(\d+)\]", rl):
            chap_done, chap_total = int(m.group(1)), int(m.group(2))
        if chap_total:
            result["chapters_done"], result["chapters_total"] = chap_done, chap_total
            result["percent"] = round(chap_done / chap_total * 100, 1)
    else:
        result["percent"] = round(step / 5 * 100, 1)
    return result


_OCR_SERVICE = "aii-ocr-daemon"


def _ocr_service_active() -> bool:
    """OCR daemon 是否在跑——查独立 systemd 服务 aii-ocr-daemon, 不再靠扫 cmdline。
    ★为什么走服务: 之前 /ocr/start 用 subprocess.Popen 把 daemon 拉成 aii-backend 的子进程,
    落在 backend 的 systemd cgroup 里, 每次重启 aii-backend 都会连带把 OCR daemon 一起杀掉
    (2026-07-14 实测: 开发学习模块时反复重启 backend, OCR 被无声带走)。放进它自己的服务
    →独立 cgroup, 与 backend 生命周期解耦。"""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", _OCR_SERVICE],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False


@router.get("/ocr/status")
async def ocr_status():
    data = _ocr_status()
    data["running"] = _ocr_service_active()
    if not data["running"]:
        # 服务已停但日志尾最后一条"── OCR:"后没等到"完成/失败"就被打断 → 日志会误判成仍 active,
        # 用服务真实存活状态纠正, 避免前端显示"运行中"却按钮全灰。
        data["active"] = False
    return {"status": "ok", "data": data}


@router.post("/ocr/stop")
async def stop_ocr():
    if not _ocr_service_active():
        return {"status": "ok", "msg": "not running"}
    # systemd 默认 KillMode=control-group: SIGTERM 发给 cgroup 内全部进程, 正在跑的
    # math_convert.py/econ_convert.py 的 release_container() 会被触发, ocr-vllm 优雅释放。
    subprocess.run(["systemctl", "--user", "stop", _OCR_SERVICE], capture_output=True, timeout=90)
    return {"status": "ok", "msg": "stop signal sent, ocr-vllm will release gracefully"}


@router.post("/ocr/start")
async def start_ocr():
    if _ocr_service_active():
        return {"status": "ok", "msg": "already running"}
    r = subprocess.run(
        ["systemctl", "--user", "start", _OCR_SERVICE],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        raise HTTPException(500, f"启动 {_OCR_SERVICE} 失败: {r.stderr[:200]}")
    return {"status": "ok", "msg": "ocr daemon started (systemd 独立服务, 不随backend重启)"}


@router.get("/pipelines")
async def list_pipelines():
    conn = await asyncpg.connect(DSN)
    try:
        out = []
        for cid, c in CHANNELS.items():
            folders = (
                [Path(f) for f in c["folder_abs"]]
                if "folder_abs" in c
                else [MD_BASE / f for f in c["folder"]]
            )
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
                    "current": _flywheel_progress(cid),
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
