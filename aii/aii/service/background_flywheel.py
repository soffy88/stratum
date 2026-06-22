"""background_flywheel — 常驻后台飞轮 (asyncio.create_task, 无新依赖).

配置 (环境变量 / 默认值):
  FLYWHEEL_ENABLED          = true      开关
  FLYWHEEL_MAX_FILES_ROUND  = 10        ★限流: 每轮最多处理 N 个文件
  FLYWHEEL_INTERVAL         = 60        轮间隔(秒)
  FLYWHEEL_EVOLVE_EVERY     = 4         每 N 轮跑一次 evolve+needs

守命门:
  - 单轮任何异常 → log + continue, 绝不 crash
  - CancelledError 立即退出 (lifespan shutdown)
  - evolve() 每 EVOLVE_EVERY 轮跑一次, 失败非致命
  - P2.6 purpose: 只导向主动选源(排序), 不拦手动投递/摄取入库
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SHARED_DIR = Path(os.getenv("FLYWHEEL_SHARED_DIR", "/home/soffy/shared/stratum-to-aii"))
_OUTPUT_DIR = Path(os.getenv("FLYWHEEL_OUTPUT_DIR", "/home/soffy/shared/aii-to-stratum"))

FLYWHEEL_ENABLED: bool = os.getenv("FLYWHEEL_ENABLED", "true").lower() not in {"false", "0", "no"}
FLYWHEEL_MAX_FILES_ROUND: int = int(os.getenv("FLYWHEEL_MAX_FILES_ROUND", "10"))
FLYWHEEL_INTERVAL: int = int(os.getenv("FLYWHEEL_INTERVAL", "60"))
FLYWHEEL_EVOLVE_EVERY: int = int(os.getenv("FLYWHEEL_EVOLVE_EVERY", "4"))

# 合集过滤: 超过此大小的文件跳过(MB), 0=不过滤
FLYWHEEL_MAX_FILE_MB: float = float(os.getenv("FLYWHEEL_MAX_FILE_MB", "5"))

# P2.6 purpose目的层选源
# purpose.md 由人工维护, AII不自生成/不自改
_PURPOSE_FILE = Path(__file__).parent.parent.parent / "config" / "purpose.md"
_purpose_text: str | None = None          # 缓存: 每次飞轮启动读一次
_purpose_embedding: list[float] | None = None  # 缓存: 启动后算一次
_purpose_title_scores: dict[str, float] = {}   # sid → score 跨轮缓存


def _read_purpose_text() -> str:
    """Read purpose.md (human-authored direction). Returns "" if missing."""
    if _PURPOSE_FILE.exists():
        return _PURPOSE_FILE.read_text(encoding="utf-8").strip()
    return ""


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed texts via default provider (sync, run in thread executor)."""
    from oprim import vector_encode
    import numpy as np
    raw = vector_encode(texts=texts, provider="default")
    arr = np.array(raw, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (arr / norms).tolist()


async def _sort_candidates_by_purpose(
    candidates: list[tuple],
) -> list[tuple]:
    """Sort (md, meta, sid) candidates by purpose_alignment_score descending.

    P2.6 命门: 只排序(导向选源), 不过滤. 所有候选仍可进入摄取.
    失败(purpose缺失/embedding错误) → 返回原序不影响流程.
    """
    global _purpose_text, _purpose_embedding

    # 读/缓存 purpose 文本
    if _purpose_text is None:
        _purpose_text = _read_purpose_text()
    if not _purpose_text:
        return candidates  # 无 purpose 文件 → 不排序

    # 计算/缓存 purpose embedding (一次)
    if _purpose_embedding is None:
        try:
            embs = await asyncio.to_thread(_embed_batch, [_purpose_text])
            _purpose_embedding = embs[0]
        except Exception as e:
            logger.warning("purpose: embedding purpose text failed: %s", e)
            return candidates

    # 找需要打分的新候选
    unscored = [(md, meta, sid) for md, meta, sid in candidates
                if sid not in _purpose_title_scores]
    if unscored:
        titles = [meta.get("title") or meta.get("name") or md.stem
                  for md, meta, sid in unscored]
        try:
            title_embs = await asyncio.to_thread(_embed_batch, titles)
            from oprim import purpose_alignment_score
            for (md, meta, sid), emb in zip(unscored, title_embs):
                title = meta.get("title") or meta.get("name") or md.stem
                try:
                    score = purpose_alignment_score(
                        purpose_text=_purpose_text,
                        ku_text=title,
                        embedding_purpose=_purpose_embedding,
                        embedding_ku=emb,
                    )
                except Exception:
                    score = 0.0
                _purpose_title_scores[sid] = score
        except Exception as e:
            logger.warning("purpose: batch embedding candidates failed: %s", e)
            return candidates  # embedding失败 → 原序

    scored = sorted(candidates, key=lambda x: _purpose_title_scores.get(x[2], 0.0), reverse=True)
    if scored:
        top = scored[0]
        logger.info(
            "purpose: sorted %d candidates, top=%s score=%.3f",
            len(scored),
            (top[1].get("title") or top[2][:12])[:40],
            _purpose_title_scores.get(top[2], 0.0),
        )
    return scored

# 标题关键词过滤: 含这些词的视为合集/套装,跳过等待 Stratum 拆分
_COLLECTION_KEYWORDS = ("套装", "合集", "全集", "丛书", "系列", "册）", "册)", "全套", "百科全书", "百科辞典", "百科词典")


def _is_collection(md: Path, meta: dict) -> tuple[bool, str]:
    """判断是否为合集/超大文件. 返回 (is_skip, reason)."""
    # 文件大小检查
    if FLYWHEEL_MAX_FILE_MB > 0:
        mb = md.stat().st_size / 1024 / 1024
        if mb > FLYWHEEL_MAX_FILE_MB:
            return True, f"file_too_large({mb:.1f}MB>{FLYWHEEL_MAX_FILE_MB}MB)"
    # 标题关键词检查
    title = (meta.get("title") or meta.get("name") or "")
    for kw in _COLLECTION_KEYWORDS:
        if kw in title:
            return True, f"collection_keyword({kw!r} in title)"
    return False, ""


def _write_skipped_collections(skipped: list[dict]) -> None:
    """将跳过的合集写到 aii-to-stratum/skipped_collections.json 供 Stratum 返工."""
    if not skipped:
        return
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _OUTPUT_DIR / "skipped_collections.json"
        # 合并已有记录(去重)
        existing: list[dict] = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing_ids = {e.get("id") for e in existing}
        new_entries = [s for s in skipped if s.get("id") not in existing_ids]
        all_entries = existing + new_entries
        out_path.write_text(
            json.dumps(all_entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if new_entries:
            logger.info(
                "flywheel: skipped_collections.json updated (+%d new, %d total)",
                len(new_entries), len(all_entries),
            )
    except Exception:
        logger.exception("flywheel: write skipped_collections failed (non-fatal)")


async def _collect_new_files(backend, limit: int) -> list[Path]:
    """返回至多 limit 个尚未摄入的 .md 文件 (配对 .json 必须存在).
    跳过超大合集(>FLYWHEEL_MAX_FILE_MB 或标题含套装/合集等关键词).
    跳过的文件不标为已摄取, Stratum 拆分后可重新进来."""
    found: list[Path] = []
    skipped_collections: list[dict] = []

    # 文件系统扫描放进线程: WSL2 跨文件系统下 Path.exists() 约 100ms/次,
    # 690 个 .md 文件 → ~49s 同步阻塞事件循环. 扫描结果是 (md, meta, sid) 三元组.
    def _scan_candidates() -> list[tuple]:
        result = []
        for md in sorted(_SHARED_DIR.glob("*.md")):
            jp = md.with_suffix(".json")
            if not jp.exists():
                continue
            try:
                meta = json.loads(jp.read_text(encoding="utf-8"))
                sid = meta.get("id", "")
                if sid:
                    result.append((md, meta, sid))
            except Exception:
                logger.warning("flywheel: bad sidecar %s, skip", jp.name)
        return result

    candidates = await asyncio.to_thread(_scan_candidates)

    # P2.6: 按purpose目的对齐分排序 (命门: 只排序不过滤, 手动投递路径不经此处)
    candidates = await _sort_candidates_by_purpose(candidates)

    for md, meta, sid in candidates:
        if len(found) >= limit:
            break
        try:
            if await backend.is_substrate_ingested(sid):
                continue

            # ── 合集/大文件过滤 ──────────────────────────────────────────
            skip, reason = _is_collection(md, meta)
            if skip:
                mb = md.stat().st_size / 1024 / 1024
                title = (meta.get("title") or meta.get("name") or md.stem)[:80]
                logger.info(
                    "flywheel: SKIP collection %s (%.1fMB) reason=%s",
                    title, mb, reason,
                )
                skipped_collections.append({
                    "id": sid,
                    "title": title,
                    "file": md.name,
                    "size_mb": round(mb, 1),
                    "reason": reason,
                })
                continue  # 不加入 found, 不标已摄

            found.append(md)
        except Exception:
            logger.warning("flywheel: error checking %s, skip", md.name)

    # 写合集清单供 Stratum 返工
    _write_skipped_collections(skipped_collections)
    return found


def _write_needs(gaps: dict) -> None:
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        high_miss = gaps.get("high_miss_topics", [])
        needs = [
            {
                "topic": t["topic"] if isinstance(t, dict) else str(t),
                "reason": "high_miss",
                "miss_count": t.get("miss_count", 0) if isinstance(t, dict) else 0,
            }
            for t in high_miss
        ]

        # P2.6: 对 needs 按 purpose 对齐分排序 (纯keyword，同步，无需embedding)
        # 方向内缺口排前，指导人工找源时优先补方向内知识
        if needs and _purpose_text:
            from oprim._purpose_alignment_score import _keyword_overlap
            for n in needs:
                n["purpose_score"] = round(_keyword_overlap(_purpose_text, n["topic"]), 4)
            needs.sort(key=lambda n: n["purpose_score"], reverse=True)
            logger.info(
                "purpose: needs sorted by purpose score, top=%s score=%.4f",
                needs[0]["topic"][:30] if needs else "",
                needs[0].get("purpose_score", 0) if needs else 0,
            )

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "needs": needs,
        }
        (_OUTPUT_DIR / "needs.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("flywheel: wrote needs.json (%d topics)", len(needs))
    except Exception:
        logger.exception("flywheel: needs.json write failed (non-fatal)")


async def _backfill_deep_one(backend) -> bool:
    """找 1 个已摄入但尚未做深度理解的 substrate, 跑 RelationEngine + DeepSynthesis.
    返回 True 表示找到并处理了, False 表示没有需要回填的."""
    from aii.service.auto_ingest import _MEDIUM_PROVIDER, _MEDIUM_DOC_TYPE
    from aii.service.relation_engine import RelationEngine
    from aii.service.synthesis_engine_deep import DeepSynthesisEngine

    rows = await backend.list_substrates_needing_deep_understanding(limit=1)
    if not rows:
        return False

    row = rows[0]
    substrate_id = row["substrate_id"]
    title = row.get("title", substrate_id[:12])
    medium = (row.get("medium") or "").lower()
    provider = _MEDIUM_PROVIDER.get(medium, "default")
    doc_type = _MEDIUM_DOC_TYPE.get(medium, "science")

    pool = await backend._ensure_pool()
    async with pool.acquire() as conn:
        ku_rows = await conn.fetch(
            "SELECT ku_id FROM aii.ku WHERE substrate_id=$1 AND is_synthesis IS NOT TRUE",
            substrate_id,
        )
    ku_ids = [str(r["ku_id"]) for r in ku_rows]
    if not ku_ids:
        await backend.mark_deep_understood(substrate_id)
        return True

    logger.info("backfill: deep understanding for %s (%d KUs)", title[:40], len(ku_ids))

    try:
        rel = RelationEngine(backend)
        rel_r = await rel.extract_relations_async(ku_ids, provider=provider)
        logger.info("backfill: relation %s → rule=%d llm=%d", title[:30],
                    rel_r.get("rule_edges", 0), rel_r.get("llm_edges", 0))
    except Exception:
        logger.exception("backfill: RelationEngine failed for %s (non-fatal)", substrate_id[:8])

    try:
        deep = DeepSynthesisEngine(backend)
        await deep.build_overview_async(ku_ids, provider=provider)
        bk = await deep.build_book_understanding_async(
            substrate_id, ku_ids, doc_type=doc_type, provider=provider,
        )
        logger.info("backfill: book_understanding %s → status=%s", title[:30], bk.get("status"))
    except Exception:
        logger.exception("backfill: DeepSynthesis failed for %s (non-fatal)", substrate_id[:8])

    await backend.mark_deep_understood(substrate_id)
    return True


async def flywheel_loop(backend) -> None:
    """后台飞轮主循环. 由 app.py lifespan asyncio.create_task() 启动."""
    from aii.service.auto_ingest import ingest_one
    from aii.service.evolution_engine import EvolutionEngine

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    round_num = 0

    logger.info(
        "flywheel: started (enabled=%s max_files=%d interval=%ds evolve_every=%d)",
        FLYWHEEL_ENABLED, FLYWHEEL_MAX_FILES_ROUND, FLYWHEEL_INTERVAL, FLYWHEEL_EVOLVE_EVERY,
    )

    while True:
        try:
            if not FLYWHEEL_ENABLED:
                await asyncio.sleep(60)
                continue

            round_num += 1
            logger.info("flywheel: round %d begin", round_num)

            # ── A. 扫新文件, ★限流 MAX_FILES_ROUND ─────────────────────────
            new_files = await _collect_new_files(backend, FLYWHEEL_MAX_FILES_ROUND)
            if new_files:
                logger.info("flywheel: ingesting %d file(s) this round", len(new_files))
                for md in new_files:
                    try:
                        n = await ingest_one(md, backend)
                        logger.info("flywheel: %s → %s KUs", md.name, n if n >= 0 else "skip")
                    except Exception:
                        logger.exception("flywheel: ingest_one failed for %s (non-fatal)", md.name)
            else:
                logger.info("flywheel: no new files this round")

            # ── A2. 回填深度理解 (已摄入但无深度理解的, 每轮最多3个) ────────
            for _bi in range(3):
                try:
                    did = await _backfill_deep_one(backend)
                    if did:
                        logger.info("flywheel: backfill deep understanding done (substrate %d/3)", _bi + 1)
                    else:
                        break  # 没有待回填的了
                except Exception:
                    logger.exception("flywheel: backfill failed (non-fatal)")
                    break

            # ── B. 定期 evolve + 写需求文件 ──────────────────────────────────
            if round_num % FLYWHEEL_EVOLVE_EVERY == 0:
                try:
                    logger.info("flywheel: running evolution (round %d)", round_num)
                    ev = EvolutionEngine(backend)
                    report = await ev.evolve()
                    gaps = report.get("gaps") or {}
                    _write_needs(gaps)
                    logger.info(
                        "flywheel: evolve done upgraded=%d gaps=%s",
                        len(report.get("upgraded", [])),
                        {k: v for k, v in gaps.items() if k != "grade_imbalance"},
                    )
                except Exception:
                    logger.exception("flywheel: evolve failed (non-fatal)")

        except asyncio.CancelledError:
            logger.info("flywheel: cancelled, shutting down")
            break
        except Exception:
            logger.exception("flywheel: round %d unhandled error (non-fatal, continuing)", round_num)

        await asyncio.sleep(FLYWHEEL_INTERVAL)
