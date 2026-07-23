"""bundle_split_service — EPUB 套装拆分 + file_hash 回填（Stratum Layer 4，§20）。

职责:
  1. epub_toc_split 试拆 → 判断是否真套装
  2. 拆成 N 个子 substrate（各含独立 derivative.markdown）
  3. 更新父 substrate: parse_quality='bundle'，meta_json['bundle_count']=N
  4. 回填 file_hash（父记录 + 每个子记录的唯一派生 hash）
  5. 真重复（同 SHA256）→ 标记为 'duplicate'
  6. 调 md_export_service.export_one() 导出子书到 AII

Bundle 判据（§20 约束内实现）:
  - epub_toc_split 返回的真书（去掉扉页/目录等辅助节点）≥ 2 本
  - 辅助节点: content < 2000 chars 且 title 含 扉页/目录/版权/前言/封面
  - 触发拆分: real_count >= 2

§20: 不改 oprim/oskill/omodul/obase/oservi 主库
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from ulid import ULID

from stratum.db import get_conn
from stratum.services.md_export_service import _detect_language

log = logging.getLogger(__name__)

# 辅助节点关键词（这类条目不算真正的书）
_AUX_TITLES = frozenset(
    [
        "扉页",
        "目录",
        "版权",
        "前言",
        "序言",
        "后记",
        "封面",
        "cover",
        "toc",
        "copyright",
        "preface",
        "contents",
        "foreword",
        "introduction",
        "about",
        "总目录",
    ]
)
_AUX_CONTENT_MAX = 2000  # chars


def _is_aux_node(title: str, content: str) -> bool:
    t = title.lower().strip()
    return len(content) < _AUX_CONTENT_MAX and any(kw in t for kw in _AUX_TITLES)


def _sha256(path: str) -> str:
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return h


def _child_file_hash(parent_hash: str, index: int) -> str:
    """父 SHA256 + 子序号 → 子 file_hash（保证唯一，符合 dedup 索引）。"""
    return f"{parent_hash[:32]}_p{index:03d}"


def _detect_bundle(books) -> list:
    """过滤掉辅助节点，返回真正的书列表。"""
    return [b for b in books if not _is_aux_node(b.book_title, b.content)]


def fix_file_hash(substrate_id: str) -> dict:
    """计算 source_path 的 SHA256 并回填 substrates.file_hash。

    Returns:
        dict: {'status': 'ok'|'skipped'|'error', 'hash': ..., 'substrate_id': ...}
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, source_path, file_hash FROM substrates WHERE id=?", (substrate_id,)
        ).fetchone()

    if not row:
        return {"status": "not_found", "substrate_id": substrate_id}

    sid, source_path, existing_hash = row
    if existing_hash:
        return {
            "status": "skipped",
            "reason": "hash already set",
            "substrate_id": sid,
            "hash": existing_hash,
        }
    if not source_path or not Path(source_path).exists():
        return {"status": "error", "reason": "source_path missing", "substrate_id": sid}

    h = _sha256(source_path)
    try:
        with get_conn() as conn:
            conn.execute("UPDATE substrates SET file_hash=?, updated_at=NOW() WHERE id=?", (h, sid))
        log.info("bundle_split: fix_file_hash %s → %s", sid[:12], h[:16])
        return {"status": "ok", "substrate_id": sid, "hash": h}
    except Exception as exc:
        err = str(exc).lower()
        if "duplicate key" in err or "constraint" in err or "unique" in err:
            # 同 user_id + file_hash 已存在 → 当前记录是真重复
            with get_conn() as conn:
                conn.execute(
                    "UPDATE substrates SET parse_quality='duplicate', updated_at=NOW() WHERE id=?",
                    (sid,),
                )
            log.info(
                "bundle_split: fix_file_hash %s → auto-marked duplicate (hash=%s)", sid[:12], h[:16]
            )
            return {
                "status": "duplicate",
                "substrate_id": sid,
                "hash": h,
                "reason": "same file_hash already exists for this user",
            }
        raise


def deduplicate_same_hash(substrate_ids: list[str]) -> dict:
    """给定同一文件的多份 substrate，保留最旧一份，其余标 duplicate。

    Returns:
        dict: {'kept': id, 'marked_duplicate': [ids]}
    """
    if len(substrate_ids) <= 1:
        return {"kept": substrate_ids[0] if substrate_ids else None, "marked_duplicate": []}

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, created_at FROM substrates WHERE id IN ({','.join('?' * len(substrate_ids))})"
            f" ORDER BY created_at ASC",
            substrate_ids,
        ).fetchall()

    if not rows:
        return {"kept": None, "marked_duplicate": []}

    keep_id = rows[0][0]
    dup_ids = [r[0] for r in rows[1:]]

    with get_conn() as conn:
        for did in dup_ids:
            conn.execute(
                "UPDATE substrates SET parse_quality='duplicate', updated_at=NOW() WHERE id=?",
                (did,),
            )
    log.info("bundle_split: dedup kept=%s marked_dup=%s", keep_id[:12], [d[:12] for d in dup_ids])
    return {"kept": keep_id, "marked_duplicate": dup_ids}


def split_one(substrate_id: str, *, force: bool = False) -> dict:
    """拆分单个 EPUB 套装为子 substrate。

    Args:
        substrate_id: 要拆分的 substrate ID
        force: 即使 parse_quality='bundle'/'duplicate' 也重跑

    Returns:
        dict: {status, substrate_id, split_count, children, skipped_reason}
    """
    t_start = time.time()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id, title, mime, source_path, file_hash,"
            " byte_size, page_count, language, parse_quality, meta_json"
            " FROM substrates WHERE id=?",
            (substrate_id,),
        ).fetchone()

    if not row:
        return {"status": "not_found", "substrate_id": substrate_id}

    (
        sid,
        user_id,
        title,
        mime,
        source_path,
        file_hash,
        byte_size,
        page_count,
        language,
        parse_quality,
        meta_json_raw,
    ) = row

    meta = json.loads(meta_json_raw or "{}")

    if not force and parse_quality == "bundle":
        return {"status": "skipped", "reason": "already bundle", "substrate_id": sid}
    if not force and meta.get("is_bundle_child"):
        return {"status": "skipped", "reason": "is_bundle_child", "substrate_id": sid}
    if not source_path or not Path(source_path).exists():
        return {"status": "error", "reason": "source_path missing", "substrate_id": sid}
    if mime and "epub" not in mime.lower():
        return {"status": "skipped", "reason": f"not epub (mime={mime})", "substrate_id": sid}

    # ── epub_toc_split ────────────────────────────────────────────────────────
    try:
        from oprim.epub_toc_split import epub_toc_split

        all_books = epub_toc_split(file_path=Path(source_path))
    except Exception as exc:
        log.error("bundle_split: epub_toc_split failed %s: %s", sid[:12], exc)
        return {"status": "error", "reason": f"epub_toc_split: {exc}", "substrate_id": sid}

    real_books = _detect_bundle(all_books)
    log.info("bundle_split: %s toc=%d real=%d", sid[:12], len(all_books), len(real_books))

    # 确保父记录 file_hash 已填
    if not file_hash:
        fix_res = fix_file_hash(sid)
        file_hash = fix_res.get("hash") or ""

    # ── 非套装 → 单本，直接更新 derivative ────────────────────────────────────
    if len(real_books) < 2:
        content = all_books[0].content if all_books else ""
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM derivative WHERE substrate_id=? AND kind='markdown'", (sid,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE derivative SET content=? WHERE substrate_id=? AND kind='markdown'",
                    (content, sid),
                )
            else:
                conn.execute(
                    "INSERT INTO derivative (id, substrate_id, kind, seq, content, created_at)"
                    " VALUES (?, ?, 'markdown', 0, ?, NOW())",
                    (str(ULID()), sid, content),
                )
            conn.execute(
                "UPDATE substrates SET parse_quality='ok', parser='epub_toc_split',"
                " updated_at=NOW() WHERE id=?",
                (sid,),
            )
        log.info("bundle_split: single-book %s (%d chars)", sid[:12], len(content))
        return {
            "status": "ok",
            "substrate_id": sid,
            "is_bundle": False,
            "split_count": 1,
            "children": [],
            "elapsed_s": round(time.time() - t_start, 1),
        }

    # ── 套装 → 拆分 N 子 substrate ────────────────────────────────────────────
    child_ids: list[str] = []
    child_results: list[dict] = []

    # 先删除该父的旧子记录（force 重跑时）
    if force:
        with get_conn() as conn:
            old_children = conn.execute(
                "SELECT id FROM substrates WHERE meta_json->>'bundle_parent_id'=?", (sid,)
            ).fetchall()
            for (old_cid,) in old_children:
                conn.execute("DELETE FROM derivative WHERE substrate_id=?", (old_cid,))
                conn.execute("DELETE FROM substrates WHERE id=?", (old_cid,))
            log.info(
                "bundle_split: force-cleared %d old children of %s", len(old_children), sid[:12]
            )

    for i, book in enumerate(real_books):
        child_id = str(ULID())
        child_hash = _child_file_hash(file_hash, i) if file_hash else None
        child_meta = {
            **{k: v for k, v in meta.items() if k not in ("is_bundle", "bundle_count")},
            "is_bundle_child": True,
            "bundle_parent_id": sid,
            "bundle_index": i,
            "medium": meta.get("medium", "book"),
        }
        # 页数估算（300字/页）
        est_pages = max(1, len(book.content) // 300)
        child_lang = (
            book.metadata.get("language") or language or _detect_language(book.content or "")
        )

        with get_conn() as conn:
            conn.execute(
                "INSERT INTO substrates"
                " (id, user_id, title, mime, source_path, file_hash,"
                "  byte_size, page_count, parser, language,"
                "  parse_quality, meta_json, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW())",
                (
                    child_id,
                    user_id,
                    book.book_title,
                    mime,
                    source_path,
                    child_hash,
                    (byte_size or 0) // max(len(real_books), 1),
                    est_pages,
                    "epub_toc_split",
                    child_lang,
                    "ok",
                    json.dumps(child_meta, ensure_ascii=False),
                ),
            )
            conn.execute(
                "INSERT INTO derivative (id, substrate_id, kind, seq, content, created_at)"
                " VALUES (?, ?, 'markdown', 0, ?, NOW())",
                (str(ULID()), child_id, book.content),
            )

        child_ids.append(child_id)
        child_results.append(
            {
                "id": child_id,
                "title": book.book_title,
                "chars": len(book.content),
            }
        )
        log.info(
            "bundle_split: child[%d] %s → %s (%d chars)",
            i,
            child_id[:12],
            book.book_title[:35],
            len(book.content),
        )

    # 更新父 substrate
    parent_meta = {**meta, "is_bundle": True, "bundle_count": len(real_books)}
    with get_conn() as conn:
        conn.execute(
            "UPDATE substrates SET parse_quality='bundle', meta_json=?,"
            " updated_at=NOW() WHERE id=?",
            (json.dumps(parent_meta, ensure_ascii=False), sid),
        )

    # AII 导出子书
    # export_one 内部调 asyncio.run()，必须在独立线程中运行（避免 event loop 冲突）
    import concurrent.futures
    from stratum.services.md_export_service import export_one

    aii_ok = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        futures = {pool.submit(export_one, cid): cid for cid in child_ids}
        for fut, cid in futures.items():
            try:
                res = fut.result(timeout=120)
                if res.get("status") in ("ok", "exported", "completed"):
                    aii_ok += 1
                else:
                    log.warning(
                        "bundle_split: export_one %s status=%s", cid[:12], res.get("status")
                    )
            except Exception as exc:
                log.warning("bundle_split: export_one failed %s: %s", cid[:12], exc)

    elapsed = round(time.time() - t_start, 1)
    log.info(
        "bundle_split: done %s → %d children, %d exported, %.1fs",
        sid[:12],
        len(real_books),
        aii_ok,
        elapsed,
    )
    return {
        "status": "ok",
        "substrate_id": sid,
        "title": title,
        "is_bundle": True,
        "split_count": len(real_books),
        "aii_exported": aii_ok,
        "children": child_results,
        "elapsed_s": elapsed,
    }


def split_batch(*, force: bool = False, epub_only: bool = True) -> dict:
    """批量检测并拆分所有套装 EPUB。

    查条件: mime LIKE '%epub%' AND parse_quality NOT IN ('bundle', 'bundle_child')
    """
    with get_conn() as conn:
        q = "SELECT id, title, byte_size, parse_quality FROM substrates WHERE mime LIKE '%epub%'"
        if not force:
            q += " AND parse_quality NOT IN ('bundle')"
        q += " AND source_path IS NOT NULL ORDER BY byte_size DESC LIMIT 100"
        candidates = conn.execute(q).fetchall()

    log.info("bundle_split: batch found %d candidates", len(candidates))
    results = []
    bundle_count = single_count = skip_count = err_count = 0

    for sid, title, byte_size, pq in candidates:
        if not force and pq == "bundle":
            skip_count += 1
            continue
        try:
            res = split_one(sid, force=force)
            results.append(res)
            s = res["status"]
            if s == "ok":
                if res.get("is_bundle"):
                    bundle_count += 1
                else:
                    single_count += 1
            elif s == "skipped":
                skip_count += 1
            else:
                err_count += 1
        except Exception as exc:
            log.error("bundle_split: batch item %s failed: %s", sid[:12], exc, exc_info=True)
            results.append({"status": "error", "substrate_id": sid, "reason": str(exc)})
            err_count += 1

    return {
        "status": "done",
        "total": len(candidates),
        "bundle_split": bundle_count,
        "single": single_count,
        "skipped": skip_count,
        "error": err_count,
        "results": results,
    }


def fix_hash_batch(*, only_null: bool = True) -> dict:
    """批量回填 file_hash=NULL 的 EPUB substrates。"""
    with get_conn() as conn:
        q = "SELECT id FROM substrates WHERE mime LIKE '%epub%' AND source_path IS NOT NULL"
        if only_null:
            q += " AND file_hash IS NULL"
        rows = conn.execute(q).fetchall()

    results = []
    ok_count = err_count = skip_count = 0
    for (sid,) in rows:
        res = fix_file_hash(sid)
        results.append(res)
        s = res["status"]
        if s == "ok":
            ok_count += 1
        elif s in ("skipped", "duplicate"):
            skip_count += 1
        else:
            err_count += 1

    return {
        "status": "done",
        "total": len(rows),
        "ok": ok_count,
        "skipped_or_deduped": skip_count,
        "error": err_count,
    }
