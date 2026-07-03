"""内容整合 + 落库 — 去重机制第②③步。

② 整合: 判为同点的一簇 A仓 KU → 一个 refined_ku 的 contributions[](各留原语言、标出处)。
   原子性预算: facet 数超阈值 → 该拆成多个 KU(信号), 不拼肥一个节点。
③ 落库: 写 rf.refined_ku(contributions 真身 + point/point_zh; natural_text 派生渲染后置)。
命门: 宁冗余不误删——相同片段丢、不同片段补, 拿不准当"不同"保留。
"""

from __future__ import annotations
import re

try:
    import ulid  # KU id 用 ULID(有序); 缺包回退 uuid4
except ImportError:
    ulid = None

FACET_BUDGET = 4  # 一个 KU 最多几个可陈述事项/facet, 超则触发拆分信号


def _lang(text: str) -> str:
    return "zh" if re.search(r"[一-鿿]", text or "") else "en"


def _new_ku_id() -> str:
    try:
        return str(ulid.new())
    except Exception:
        import uuid

        return uuid.uuid4().hex


def cluster_same(pairs: list[tuple]) -> list[set]:
    """union-find: 由 confirmed-same 对(a,b)聚成簇。只喂 verdict==same 的对(宁碎片)。"""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        parent[find(a)] = find(b)
    groups = {}
    for x in list(parent):
        groups.setdefault(find(x), set()).add(x)
    return list(groups.values())


def build_contributions(members: list[dict]) -> tuple[list, int]:
    """members: 同簇 A仓 KU [{raw_ku_id, book, version, facet, text}]。
    返回 (contributions, facet_count)。相同 facet+近同文本去一份(留出处)。"""
    contribs, seen_facets = [], set()
    for m in members:
        facet = m.get("facet") or "main"
        key = (facet, (m.get("text") or "").strip()[:80])
        if key in seen_facets:  # 相同片段(同 facet 近同文)→ 丢, 但出处并入上一条
            for c in contribs:
                if c["facet"] == facet:
                    c.setdefault("also_sources", []).append(m.get("raw_ku_id"))
                    break
            continue
        seen_facets.add(key)
        contribs.append(
            {
                "source_book_id": m.get("book"),
                "version": m.get("version", 1),
                "raw_ku_id": m.get("raw_ku_id"),
                "facet": facet,
                "fragment_text": m.get("text"),
                "lang": _lang(m.get("text")),
            }
        )
    facet_count = len({c["facet"] for c in contribs})
    return contribs, facet_count


def needs_split(facet_count: int) -> bool:
    """原子性预算: facet 数超阈值 → 该拆多个 KU(节点不肥)。"""
    return facet_count > FACET_BUDGET


def render_zh(contributions: list) -> str:
    """显示渲染: contributions 原语言片段拼装(en 片段 en→zh 是前端后置事, 此处暂留原文)。"""
    parts = []
    for c in contributions:
        f, t = c.get("facet"), (c.get("fragment_text") or "").strip()
        if t:
            parts.append(f"【{f}】{t}" if f and f != "main" else t)
    return "\n".join(parts)


def embed_text(contributions: list) -> str:
    """B仓独立向量的编码输入: 合并后干净内容(原语言片段, BGE-M3 多语种直接编)。"""
    return " ".join((c.get("fragment_text") or "").strip() for c in contributions).strip()


async def persist_refined_ku(
    conn,
    *,
    point,
    point_zh,
    ku_type,
    contributions,
    facet_count,
    embedding=None,
    natural_text_zh=None,
    decision_id=None,
    ku_id=None,
) -> str:
    """落 rf.refined_ku(contributions 真身 + B仓独立向量 embedding + 中文渲染)。返回 ku_id。"""
    import json

    ku_id = ku_id or _new_ku_id()
    await conn.execute(
        """
        INSERT INTO rf.refined_ku
          (ku_id, point, point_zh, ku_type, contributions, facet_count, embedding, natural_text_zh, decision_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (ku_id) DO UPDATE SET contributions=EXCLUDED.contributions,
          facet_count=EXCLUDED.facet_count, embedding=EXCLUDED.embedding,
          natural_text_zh=EXCLUDED.natural_text_zh, updated_at=now()
        """,
        ku_id,
        point,
        point_zh,
        ku_type,
        json.dumps(contributions, ensure_ascii=False),
        facet_count,
        embedding,
        natural_text_zh,
        decision_id,
    )
    return ku_id
