"""
GraphRAG Stage A: 入库后从 derivative.content 抽实体+关系写入 graph_entities/graph_relations.

调用链（全 3O 主库元素，不动主库）:
  derivative.content (markdown)
  → oprim.structural_chunk → chunks
  → oprim.llm_call (抽实体+关系 JSON)
  → dao.graph.upsert_entity / upsert_relation
"""
import asyncio
import json
import logging
from stratum.db import get_conn
from stratum.dao.graph import upsert_entity, upsert_relation

log = logging.getLogger(__name__)

_EXTRACT_PROMPT = """从以下文本中抽取实体和关系。

要求:
- entities: 列出重要概念/方法/人物/系统，每个含 name(中英文均可), type(concept/method/person/system), description(一句话)
- relations: 列出实体间关系，每个含 source, target, relation_type(affects/defines/part_of/supports/contradicts/uses), description

返回严格 JSON，不加任何说明:
{
  "entities": [{"name": "...", "type": "...", "description": "..."}],
  "relations": [{"source": "...", "target": "...", "relation_type": "...", "description": "..."}]
}

文本:
"""

_MAX_CHUNK_CHARS = 2000
_MAX_ENTITIES_PER_SUBSTRATE = 30


async def build_graph_from_substrate(substrate_id: str, user_id_hash: str) -> dict:
    """
    Main entry: read derivative.content, chunk, extract entities+relations via LLM,
    write to graph tables.
    Returns {"entities_added": N, "relations_added": M}
    """
    from oprim import structural_chunk, llm_call

    # 1. 读 markdown derivative
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown'",
            (substrate_id,)
        ).fetchone()

    if not row or not row[0]:
        log.warning("graph_builder: no markdown derivative for %s", substrate_id)
        return {"entities_added": 0, "relations_added": 0}

    content = row[0]

    # 2. chunk（oprim.structural_chunk returns list of dicts with "content" key）
    raw_chunks = structural_chunk(
        text=content,
        min_chars=500,
        max_chars=_MAX_CHUNK_CHARS,
    )
    chunks: list[str] = []
    if raw_chunks:
        for c in raw_chunks:
            text = c.get("content", "") if isinstance(c, dict) else str(c)
            if text:
                chunks.append(text)
    if not chunks:
        chunks = [content[:_MAX_CHUNK_CHARS]]

    entities_added = 0
    relations_added = 0
    seen_entities: dict[str, str] = {}  # name → entity_id

    # 3. 每 chunk LLM 抽取（llm_call 是同步阻塞调用，run in thread）
    for chunk_text in chunks[:5]:
        try:
            resp = await asyncio.to_thread(
                llm_call,
                _EXTRACT_PROMPT + chunk_text,
                "qwen3_dashscope",
            )
            text = resp.text.strip().strip("```json").strip("```").strip()
            data = json.loads(text)
        except Exception as e:
            log.warning("graph_builder: LLM extract failed for chunk: %s", e)
            continue

        # 4. upsert entities
        for ent in data.get("entities", [])[:_MAX_ENTITIES_PER_SUBSTRATE]:
            name = ent.get("name", "").strip()
            if not name:
                continue
            eid = upsert_entity(
                user_id=user_id_hash,
                name=name,
                entity_type=ent.get("type", "concept"),
                description=ent.get("description"),
                substrate_id=substrate_id,
            )
            seen_entities[name] = eid
            entities_added += 1

        # 5. upsert relations（both endpoints must be in seen_entities）
        for rel in data.get("relations", []):
            src_name = rel.get("source", "").strip()
            tgt_name = rel.get("target", "").strip()
            if src_name not in seen_entities or tgt_name not in seen_entities:
                continue
            upsert_relation(
                user_id=user_id_hash,
                source_id=seen_entities[src_name],
                target_id=seen_entities[tgt_name],
                relation_type=rel.get("relation_type", "related"),
                description=rel.get("description"),
                substrate_id=substrate_id,
                confidence=0.7,
            )
            relations_added += 1

    log.info("graph_builder: substrate=%s entities=%d relations=%d",
             substrate_id, entities_added, relations_added)
    return {"entities_added": entities_added, "relations_added": relations_added}
