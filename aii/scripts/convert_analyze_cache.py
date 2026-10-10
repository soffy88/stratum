"""convert 脚本 analyze() 结果缓存 — 防 600s 轮预算被逐轮全量重扫吃掉.

背景: USB/Drive 同步后池子撑到 2000+ 文件, 每轮 pull_ingest 都全量 analyze 一遍;
需OCR/无章节/打不开 的书永远不转 → 每轮都重新付全价(扫描版单本 15~25s)。
书本体不变时按 (mtime, size) 缓存分类结果, 变了才重算。

用法:
    from convert_analyze_cache import get as _cat_cache_get, put as _cat_cache_put
    hit = _cat_cache_get(path)      # 返回 (cat, stem, npg) 或 None
    _cat_cache_put(path, result)    # result 为 analyze() 返回的三元组
写入批量落盘(脏计数≥200 或解释器退出), 原子替换, 多进程经 flock 串行无并发写。
"""

import atexit
import json
import os
import time
from pathlib import Path

_CACHE_FILE = Path(
    os.getenv(
        "AII_CONVERT_CACHE",
        str(
            Path(__file__).resolve().parent.parent
            / "context_pipeline"
            / "convert_analyze_cache.json"
        ),
    )
)
_db = None
_dirty = 0
_loaded_at = 0.0
# ★2026-09-21 门禁改 distinct 章节计数(v2): 旧缓存的"无章节结构"结论是窄正则误杀,
#   必须失效重判, 否则新门禁永不生效。
# ★2026-10-04 门禁改正则(v3): chapters() 的中文章节分支原带强制 #+ 前缀, 而 analyze()
#   跑在 PDF 原文上('#' 是 md 标记, 转换后才存在) → 中文书一律误判"无章节结构"。
#   同属窄正则误杀, 同样必须整体失效重判。
_GATE_VERSION = 3


def _load():
    global _db, _loaded_at
    if _db is None or time.time() - _loaded_at > 120:
        try:
            if _CACHE_FILE.exists():
                _db = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            else:
                _db = {}
        except Exception:
            _db = _db or {}
        _loaded_at = time.time()
    return _db


def get(path):
    """命中且文件未变 → (cat, stem, npg); 否则 None."""
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except OSError:
        return None
    ent = _load().get(str(path))
    if (
        ent
        and (ent.get("mtime"), ent.get("size")) == key
        and ent.get("ver", 1) == _GATE_VERSION
    ):
        return (ent["cat"], Path(path).stem, ent.get("npg"))
    return None


def put(path, result):
    """缓存 analyze() 三元组 (cat, stem, npg). result 为 None 时跳过."""
    global _dirty
    if not result or not result[0]:
        return
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except OSError:
        return
    p = str(path)
    db = _load()
    old = db.get(p)
    if (
        old
        and (old.get("mtime"), old.get("size")) == key
        and old.get("cat") == result[0]
        # ★2026-10-04 修复: 原条件漏判 ver —— bump 门禁版本后, 分类结论未变的条目不会覆写,
        #   ver 永远停在旧值, get() 因 ver 不匹配永不命中 → 每轮都全量重扫(实测 1100 本
        #   跑 5 小时以上)。ver 不同即视为有变化, 必须覆写以完成门禁升级。
        and old.get("ver") == _GATE_VERSION
    ):
        return  # 没变化, 不写
    db[p] = {"mtime": key[0], "size": key[1], "cat": result[0], "npg": result[2], "ver": _GATE_VERSION}
    _dirty += 1
    if _dirty >= 200:
        _flush()


def _flush():
    global _dirty
    if _db is None or _dirty == 0:
        return
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_db, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_CACHE_FILE)
        _dirty = 0
    except Exception:
        pass


atexit.register(_flush)
