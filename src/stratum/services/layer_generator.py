"""Layer Generator — L0/L1/L2 内容分层生成 (对标 OpenViking Context Layers).

每个 substrate/KU 入库后自动生成三级摘要:
  L0 (Abstract):  一句话摘要 ~100 token — 快速相关性判断
  L1 (Overview):  结构化概览 ~2K token — 关键信息 + 使用场景
  L2 (Details):   原文引用 — 按需加载 (不生成, 直接引用原文)

LLM: qwen3-8b via 本地 Ollama (免费, 与 ku_translate 共用).
"""

from __future__ import annotations

import sys

_OPRIM_ROOT = "/data/soffy/projects/platform/3O/oprim"
if _OPRIM_ROOT not in sys.path:
    sys.path.insert(0, _OPRIM_ROOT)

import asyncio
import logging
import os
from typing import Any

import httpx

from stratum.db import get_conn

logger = logging.getLogger(__name__)

_OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://172.19.0.1:11434")
_MODEL = os.environ.get("STRATUM_LLM_MODEL", "qwen3-8b")
_TIMEOUT = 300.0  # cold start can take ~180s

# ── Prompts ──────────────────────────────────────────────────────────────────

_L0_SYSTEM = """\
你是一位学术内容摘要专家。请用一句话（不超过50个中文字或30个英文词）概括以下内容的核心要义。
要求：
- 精确反映主题和关键概念
- 不要前缀（如"本文讲述"），直接输出摘要
- 如果是数学/技术内容，保留关键术语"""

_L1_SYSTEM = """\
你是一位学术内容结构化分析专家。请为以下内容生成一份结构化概览（约500-1000字），包含：

## 核心主题
一句话概括主题

## 关键概念
列出3-7个核心概念/定义/定理，每个用一句话解释

## 主要内容
2-3段概述主要内容和论证结构

## 应用场景
这些知识在哪些领域有用

## 前置知识
理解这些内容需要什么背景知识

要求：
- 保留关键数学公式（用 $...$ 格式）
- 保留专业术语的精确表述
- 不要添加原文没有的信息"""

# ── LLM call ─────────────────────────────────────────────────────────────────


def _call_llm(system_prompt: str, user_content: str, max_tokens: int = 2048) -> str:
    """Call Ollama LLM synchronously. Returns response text or empty string on failure."""
    try:
        # Truncate very long content to avoid OOM; strip NUL chars
        content = (user_content[:8000] if len(user_content) > 8000 else user_content).replace(
            "\x00", ""
        )
        resp = httpx.post(
            f"{_OLLAMA_BASE}/api/chat",
            json={
                "model": _MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                "stream": False,
                "think": False,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json().get("message", {}).get("content", "").strip()
        # Strip thinking tags from qwen3 reasoning output
        if "" in result:
            import re

            result = re.sub(r"", "", result, flags=re.DOTALL).strip()
        return result
    except Exception as exc:
        logger.warning("layer_generator: LLM call failed: %s", exc)
        return ""


async def _call_llm_async(system_prompt: str, user_content: str, max_tokens: int = 2048) -> str:
    """Call Ollama LLM asynchronously."""
    try:
        content = (user_content[:8000] if len(user_content) > 8000 else user_content).replace(
            "\x00", ""
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_OLLAMA_BASE}/api/chat",
                json={
                    "model": _MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                    "stream": False,
                    "think": False,
                },
            )
            resp.raise_for_status()
            result = resp.json().get("message", {}).get("content", "").strip()
            # Strip thinking tags from qwen3 reasoning output
            if "" in result:
                import re

                result = re.sub(r"", "", result, flags=re.DOTALL).strip()
            return result
    except Exception as exc:
        logger.warning("layer_generator: async LLM call failed: %s", exc)
        return ""


# ── Embedding ────────────────────────────────────────────────────────────────

_LLM_MODEL = "qwen3-8b"

# BGE-M3 embedder — must match substrate_layers.embedding space (1024-dim, cosine)
_bge: Any | None = None


def _get_bge():
    global _bge
    if _bge is None:
        from oprim.embedding.bge_m3 import BgeM3Embedder

        _bge = BgeM3Embedder()
    return _bge


_EMBED_DIM = 1024  # Must match substrate_layers.embedding vector dimension
_EMBEDDING_MODEL = "BAAI/bge-m3"


def _get_embedding(text: str) -> list[float] | None:
    """Get embedding vector for text using BGE-M3 — same space as substrate_layers.

    Truncates to _EMBED_DIM (1024) to match pgvector column.
    """
    try:
        text = text[:4000] if len(text) > 4000 else text
        emb = _get_bge().embed([text], dim=1024)
        if not emb or not emb[0]:
            return None
        vec = emb[0]
        return vec[:_EMBED_DIM] if len(vec) > _EMBED_DIM else vec
    except Exception as exc:
        logger.warning("layer_generator: BGE-M3 embedding failed: %s", exc)
        return None


# ── Token estimation ─────────────────────────────────────────────────────────


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for mixed CJK/English."""
    return max(1, len(text) // 4)


# ── ID generation ────────────────────────────────────────────────────────────


def _gen_id(prefix: str = "layer") -> str:
    import hashlib
    import time
    import random

    raw = f"{prefix}-{time.time()}-{random.randint(0, 999999)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ── Substrate layers ─────────────────────────────────────────────────────────


def generate_substrate_layers(
    substrate_id: str, title: str | None = None, content: str | None = None
) -> dict[str, str]:
    """Generate L0/L1 layers for a substrate. L2 is the original content.

    Args:
        substrate_id: The substrate ID
        title: Substrate title (used as L0 fallback if content is short)
        content: Substrate markdown content

    Returns:
        dict with keys 'L0', 'L1', 'L2' and their content strings
    """
    if not content and not title:
        return {"L0": "", "L1": "", "L2": ""}

    text = content or title or ""
    layers: dict[str, str] = {}

    # L0: one-sentence abstract
    if title and len(text) < 500:
        # Short content: use title as L0
        layers["L0"] = title[:200]
    else:
        l0_text = _call_llm(_L0_SYSTEM, text, max_tokens=200)
        layers["L0"] = l0_text if l0_text else (title or text[:200])

    # L1: structured overview
    l1_text = _call_llm(_L1_SYSTEM, text, max_tokens=2048)
    layers["L1"] = l1_text if l1_text else text[:3000]

    # L2: original content (no generation needed)
    layers["L2"] = text

    # Persist to DB
    _persist_substrate_layers(substrate_id, layers)

    return layers


async def generate_substrate_layers_async(
    substrate_id: str, title: str | None = None, content: str | None = None
) -> dict[str, str]:
    """Async version of generate_substrate_layers."""
    if not content and not title:
        return {"L0": "", "L1": "", "L2": ""}

    text = content or title or ""
    layers: dict[str, str] = {}

    # L0
    if title and len(text) < 500:
        layers["L0"] = title[:200]
    else:
        l0_text = await _call_llm_async(_L0_SYSTEM, text, max_tokens=200)
        layers["L0"] = l0_text if l0_text else (title or text[:200])

    # L1
    l1_text = await _call_llm_async(_L1_SYSTEM, text, max_tokens=2048)
    layers["L1"] = l1_text if l1_text else text[:3000]

    # L2
    layers["L2"] = text

    # Persist
    await asyncio.to_thread(_persist_substrate_layers, substrate_id, layers)

    return layers


def _persist_substrate_layers(substrate_id: str, layers: dict[str, str]) -> None:
    """Write substrate layers to DB, computing embeddings for L0."""
    with get_conn() as conn:
        for layer_name, content in layers.items():
            if not content:
                continue
            # Strip NUL chars (psycopg2 rejects them)
            clean = content.replace("\x00", "")
            layer_id = _gen_id(f"sl-{substrate_id}-{layer_name}")

            # Compute embedding for L0 (used for vector search)
            embedding = None
            if layer_name == "L0":
                embedding = _get_embedding(clean)

            if embedding:
                emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
                model_used = _EMBEDDING_MODEL if layer_name == "L0" else _MODEL
                conn.execute(
                    """INSERT INTO substrate_layers (id, substrate_id, layer, content, token_count, model_used, embedding)
                       VALUES (?, ?, ?, ?, ?, ?, ?::vector)
                       ON CONFLICT (substrate_id, layer) DO UPDATE
                       SET content = EXCLUDED.content,
                           token_count = EXCLUDED.token_count,
                           model_used = EXCLUDED.model_used,
                           embedding = EXCLUDED.embedding,
                           generated_at = NOW()""",
                    (
                        layer_id,
                        substrate_id,
                        layer_name,
                        clean,
                        _estimate_tokens(clean),
                        model_used,
                        emb_str,
                    ),
                )
            else:
                model_used = _EMBEDDING_MODEL if layer_name == "L0" else _MODEL
                conn.execute(
                    """INSERT INTO substrate_layers (id, substrate_id, layer, content, token_count, model_used)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT (substrate_id, layer) DO UPDATE
                       SET content = EXCLUDED.content,
                           token_count = EXCLUDED.token_count,
                           model_used = EXCLUDED.model_used,
                           generated_at = NOW()""",
                    (layer_id, substrate_id, layer_name, clean, _estimate_tokens(clean), model_used),
                )
    logger.info(
        "layer_generator: persisted substrate %s layers L0=%d L1=%d L2=%d chars",
        substrate_id,
        len(layers.get("L0", "")),
        len(layers.get("L1", "")),
        len(layers.get("L2", "")),
    )


# ── KU layers ────────────────────────────────────────────────────────────────


def generate_ku_layers(
    ku_id: str, natural_text: str, natural_text_zh: str | None = None
) -> dict[str, str]:
    """Generate L0/L1 layers for a Knowledge Unit.

    Args:
        ku_id: The KU ID (from aii.ku_onto)
        natural_text: English natural text of the KU
        natural_text_zh: Chinese translation (optional, used for bilingual L1)

    Returns:
        dict with keys 'L0', 'L1', 'L2'
    """
    if not natural_text:
        return {"L0": "", "L1": "", "L2": ""}

    text = natural_text
    layers: dict[str, str] = {}

    # L0: one-sentence abstract
    l0_text = _call_llm(_L0_SYSTEM, text, max_tokens=200)
    layers["L0"] = l0_text if l0_text else text[:200]

    # L1: structured overview (shorter for KU — KUs are already atomic)
    l1_prompt = (
        _L1_SYSTEM
        + "\n\n注意: 这是一条原子知识单元(KU), 概览应比文档更精炼, 重点突出核心概念和应用。"
    )
    l1_text = _call_llm(l1_prompt, text, max_tokens=1024)
    layers["L1"] = l1_text if l1_text else text[:2000]

    # L2: original text (+ Chinese if available)
    if natural_text_zh:
        layers["L2"] = f"{natural_text}\n\n---\n\n{natural_text_zh}"
    else:
        layers["L2"] = text

    # Persist
    _persist_ku_layers(ku_id, layers)

    return layers


def _persist_ku_layers(ku_id: str, layers: dict[str, str]) -> None:
    """Write KU layers to DB."""
    with get_conn() as conn:
        for layer_name, content in layers.items():
            if not content:
                continue
            layer_id = _gen_id(f"kl-{ku_id}-{layer_name}")
            conn.execute(
                """INSERT INTO ku_layers (id, ku_id, layer, content, token_count, model_used)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT (ku_id, layer) DO UPDATE
                   SET content = EXCLUDED.content,
                       token_count = EXCLUDED.token_count,
                       model_used = EXCLUDED.model_used,
                       generated_at = NOW()""",
                (layer_id, ku_id, layer_name, content, _estimate_tokens(content), _MODEL),
            )
    logger.info("layer_generator: persisted KU %s layers", ku_id)


# ── Query helpers ────────────────────────────────────────────────────────────


def get_substrate_layers(substrate_id: str) -> dict[str, dict[str, Any]]:
    """Get all layers for a substrate."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT layer, content, token_count, model_used, generated_at "
            "FROM substrate_layers WHERE substrate_id = ? ORDER BY layer",
            (substrate_id,),
        ).fetchall()
    return {
        r[0]: {"content": r[1], "token_count": r[2], "model": r[3], "generated_at": str(r[4])}
        for r in rows
    }


def get_ku_layers(ku_id: str) -> dict[str, dict[str, Any]]:
    """Get all layers for a KU."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT layer, content, token_count, model_used, generated_at "
            "FROM ku_layers WHERE ku_id = ? ORDER BY layer",
            (ku_id,),
        ).fetchall()
    return {
        r[0]: {"content": r[1], "token_count": r[2], "model": r[3], "generated_at": str(r[4])}
        for r in rows
    }


def get_layer_stats() -> dict[str, Any]:
    """Get layer generation statistics."""
    try:
        with get_conn() as conn:
            sl_count = conn.execute(
                "SELECT count(DISTINCT substrate_id) FROM substrate_layers WHERE layer='L0'"
            ).fetchone()[0]
            sl_total = conn.execute("SELECT count(*) FROM substrate_layers").fetchone()[0]
            kl_count = conn.execute(
                "SELECT count(DISTINCT ku_id) FROM ku_layers WHERE layer='L0'"
            ).fetchone()[0]
            kl_total = conn.execute("SELECT count(*) FROM ku_layers").fetchone()[0]
        return {
            "substrates_with_layers": sl_count,
            "substrate_layer_rows": sl_total,
            "kus_with_layers": kl_count,
            "ku_layer_rows": kl_total,
        }
    except Exception as exc:
        logger.warning("get_layer_stats failed: %s", exc)
        return {"error": str(exc)}


def get_substrates_without_layers() -> list[str]:
    """Get substrate IDs that don't have L0 layer yet (for backfill)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id FROM substrates s
               LEFT JOIN substrate_layers sl ON s.id = sl.substrate_id AND sl.layer = 'L0'
               WHERE sl.id IS NULL
               ORDER BY s.created_at DESC
               LIMIT 100"""
        ).fetchall()
    return [r[0] for r in rows]


def backfill_embeddings(batch_size: int = 50) -> int:
    """Compute and store embeddings for L0 layers that don't have them yet.

    Returns the number of embeddings generated.
    """
    count = 0
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, substrate_id, content FROM substrate_layers
               WHERE layer = 'L0' AND embedding IS NULL
               ORDER BY generated_at DESC
               LIMIT ?""",
            (batch_size,),
        ).fetchall()

    for row_id, substrate_id, content in rows:
        if not content:
            continue
        embedding = _get_embedding(content)
        if embedding:
            emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
            with get_conn() as conn:
                conn.execute(
                    "UPDATE substrate_layers SET embedding = ?::vector, model_used = ? WHERE id = ?",
                    (emb_str, _EMBEDDING_MODEL, row_id),
                )
            count += 1
            logger.info("backfill_embeddings: %s (%d/%d)", substrate_id[:12], count, len(rows))
        else:
            logger.warning("backfill_embeddings: failed for %s", substrate_id[:12])

    logger.info("backfill_embeddings: generated %d embeddings", count)
    return count
