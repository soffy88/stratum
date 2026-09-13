"""Project real parser outputs into the production fragment/vector index.

The upload endpoint is the parser boundary.  This command performs the
existing production post-ingest projection (``oprim.structural_chunk`` plus
BGE-M3) for the substrate IDs returned by that endpoint; it does not create
or alter source records by hand.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path

PG = dict(
    host=os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
    port=int(os.environ.get("STRATUM_PG_PORT", "5435")),
    user=os.environ.get("STRATUM_PG_USER", "aii"),
    password=os.environ.get("STRATUM_PG_PASSWORD", "aii_safe_pass"),
    database=os.environ.get("STRATUM_PG_DB", "aii_kg"),
)
BATCH = int(os.environ.get("REEMBED_BATCH", "16"))
MIN_CHARS, MAX_CHARS = 500, 2000
FRAGMENT_VERSION = int(os.environ.get("STRATUM_FRAGMENT_VERSION", "1"))
PARSER_VERSION = os.environ.get("STRATUM_PARSER_VERSION", "structural_chunk-v1")


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _anchor_for(content: str, text: str) -> dict[str, object]:
    """Resolve a persisted fragment to an exact or approximate source range."""
    start = content.find(text)
    status = "exact"
    if start < 0:
        normalized_content = re.sub(r"\s+", " ", content)
        normalized_text = re.sub(r"\s+", " ", text).strip()
        normalized_start = normalized_content.find(normalized_text)
        if normalized_start >= 0:
            # The normalized offset is a stable enough source locator for the
            # markdown derivative; map it back to the original text.
            start = min(len(content), int(normalized_start * len(content) / max(len(normalized_content), 1)))
            status = "normalized"
        else:
            # structural_chunk can join page/paragraph boundaries.  Pick the
            # highest-overlap source paragraph and retain the approximation in
            # metadata instead of claiming quote-level exactness.
            needle = set(re.findall(r"[\w\u3400-\u9fff]{2,}", text.lower()))
            paragraphs = [item for item in re.split(r"\n\s*\n", content) if item.strip()]
            best = max(
                paragraphs,
                key=lambda item: len(needle & set(re.findall(r"[\w\u3400-\u9fff]{2,}", item.lower()))),
                default="",
            )
            start = content.find(best[:80]) if best else -1
            status = "approx"
    if start < 0:
        return {"anchor_status": "unresolved"}
    end = min(len(content), start + len(text))
    return {
        "start_pos": start,
        "end_pos": end,
        "anchor_status": status,
        "paragraph_index": content[:start].count("\n\n"),
    }


def _read_ids(args: argparse.Namespace) -> list[str]:
    values = list(args.substrate_id or [])
    if args.ids_file:
        payload = json.loads(Path(args.ids_file).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("substrate_ids", [])
        values.extend(str(item) for item in payload)
    return sorted(set(values))


async def _run(substrate_ids: list[str]) -> int:
    if not substrate_ids:
        raise SystemExit("no substrate IDs supplied")

    import asyncpg
    from pgvector.asyncpg import register_vector
    from oprim import structural_chunk
    from oprim.embedding.bge_m3 import BgeM3Embedder

    started = time.time()
    _log("loading BGE-M3")
    embedder = BgeM3Embedder()
    embedder.embed(["AII parser projection warmup"])
    _log(f"BGE-M3 ready; model={embedder.model_name}; dim={embedder.native_dim}")

    conn = await asyncpg.connect(server_settings={"search_path": "stratum"}, **PG)
    await register_vector(conn)
    done = {
        row["substrate_id"]
        for row in await conn.fetch(
            "SELECT DISTINCT substrate_id FROM substrate_chunk WHERE substrate_id = ANY($1::text[])",
            substrate_ids,
        )
    }
    rows = await conn.fetch(
        """
        SELECT s.id, (
            SELECT d.content FROM derivative d
            WHERE d.substrate_id = s.id AND d.kind='markdown' AND length(d.content) > 0
            ORDER BY length(d.content) DESC LIMIT 1
        ) AS content
        FROM substrates s
        WHERE s.id = ANY($1::text[])
        """,
        substrate_ids,
    )
    by_id = {row["id"]: row["content"] for row in rows}
    missing = [sid for sid in substrate_ids if sid not in by_id]
    no_content = [sid for sid in substrate_ids if not by_id.get(sid)]
    _log(f"sources={len(substrate_ids)} already_projected={len(done)} missing={len(missing)} no_content={len(no_content)}")

    # Refresh anchor metadata for rows projected by older versions of the
    # same production projection, without recomputing the expensive vectors.
    for sid in sorted(done):
        content = by_id.get(sid) or ""
        for row in await conn.fetch(
            "SELECT id, text FROM substrate_chunk WHERE substrate_id=$1 ORDER BY chunk_idx", sid
        ):
            await conn.execute(
                "UPDATE substrate_chunk SET anchor_json=$2::jsonb WHERE id=$1",
                row["id"], json.dumps(_anchor_for(content, row["text"]), ensure_ascii=False),
            )

    total = 0
    for number, sid in enumerate(substrate_ids, 1):
        content = by_id.get(sid)
        if not content or sid in done:
            continue
        raw_chunks = structural_chunk(text=content, min_chars=MIN_CHARS, max_chars=MAX_CHARS) or []
        chunks: list[tuple[str, dict[str, object]]] = []
        for item in raw_chunks:
            if isinstance(item, dict):
                text = item.get("content", "")
                anchor = {
                    key: item[key]
                    for key in ("heading_path", "start_pos", "end_pos", "block_types")
                    if item.get(key) is not None
                }
            else:
                text, anchor = str(item), {}
            if text and text.strip():
                # oprim's structural_chunk output is the canonical parser
                # result but older versions omit character offsets.  Resolve
                # the returned fragment back into the persisted markdown so
                # every production fragment has a real, resolvable anchor.
                if "start_pos" not in anchor or "end_pos" not in anchor:
                    anchor.update(_anchor_for(content, text))
                chunks.append((text, anchor))
        if not chunks:
            chunks = [
                (
                    content[:MAX_CHARS],
                    _anchor_for(content, content[:MAX_CHARS]),
                )
            ]

        records = []
        for offset in range(0, len(chunks), BATCH):
            batch = chunks[offset : offset + BATCH]
            vectors = embedder.embed([text for text, _ in batch])
            for index, ((text, anchor), vector) in enumerate(zip(batch, vectors)):
                chunk_idx = offset + index
                records.append(
                    (
                        f"{sid}#{chunk_idx}", sid, chunk_idx, text, vector,
                        FRAGMENT_VERSION, json.dumps(anchor, ensure_ascii=False), PARSER_VERSION,
                    )
                )
        await conn.executemany(
            """
            INSERT INTO substrate_chunk
              (id, substrate_id, chunk_idx, text, embedding, version, anchor_json, parser_version)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
            ON CONFLICT (id) DO NOTHING
            """,
            records,
        )
        total += len(records)
        _log(f"{number}/{len(substrate_ids)} {sid} chunks={len(records)}")

    try:
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_substrate_chunk_vec "
            "ON substrate_chunk USING hnsw (embedding vector_cosine_ops)"
        )
    except Exception as exc:
        # The qualification database may expose pgvector without the HNSW
        # access method.  Retrieval still uses the registered production path;
        # report the index capability rather than hiding inserted fragments.
        _log(f"vector index creation skipped: {type(exc).__name__}: {exc}")
    count = await conn.fetchval("SELECT count(*) FROM substrate_chunk")
    await conn.close()
    _log(f"done total_rows={count} new_rows={total} elapsed={time.time() - started:.1f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids-file", type=Path)
    parser.add_argument("--substrate-id", action="append")
    args = parser.parse_args()
    return asyncio.run(_run(_read_ids(args)))


if __name__ == "__main__":
    raise SystemExit(main())
