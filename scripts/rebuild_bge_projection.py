"""Rebuild the KnowledgeView L0 dense projection with BAAI/bge-m3.

This is a corpus-wide, resumable projection rebuild.  It updates only the
rebuildable ``substrate_layers.embedding`` and ``model_used`` fields; canonical
Source/Fragment content is never synthesized or replaced.
"""

from __future__ import annotations

import argparse
import os
import time

import psycopg2


DB = dict(
    host=os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
    port=int(os.environ.get("STRATUM_PG_PORT", "5435")),
    user=os.environ.get("STRATUM_PG_USER", "aii"),
    password=os.environ.get("STRATUM_PG_PASSWORD", "aii_safe_pass"),
    dbname=os.environ.get("STRATUM_PG_DB", "aii_kg"),
)
MODEL = "BAAI/bge-m3"
DIM = 1024


def rebuild(
    batch_size: int,
    max_length: int,
    limit: int | None = None,
    shard_index: int = 0,
    shard_count: int = 1,
    reindex: bool = True,
) -> dict[str, int]:
    import torch

    # Several independent workers are used on CPU in the qualification host.
    # Keep each worker bounded so they do not oversubscribe the host.
    threads = int(os.environ.get("BGE_NUM_THREADS", "4"))
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(max(1, min(threads, 4)))
    from FlagEmbedding import BGEM3FlagModel

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(
        """SELECT sl.id, sl.content
           FROM stratum.substrate_layers sl
           JOIN stratum.substrates s ON s.id = sl.substrate_id
           WHERE sl.layer = 'L0'
             AND (sl.embedding IS NULL OR sl.model_used IS DISTINCT FROM %s
                  OR vector_dims(sl.embedding) <> %s)
             AND mod(abs(hashtext(sl.id)), %s) = %s
           ORDER BY sl.id""",
        (MODEL, DIM, shard_count, shard_index),
    )
    targets = cur.fetchall()
    if limit:
        targets = targets[:limit]
    print(f"eligible_targets={len(targets)}", flush=True)

    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
    done = 0
    failed = 0
    started = time.monotonic()
    for offset in range(0, len(targets), batch_size):
        batch = targets[offset : offset + batch_size]
        texts = [(content or "")[:max_length] for _, content in batch]
        try:
            vectors = model.encode(texts, batch_size=batch_size, max_length=max_length)["dense_vecs"]
            if len(vectors) != len(batch):
                raise RuntimeError(f"embedding count {len(vectors)} != target count {len(batch)}")
            for (layer_id, _), vector in zip(batch, vectors):
                if len(vector) != DIM:
                    raise RuntimeError(f"wrong embedding dimension for {layer_id}: {len(vector)}")
                vec = "[" + ",".join(str(float(value)) for value in vector) + "]"
                cur.execute(
                    "UPDATE stratum.substrate_layers "
                    "SET embedding=%s::vector, model_used=%s, generated_at=NOW() WHERE id=%s",
                    (vec, MODEL, layer_id),
                )
            conn.commit()
            done += len(batch)
        except Exception as exc:
            conn.rollback()
            failed += len(batch)
            print(f"batch_failed offset={offset} size={len(batch)} error={exc}", flush=True)
        if done and (done % (batch_size * 10) == 0 or done == len(targets)):
            print(
                f"processed={done}/{len(targets)} failed={failed} "
                f"elapsed={time.monotonic() - started:.1f}s",
                flush=True,
            )

    if reindex:
        cur.execute("REINDEX INDEX stratum.idx_sl_embedding")
        cur.execute("REINDEX INDEX stratum.idx_substrate_layers_embedding")
        conn.commit()
    else:
        conn.commit()
    cur.execute(
        """SELECT count(*) FILTER (WHERE embedding IS NOT NULL AND model_used=%s
                                      AND vector_dims(embedding)=%s),
                         count(*) FILTER (WHERE embedding IS NULL),
                         count(*) FILTER (WHERE embedding IS NOT NULL AND model_used<>%s),
                         count(*) FILTER (WHERE embedding IS NOT NULL AND vector_dims(embedding)<>%s)
                  FROM stratum.substrate_layers WHERE layer='L0'""",
        (MODEL, DIM, MODEL, DIM),
    )
    indexed, missing, wrong_model, wrong_dim = cur.fetchone()
    conn.close()
    result = {
        "eligible_targets": len(targets),
        "updated": done,
        "failed": failed,
        "indexed_l0": indexed,
        "missing_embeddings": missing,
        "wrong_model": wrong_model,
        "wrong_dimension": wrong_dim,
    }
    print(result, flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=8192)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--skip-reindex", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("--shard-index must be within --shard-count")
    rebuild(
        args.batch_size,
        args.max_length,
        args.limit,
        args.shard_index,
        args.shard_count,
        not args.skip_reindex,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
