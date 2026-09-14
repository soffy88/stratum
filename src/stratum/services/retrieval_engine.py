"""Retrieval Engine — 目录递归分层检索 (对标 OpenViking Directory-Recursive Retrieval).

核心算法:
  Step 1: 粗筛 — 对所有 L0 做向量搜索, 找到 top-N 相关目录/节点
  Step 2: 钻取 — 对命中目录的子节点 L1 做二次搜索
  Step 3: 加载 — 对最终命中节点加载 L2 全文

关键特性:
  - trajectory: 每步记录 (候选数, 命中数, 得分分布) — 可观测性核心
  - depth_control: 可指定检索深度 (L0-only, L0+L1, L0+L1+L2)
  - hybrid_search: 向量搜索 + BM25 关键词
  - rerank: 复用现有 LLM rerank (aii/service/retrieval.py)
"""

from __future__ import annotations

import logging
import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

from stratum.config import OLLAMA_BASE_URL
from stratum.db import get_conn

logger = logging.getLogger(__name__)
_OLLAMA_BASE = OLLAMA_BASE_URL


def _user_owner_ids(user_id: str | None) -> tuple[str | None, str | None]:
    """Return (raw_user_id, hashed_user_id) for substrate ownership filters."""
    if not user_id or user_id == "default":
        return None, None
    from stratum.utils.user_id_hash import hash_user_id

    return user_id, hash_user_id(user_id)


_LLM_MODEL = "qwen3-8b"

# BGE-M3 embedder — must match substrate_layers.embedding space (1024-dim, cosine)
_bge: Any | None = None


def _get_bge():
    global _bge
    if _bge is None:
        from oprim.embedding.bge_m3 import BgeM3Embedder

        _bge = BgeM3Embedder()
    return _bge


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class RetrievalStep:
    """Single step in the retrieval trajectory."""

    phase: str  # "coarse", "drill", "load", "rerank"
    candidates: int
    hits: int
    scores: list[float] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Single retrieval result."""

    uri: str
    node_type: str
    ref_id: str | None
    layer: str  # "L0", "L1", "L2"
    content: str
    score: float
    token_count: int = 0
    namespace: str = "global"  # global=权威库(B仓/项目) | personal=个人草稿
    fragment_id: str | None = None


@dataclass
class RetrievalResponse:
    """Complete retrieval response with trajectory."""

    query: str
    results: list[RetrievalResult]
    trajectory: list[RetrievalStep]
    total_ms: int
    trajectory_id: str | None = None


# ── Embedding ────────────────────────────────────────────────────────────────

_EMBED_DIM = 1024  # Must match substrate_layers.embedding vector dimension


def get_embedding(text: str) -> list[float] | None:
    """Get embedding vector for text using BGE-M3 — same space as substrate_layers.

    Truncates to _EMBED_DIM (1024) to match pgvector column.
    """
    try:
        text = text[:8000] if len(text) > 8000 else text
        emb = _get_bge().embed([text], dim=1024)
        if not emb or not emb[0]:
            return None
        vec = emb[0]
        return vec[:_EMBED_DIM] if len(vec) > _EMBED_DIM else vec
    except Exception as exc:
        logger.warning("retrieval_engine: BGE-M3 embedding failed: %s", exc)
        return None


# ── Vector search ────────────────────────────────────────────────────────────


def _vector_search_layers(
    query_embedding: list[float],
    layer: str = "L0",
    top_k: int = 50,
    scope_uri: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """Search substrate_layers by vector similarity using pgvector.

    When user_id is set, only returns layers for substrates owned by that user
    (raw JWT sub or hash_user_id). Returns list of {substrate_id, content, token_count, score}.
    """
    if not query_embedding:
        return []

    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: tuple = ()
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = (uid, uh)

    with get_conn() as conn:
        try:
            rows = conn.execute(
                f"""SELECT sl.substrate_id, sl.content, sl.token_count,
                          1 - (sl.embedding <=> ?::vector) as score
                   FROM substrate_layers sl
                   JOIN substrates s ON s.id = sl.substrate_id
                   WHERE sl.layer = ? AND sl.embedding IS NOT NULL
                   {owner_sql}
                   ORDER BY sl.embedding <=> ?::vector
                   LIMIT ?""",
                (emb_str, layer, *owner_params, emb_str, top_k),
            ).fetchall()
            logger.debug("vector_search_layers: pgvector returned %d rows", len(rows))
            return [
                {"substrate_id": r[0], "content": r[1], "token_count": r[2], "score": float(r[3])}
                for r in rows
            ]
        except Exception as exc:
            # Never materialise and score the canonical corpus in Python. A
            # missing/broken pgvector index is an observable retrieval failure,
            # not permission to fall back to an unbounded scan.
            logger.warning("vector_search_layers pgvector failed: %s", exc)
            return []


# ── Text search (BM25-like) ─────────────────────────────────────────────────


def _text_search_layers(
    query: str, layer: str = "L0", top_k: int = 50, user_id: str | None = None
) -> list[dict]:
    """Use PostgreSQL's indexed trigram search for layer text.

    When user_id is set, only searches layers owned by that user.
    Returns list of {substrate_id, content, token_count, score}.
    """
    if not query:
        return []

    # Split query into terms
    terms = [t.strip() for t in query.split() if len(t.strip()) > 1]
    if not terms:
        return []

    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: list = []
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = [uid, uh]

    with get_conn() as conn:
        conditions = " OR ".join("sl.content ILIKE ?" for _ in terms)
        score_sql = " + ".join("CASE WHEN sl.content ILIKE ? THEN 1 ELSE 0 END" for _ in terms)
        patterns = [f"%{t}%" for t in terms]
        params = patterns + [len(terms)] + patterns + [layer] + owner_params + [top_k]

        try:
            rows = conn.execute(
                f"""SELECT sl.substrate_id, sl.content, sl.token_count,
                           ({score_sql})::double precision / ? AS score
                    FROM substrate_layers sl
                    JOIN substrates s ON s.id = sl.substrate_id
                    WHERE ({conditions}) AND sl.layer = ?
                    {owner_sql}
                    ORDER BY score DESC, sl.substrate_id
                    LIMIT ?""",
                tuple(params),
            ).fetchall()
        except Exception as exc:
            logger.warning("text_search failed: %s", exc)
            return []

    return [
        {"substrate_id": r[0], "content": r[1], "token_count": r[2], "score": float(r[3])}
        for r in rows
    ]


# ── Canonical fragment/metadata channels ────────────────────────────────────


def _normalise_retrieval_text(value: str | None) -> str:
    """Normalise user text for exact/lexical retrieval without losing CJK."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "").casefold()).strip()


def _compact_retrieval_text(value: str | None) -> str:
    """Remove punctuation/spacing for robust title and phrase comparisons."""
    return re.sub(r"[^\w\u3400-\u9fff]+", "", _normalise_retrieval_text(value))


def _retrieval_terms(value: str | None) -> list[str]:
    """Return word terms plus CJK bigrams for punctuation/footnote-tolerant search."""
    normalised = _normalise_retrieval_text(value)
    terms = re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", normalised)
    cjk_grams: list[str] = []
    for term in terms:
        if re.fullmatch(r"[\u3400-\u9fff]+", term) and len(term) >= 2:
            cjk_grams.extend(term[i : i + 2] for i in range(len(term) - 1))
    # Keep the original CJK terms first; bigrams make OCR footnotes and
    # punctuation between characters searchable without a new tokenizer.
    output: list[str] = []
    for term in terms + cjk_grams:
        if len(term) > 1 and term not in output:
            output.append(term)
    return output


def _lexical_match_score(query: str, text: str) -> tuple[float, bool]:
    """Score a fragment and report whether it is an exact/high-confidence hit."""
    qcompact = _compact_retrieval_text(query)
    tcompact = _compact_retrieval_text(text)
    exact = bool(qcompact and len(qcompact) >= 4 and qcompact in tcompact)
    terms = _retrieval_terms(query)
    if not terms:
        # Some OCR/PDF fixtures contain opaque control-character text. Keep
        # those queries searchable without treating the corrupted string as a
        # normal word: compare short windows after whitespace removal.
        qopaque = "".join(_normalise_retrieval_text(query).split())
        top_ratio = 0.0
        if len(qopaque) >= 8:
            compact_text = "".join(_normalise_retrieval_text(text).split())
            window = len(qopaque) + 4
            for start in range(0, max(len(compact_text) - len(qopaque) + 1, 1), 1):
                candidate = compact_text[start : start + window]
                top_ratio = max(
                    top_ratio,
                    SequenceMatcher(None, qopaque, candidate, autojunk=False).ratio(),
                )
            return top_ratio * 100.0, top_ratio >= 0.85
        return 0.0, exact
    matched = sum(1 for term in terms if term in tcompact)
    coverage = matched / len(terms)
    cjk_terms = [term for term in terms if re.fullmatch(r"[\u3400-\u9fff]+", term)]
    cjk_coverage = (
        sum(1 for term in cjk_terms if term in tcompact) / len(cjk_terms) if cjk_terms else 0.0
    )
    # A CJK phrase can have a footnote marker between two characters. Treat a
    # high bigram-coverage match as an exact lexical signal, but not a generic
    # one-token semantic match.
    protected_phrase = bool(len(cjk_terms) >= 3 and cjk_coverage >= 0.75)
    return (200.0 if exact else 0.0) + coverage * 10.0, exact or protected_phrase


def _text_search_chunks(query: str, top_k: int = 50, user_id: str | None = None) -> list[dict]:
    """Search canonical substrate fragments with Unicode/CJK-aware lexical scoring."""
    terms = _retrieval_terms(query)
    if not terms:
        return []
    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: list[Any] = []
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = [uid, uh]
    # PostgreSQL's pg_trgm index supports the ILIKE predicates below. Match
    # scoring and ordering also stay in SQL; Python only normalises the query
    # terms and materialises the bounded result set.
    search_terms = terms[:32]
    conditions = " OR ".join("c.text ILIKE ?" for _ in search_terms)
    patterns = [f"%{term}%" for term in search_terms]
    score_sql = " + ".join("CASE WHEN c.text ILIKE ? THEN 1 ELSE 0 END" for _ in search_terms)
    exact_sql = "c.text ILIKE ?" if query.strip() else "FALSE"
    params: list[Any] = patterns + [len(search_terms)]
    params += [f"%{query.strip()}%"] if query.strip() else []
    params += patterns
    params.extend(owner_params)
    with get_conn() as conn:
        try:
            if conditions:
                rows = conn.execute(
                    f"""SELECT c.id, c.substrate_id, c.text, c.chunk_idx,
                               ({score_sql})::double precision / ? AS score,
                               {exact_sql} AS exact_match
                        FROM substrate_chunk c
                        JOIN substrates s ON s.id = c.substrate_id
                        WHERE ({conditions}) {owner_sql}
                        ORDER BY score DESC, c.substrate_id, c.chunk_idx
                        LIMIT ?""",
                    tuple(params + [max(top_k * 20, 200)]),
                ).fetchall()
        except Exception as exc:
            logger.warning("text_search_chunks failed: %s", exc)
            return []
    return [
        {
            "substrate_id": row[1],
            "fragment_id": row[0],
            "content": row[2] or "",
            "token_count": len(row[2] or "") // 4,
            "score": float(row[4]),
            "exact_match": bool(row[5]),
            "chunk_idx": row[3],
        }
        for row in rows[:top_k]
    ]


def _vector_search_chunks(
    query_embedding: list[float], top_k: int = 50, user_id: str | None = None
) -> list[dict]:
    """Search canonical fragments whose BGE-M3 vectors are available."""
    if not query_embedding:
        return []
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: tuple[Any, ...] = ()
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = (uid, uh)
    with get_conn() as conn:
        try:
            rows = conn.execute(
                f"""SELECT c.id, c.substrate_id, c.text, c.chunk_idx,
                           1 - (c.embedding <=> ?::vector) AS score
                    FROM substrate_chunk c
                    JOIN substrates s ON s.id = c.substrate_id
                    WHERE c.embedding IS NOT NULL {owner_sql}
                    ORDER BY c.embedding <=> ?::vector
                    LIMIT ?""",
                (emb_str, *owner_params, emb_str, top_k),
            ).fetchall()
        except Exception as exc:
            logger.warning("vector_search_chunks failed: %s", exc)
            return []
    return [
        {
            "substrate_id": row[1],
            "fragment_id": row[0],
            "content": row[2] or "",
            "token_count": len(row[2] or "") // 4,
            "score": float(row[4]),
            "chunk_idx": row[3],
        }
        for row in rows
    ]


def _contains_query_phrase(query: str, phrase: str) -> bool:
    """Match a canonical claim statement as a phrase, not a substring prefix."""
    query_text = _normalise_retrieval_text(query)
    phrase_text = _normalise_retrieval_text(phrase)
    if not query_text or not phrase_text:
        return False
    pattern = re.escape(phrase_text).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<!\w){pattern}(?!\w)", query_text))


def _claim_provenance_search(query: str, top_k: int = 20, user_id: str | None = None) -> list[dict]:
    """Resolve exact canonical claim statements to their evidenced sources.

    Claims are canonical records, not benchmark fixtures. This channel makes a
    claim question retrievable through the existing Claim -> Evidence -> Source
    provenance path instead of pretending the statement is present in a PDF's
    title-only L0 summary.
    """
    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: tuple[Any, ...] = ()
    if uid is not None:
        owner_sql = """ AND (c.user_id = ? OR c.user_id = ?)
                         AND (e.user_id = ? OR e.user_id = ?)
                         AND (s.user_id = ? OR s.user_id = ?)"""
        owner_params = (uid, uh, uid, uh, uid, uh)
    with get_conn() as conn:
        try:
            rows = conn.execute(
                f"""SELECT c.id, c.statement, e.substrate_id, e.quote
                    FROM knowledge_claims c
                    JOIN claim_evidence ce ON ce.claim_id = c.id
                    JOIN evidence e ON e.id = ce.evidence_id
                    JOIN substrates s ON s.id = e.substrate_id
                    WHERE c.deleted_at IS NULL {owner_sql}
                    ORDER BY c.id, e.id""",
                owner_params,
            ).fetchall()
        except Exception as exc:
            logger.warning("claim_provenance_search failed: %s", exc)
            return []
    results: list[dict] = []
    seen: set[str] = set()
    for claim_id, statement, substrate_id, quote in rows:
        if substrate_id in seen or not _contains_query_phrase(query, statement or ""):
            continue
        seen.add(substrate_id)
        results.append(
            {
                "substrate_id": substrate_id,
                "content": quote or statement or "",
                "token_count": len(quote or statement or "") // 4,
                "score": 100.0,
                "exact_match": True,
                "claim_id": claim_id,
                "channel": "claim",
            }
        )
        if len(results) >= top_k:
            break
    return results


def _title_metadata_search(query: str, top_k: int = 50, user_id: str | None = None) -> list[dict]:
    """Search title/path metadata through indexed PostgreSQL predicates.

    This deliberately returns no rows for an un-tokenisable query instead of
    falling back to a full metadata-table scan.
    """
    terms = _retrieval_terms(query)
    if not terms:
        return []
    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: tuple[Any, ...] = ()
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = (uid, uh)
    conditions = " OR ".join("s.title ILIKE ? OR s.source_path ILIKE ?" for _ in terms)
    score_sql = " + ".join(
        "CASE WHEN s.title ILIKE ? OR s.source_path ILIKE ? THEN 1 ELSE 0 END" for _ in terms
    )
    patterns = [value for term in terms for value in (f"%{term}%", f"%{term}%")]
    with get_conn() as conn:
        try:
            rows = conn.execute(
                f"""SELECT s.id, s.title, s.source_path,
                           ({score_sql})::double precision / ? AS score
                    FROM substrates s
                    WHERE ({conditions}) {owner_sql}
                    ORDER BY score DESC, s.id
                    LIMIT ?""",
                tuple(patterns + [len(terms)] + patterns + list(owner_params) + [top_k]),
            ).fetchall()
        except Exception as exc:
            logger.warning("title_metadata_search failed: %s", exc)
            return []
    return [
        {
            "substrate_id": row[0],
            "content": row[1] or row[2] or row[0],
            "token_count": len(row[1] or "") // 4,
            "score": float(row[3]),
            "exact_match": query.casefold() in f"{row[1] or ''} {row[2] or ''}".casefold(),
            "channel": "title",
        }
        for row in rows
    ]


def _rrf_merge_channels(
    channels: dict[str, list[dict]],
    top_k: int = 30,
    rrf_k: int = 60,
    protect_exact: bool = True,
) -> list[dict]:
    """Merge ranked channels with RRF and optionally protect exact matches."""
    merged: dict[str, dict] = {}
    exact_priority = {"claim": 4, "title": 3, "lexical_chunk": 3} if protect_exact else {}
    for channel, rows in channels.items():
        for rank, row in enumerate(rows, 1):
            substrate_id = row.get("substrate_id")
            if not substrate_id:
                continue
            candidate = merged.setdefault(
                substrate_id,
                {
                    "substrate_id": substrate_id,
                    "content": row.get("content") or "",
                    "token_count": row.get("token_count") or 0,
                    "score": 0.0,
                    "rrf_score": 0.0,
                    "fragment_id": row.get("fragment_id"),
                    "exact_priority": 0,
                    "channels": [],
                },
            )
            candidate["rrf_score"] += 1.0 / (rrf_k + rank)
            candidate["channels"].append(channel)
            candidate["score"] = max(float(candidate["score"]), float(row.get("score") or 0.0))
            if row.get("content") and not candidate["content"]:
                candidate["content"] = row["content"]
            if row.get("fragment_id") and not candidate.get("fragment_id"):
                candidate["fragment_id"] = row["fragment_id"]
            if protect_exact and row.get("exact_match"):
                candidate["exact_priority"] = max(
                    candidate["exact_priority"], exact_priority.get(channel, 2)
                )
    return sorted(
        merged.values(),
        key=lambda row: (
            -row["exact_priority"],
            -row["rrf_score"],
            -row["score"],
            row["substrate_id"],
        ),
    )[:top_k]


# ── Directory-aware retrieval ────────────────────────────────────────────────


def _search_personal_notes(query: str, top_k: int = 5) -> list[RetrievalResult]:
    """个人草稿区检索(~/.stratum/notes/*.md) — 关键词匹配 + 简单评分。

    设计(P3): 低门槛碎片区, 不做向量/不做图谱; 结果标注 namespace=personal,
    权重上限 0.6(低于 global 权威命中), 防污染核心库。
    """
    notes_dir = Path.home() / ".stratum" / "notes"
    if not notes_dir.is_dir():
        return []
    terms = [t.lower() for t in re.findall(r"[\w\u4e00-\u9fff]{2,}", query or "")]
    if not terms:
        return []
    hits: list[RetrievalResult] = []
    for f in sorted(notes_dir.glob("*.md"))[:200]:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")[:20000]
        except OSError:
            continue
        low = text.lower()
        matched = sum(1 for t in terms if t in low)
        if matched == 0:
            continue
        score = min(0.6, 0.25 + 0.07 * matched + 0.01 * min(len(text) // 500, 3))
        snippet = text[:400].replace("\n", " ")[:300]
        hits.append(
            RetrievalResult(
                uri=f"pnote://{f.stem}",
                node_type="note",
                ref_id=f.stem,
                layer="L0",
                content=snippet,
                score=score,
                token_count=len(snippet) // 4,
                namespace="personal",
            )
        )
    hits.sort(key=lambda r: r.score, reverse=True)
    return hits[:top_k]


def _get_directory_context(substrate_id: str) -> dict[str, Any] | None:
    """Get directory context for a substrate."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT cd.uri, cd.parent_id, pd.uri as parent_uri, pd.l0_content as dir_l0
               FROM context_directory cd
               LEFT JOIN context_directory pd ON cd.parent_id = pd.id
               WHERE cd.ref_id = ? AND cd.node_type = 'substrate'""",
            (substrate_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "uri": row[0],
        "parent_uri": row[2],
        "dir_l0": row[3],
    }


def _get_sibling_kus(parent_uri: str, limit: int = 5) -> list[dict]:
    """Get sibling KUs in the same directory."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT cd.uri, cd.ref_id, cd.l0_content
               FROM context_directory cd
               JOIN context_directory pd ON cd.parent_id = pd.id
               WHERE pd.uri = ? AND cd.node_type = 'ku'
               LIMIT ?""",
            (parent_uri, limit),
        ).fetchall()
    return [{"uri": r[0], "ku_id": r[1], "l0": r[2]} for r in rows]


def _get_directory_siblings(parent_uri: str, exclude_ids: set[str], limit: int = 5) -> list[dict]:
    """Get sibling substrate L0 summaries from the same directory.

    Used for directory-recursive retrieval: when a substrate matches,
    include its neighbors for richer context.
    """
    if not parent_uri:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT cd.uri, cd.ref_id, cd.l0_content
               FROM context_directory cd
               JOIN context_directory pd ON cd.parent_id = pd.id
               WHERE pd.uri = ? AND cd.node_type = 'substrate'
               ORDER BY cd.uri
               LIMIT ?""",
            (parent_uri, limit + len(exclude_ids)),
        ).fetchall()
    results = []
    for uri, ref_id, l0 in rows:
        if ref_id not in exclude_ids and l0:
            results.append({"uri": uri, "substrate_id": ref_id, "l0": l0})
            if len(results) >= limit:
                break
    return results


# ── LLM Rerank ──────────────────────────────────────────────────────────────


def _llm_rerank(
    query: str, candidates: list[RetrievalResult], top_k: int = 10
) -> list[RetrievalResult]:
    """Re-rank candidates using Ollama LLM.

    Asks LLM to score each candidate's relevance to query, returns re-sorted list.
    Falls back to original order on any failure.
    """
    if not candidates:
        return []
    if len(candidates) <= 1:
        return candidates

    import json as _json

    # Build candidate list for LLM
    items = []
    for i, r in enumerate(candidates[:20]):  # Limit to 20 for LLM context
        snippet = r.content[:200].replace("\n", " ").strip()
        items.append(f"[{i}] {r.uri.split('/')[-1][:50]}: {snippet}")

    items_text = "\n".join(items)
    prompt = (
        f"Query: {query}\n\n"
        f"Candidates:\n{items_text}\n\n"
        f"Score each candidate's relevance to the query (0-10, 10=perfect match). "
        f'Return ONLY valid JSON: {{"scores":[{{"id":<int>,"score":<float>}}]}}'
    )

    try:
        resp = httpx.post(
            f"{_OLLAMA_BASE}/api/chat",
            json={
                "model": _LLM_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise retrieval re-ranker. Output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        result = resp.json().get("message", {}).get("content", "").strip()

        # Strip thinking tags from qwen3
        if "" in result:
            result = re.sub(r"", "", result, flags=re.DOTALL).strip()

        # Parse JSON response
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if not match:
            logger.warning("rerank: no JSON found in LLM response")
            return candidates[:top_k]

        data = _json.loads(match.group(0))
        scores_list = data.get("scores", [])

        # Build id→score mapping
        score_map = {}
        for entry in scores_list:
            try:
                idx = int(entry["id"])
                score = float(entry.get("score", 0))
                if 0 <= idx < len(candidates):
                    score_map[idx] = score
            except (KeyError, ValueError, TypeError):
                continue

        if not score_map:
            logger.warning("rerank: no valid scores parsed")
            return candidates[:top_k]

        # Create re-ranked list with updated scores
        reranked = []
        for idx in sorted(score_map.keys(), key=lambda i: score_map[i], reverse=True):
            r = candidates[idx]
            # Update score (normalize to 0-1 range)
            r.score = score_map[idx] / 10.0
            reranked.append(r)

        # Append candidates not scored by LLM (at the end)
        scored_ids = set(score_map.keys())
        for i, r in enumerate(candidates):
            if i not in scored_ids:
                reranked.append(r)

        logger.debug("rerank: re-sorted %d candidates", len(reranked))
        return reranked[:top_k]

    except Exception as exc:
        logger.warning("rerank failed: %s", exc)
        return candidates[:top_k]


# ── Main retrieval ──────────────────────────────────────────────────────────


def retrieve(
    query: str,
    max_depth: int = 2,
    top_k: int = 10,
    layers: list[str] | None = None,
    rerank: bool = False,
    user_id: str = "default",
    namespace: str = "global",
    budget_tokens: int | None = None,
    query_embedding: list[float] | None = None,
) -> RetrievalResponse:
    """Directory-recursive retrieval with trajectory tracking.

    Args:
        query: Search query
        max_depth: Max retrieval depth (1=L0 only, 2=L0+L1, 3=L0+L1+L2)
        top_k: Number of results to return
        layers: Specific layers to retrieve (overrides max_depth)
        rerank: Whether to apply LLM reranking
        user_id: User ID for trajectory logging
        namespace: "global"(权威库) | "personal"(个人草稿) | "all"(联邦合并)
        budget_tokens: 结果 token 预算(book-to-skill 启发: 查询成本与答案成正比,
            默认 None=不限制; 超预算截断低分项)

    Returns:
        RetrievalResponse with results and trajectory
    """
    start_time = time.time()
    trajectory: list[RetrievalStep] = []

    if layers is None:
        if max_depth == 1:
            layers = ["L0"]
        elif max_depth == 2:
            layers = ["L0", "L1"]
        else:
            layers = ["L0", "L1", "L2"]

    # Step 1: Get query embedding
    query_emb = query_embedding if query_embedding is not None else get_embedding(query)

    # Step 2: Coarse search — dense/lexical source summaries plus canonical
    # fragments and provenance metadata. L0 remains useful for the broad
    # corpus, while chunks carry the actual passage-level evidence.
    vector_results = (
        _vector_search_layers(query_emb, "L0", top_k=50, user_id=user_id) if query_emb else []
    )
    chunk_vector_results = (
        _vector_search_chunks(query_emb, top_k=50, user_id=user_id) if query_emb else []
    )
    text_results = _text_search_layers(query, "L0", top_k=50, user_id=user_id)
    chunk_text_results = _text_search_chunks(query, top_k=50, user_id=user_id)
    claim_results = _claim_provenance_search(query, top_k=20, user_id=user_id)
    title_results = _title_metadata_search(query, top_k=50, user_id=user_id)

    channel_results = {
        "dense_l0": vector_results,
        "dense_chunk": chunk_vector_results,
        "lexical_l0": text_results,
        "lexical_chunk": chunk_text_results,
        "claim": claim_results,
        "title": title_results,
    }
    coarse_results = _rrf_merge_channels(channel_results, top_k=30)

    trajectory.append(
        RetrievalStep(
            phase="coarse",
            candidates=sum(len(rows) for rows in channel_results.values()),
            hits=len(coarse_results),
            scores=[r["score"] for r in coarse_results[:10]],
            details={
                "dense_l0_hits": len(vector_results),
                "dense_chunk_hits": len(chunk_vector_results),
                "lexical_l0_hits": len(text_results),
                "lexical_chunk_hits": len(chunk_text_results),
                "claim_hits": len(claim_results),
                "title_hits": len(title_results),
                "fusion": "rrf_with_exact_protection",
            },
        )
    )

    # Step 2b: Directory-recursive expansion — boost siblings of top hits
    merged: dict[str, dict] = {r["substrate_id"]: r for r in coarse_results}
    expanded_ids = set()
    for r in coarse_results[:5]:
        sid = r["substrate_id"]
        dir_ctx = _get_directory_context(sid)
        if dir_ctx and dir_ctx.get("parent_uri"):
            parent_uri = dir_ctx["parent_uri"]
            # Get sibling L0 summaries (exclude already-matched substrates)
            exclude = {c["substrate_id"] for c in coarse_results}
            siblings = _get_directory_siblings(parent_uri, exclude, limit=3)
            for sib in siblings:
                sib_id = sib["substrate_id"]
                if sib_id not in expanded_ids and sib_id not in exclude:
                    expanded_ids.add(sib_id)
                    # Boost sibling with discounted score
                    boosted_score = r["score"] * 0.7
                    merged[sib_id] = {
                        "substrate_id": sib_id,
                        "content": sib["l0"],
                        "token_count": len(sib["l0"]) // 4,
                        "score": boosted_score,
                        "uri": sib["uri"],
                        "is_sibling": True,
                    }

    if expanded_ids:
        # Re-sort with expanded results
        coarse_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:30]
        trajectory.append(
            RetrievalStep(
                phase="expand",
                candidates=len(expanded_ids),
                hits=len(expanded_ids),
                scores=[merged[sid]["score"] for sid in list(expanded_ids)[:5]],
                details={"siblings_added": len(expanded_ids)},
            )
        )

    # Step 3: Drill down — get directory context + L1 for top results
    enriched_results: list[RetrievalResult] = []
    for r in coarse_results[:15]:
        sid = r["substrate_id"]
        dir_ctx = _get_directory_context(sid)

        # Add L0 result
        enriched_results.append(
            RetrievalResult(
                uri=dir_ctx["uri"] if dir_ctx else f"viking://resources/其他/{sid}",
                node_type="substrate",
                ref_id=sid,
                layer="L0",
                content=r["content"],
                score=r["score"],
                token_count=r["token_count"],
                fragment_id=r.get("fragment_id"),
            )
        )

        # If L1 requested, get it
        if "L1" in layers:
            with get_conn() as conn:
                l1_row = conn.execute(
                    "SELECT content, token_count FROM substrate_layers WHERE substrate_id=? AND layer='L1'",
                    (sid,),
                ).fetchone()
            if l1_row:
                enriched_results.append(
                    RetrievalResult(
                        uri=dir_ctx["uri"] if dir_ctx else f"viking://resources/其他/{sid}",
                        node_type="substrate",
                        ref_id=sid,
                        layer="L1",
                        content=l1_row[0],
                        score=r["score"] * 0.9,  # slight discount for deeper layer
                        token_count=l1_row[1],
                    )
                )

    trajectory.append(
        RetrievalStep(
            phase="drill",
            candidates=len(coarse_results[:15]),
            hits=len(enriched_results),
            scores=[r.score for r in enriched_results[:10]],
        )
    )

    # Step 4: Load L2 if requested (only for top-k)
    if "L2" in layers:
        top_substrate_ids = [r.ref_id for r in enriched_results if r.layer == "L0"][:top_k]
        for sid in top_substrate_ids:
            with get_conn() as conn:
                l2_row = conn.execute(
                    "SELECT content, token_count FROM substrate_layers WHERE substrate_id=? AND layer='L2'",
                    (sid,),
                ).fetchone()
            if l2_row:
                dir_ctx = _get_directory_context(sid)
                enriched_results.append(
                    RetrievalResult(
                        uri=dir_ctx["uri"] if dir_ctx else f"viking://resources/其他/{sid}",
                        node_type="substrate",
                        ref_id=sid,
                        layer="L2",
                        content=l2_row[0][:3000],  # Truncate L2 to save tokens
                        score=next(
                            (
                                r.score
                                for r in enriched_results
                                if r.ref_id == sid and r.layer == "L0"
                            ),
                            0.5,
                        )
                        * 0.8,
                        token_count=min(l2_row[1], 750),
                    )
                )

        trajectory.append(
            RetrievalStep(
                phase="load",
                candidates=len(top_substrate_ids),
                hits=len([r for r in enriched_results if r.layer == "L2"]),
                scores=[r.score for r in enriched_results if r.layer == "L2"][:10],
            )
        )

    # Step 5: Optional rerank (using Ollama LLM)
    if rerank and len(enriched_results) > 5:
        l0_results = [r for r in enriched_results if r.layer == "L0"]
        reranked = _llm_rerank(query, l0_results, top_k=min(top_k, len(l0_results)))
        if reranked:
            # Reorder: reranked L0s first, then other layers
            rerank_ids = {r.ref_id for r in reranked}
            other_results = [
                r for r in enriched_results if r.ref_id not in rerank_ids or r.layer != "L0"
            ]
            enriched_results = reranked + other_results
            trajectory.append(
                RetrievalStep(
                    phase="rerank",
                    candidates=len(l0_results),
                    hits=len(reranked),
                    scores=[r.score for r in reranked[:10]],
                )
            )

    # Step 5b: Personal 层联邦检索(P3) — namespace ∈ {personal, all}
    # 个人草稿(~/.stratum/notes/*.md)低门槛碎片区: 只做关键词匹配, 结果标注
    # namespace=personal 且权重打折(global 权威优先); 永不进入图谱/规范构建。
    if namespace in ("personal", "all"):
        personal_hits = _search_personal_notes(query, top_k=5)
        if personal_hits:
            trajectory.append(
                RetrievalStep(
                    phase="personal",
                    candidates=len(personal_hits),
                    hits=len(personal_hits),
                    scores=[r.score for r in personal_hits[:10]],
                    details={"namespace": "personal"},
                )
            )
            enriched_results.extend(personal_hits)
    if namespace == "personal":
        enriched_results = [r for r in enriched_results if r.namespace == "personal"]

    # Sort by score and limit (global 权威 + personal 草稿混排时 global 权重已内建)
    enriched_results.sort(key=lambda r: r.score, reverse=True)
    final_results = enriched_results[: top_k * len(layers)]
    # ★Token 预算(book-to-skill 启发 P1): 查询成本与答案成正比
    # 按 score 顺序累计 token_count, 超预算截断低分项(保高分权威内容)
    if budget_tokens and budget_tokens > 0:
        used = 0
        kept: list[RetrievalResult] = []
        for r in final_results:
            if used + (r.token_count or 0) > budget_tokens and kept:
                trajectory.append(
                    RetrievalStep(
                        phase="budget",
                        candidates=len(final_results),
                        hits=len(kept),
                        details={
                            "budget_tokens": budget_tokens,
                            "used_tokens": used,
                            "truncated": len(final_results) - len(kept),
                        },
                    )
                )
                break
            used += r.token_count or 0
            kept.append(r)
        final_results = kept

    total_ms = int((time.time() - start_time) * 1000)

    # Store trajectory
    trajectory_id = _store_trajectory(
        query, query_emb, final_results, trajectory, total_ms, user_id
    )

    return RetrievalResponse(
        query=query,
        results=final_results,
        trajectory=trajectory,
        total_ms=total_ms,
        trajectory_id=trajectory_id,
    )


# ── Trajectory storage ────────────────────────────────────────────────────────


def _store_trajectory(
    query: str,
    query_emb: list[float] | None,
    results: list[RetrievalResult],
    trajectory: list[RetrievalStep],
    total_ms: int,
    user_id: str,
) -> str:
    """Store retrieval trajectory in DB."""
    import hashlib

    traj_id = hashlib.sha256(f"{query}-{time.time()}".encode()).hexdigest()[:24]

    results_json = [
        {
            "uri": r.uri,
            "layer": r.layer,
            "score": round(r.score, 4),
            "content_preview": r.content[:200],
            "token_count": r.token_count,
        }
        for r in results
    ]
    trajectory_json = [
        {
            "phase": s.phase,
            "candidates": s.candidates,
            "hits": s.hits,
            "scores": [round(x, 4) for x in s.scores[:10]],
            "details": s.details,
        }
        for s in trajectory
    ]

    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO retrieval_trajectories
                   (id, user_id, query, query_embedding, results, trajectory, total_ms, result_count)
                   VALUES (?, ?, ?, ?, ?::jsonb, ?::jsonb, ?, ?)""",
                (
                    traj_id,
                    user_id,
                    query,
                    query_emb,  # psycopg2 should handle float[] → vector
                    json.dumps(results_json, ensure_ascii=False),
                    json.dumps(trajectory_json, ensure_ascii=False),
                    total_ms,
                    len(results),
                ),
            )
    except Exception as exc:
        logger.warning("store_trajectory failed: %s", exc)
        return ""

    return traj_id


def get_trajectory(trajectory_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    """Get stored trajectory by ID. When user_id set, only return own trajectories."""
    with get_conn() as conn:
        if user_id is not None:
            row = conn.execute(
                """SELECT query, results, trajectory, total_ms, result_count, created_at
                   FROM retrieval_trajectories WHERE id = ? AND user_id = ?""",
                (trajectory_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT query, results, trajectory, total_ms, result_count, created_at
                   FROM retrieval_trajectories WHERE id = ?""",
                (trajectory_id,),
            ).fetchone()
    if not row:
        return None
    return {
        "query": row[0],
        "results": row[1],
        "trajectory": row[2],
        "total_ms": row[3],
        "result_count": row[4],
        "created_at": str(row[5]),
    }


def get_recent_trajectories(user_id: str = "default", limit: int = 10) -> list[dict]:
    """Get recent retrieval trajectories."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, query, total_ms, result_count, created_at
               FROM retrieval_trajectories
               WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [
        {"id": r[0], "query": r[1], "total_ms": r[2], "result_count": r[3], "created_at": str(r[4])}
        for r in rows
    ]
