"""L0-only layer backfill for substrates missing L0 (no LLM, local embeddings).

Usage (inside stratum-sl container):
    python3 backfill_l0.py <user_id_hash> [limit] [start_log]

L0 content = title (short) or first 200 chars of preferred derivative.
Idempotent/resumable: skips substrates that already have an L0 row.
"""
from __future__ import annotations

import sys
import time

from stratum.db import get_conn
from stratum.services.layer_generator import _get_embedding, _estimate_tokens, _gen_id

uid_hash = sys.argv[1] if len(sys.argv) > 1 else "56d6bc01edc35765"
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200
MODEL = "qwen3-embedding"

with get_conn() as c:
    rows = c.execute(
        """SELECT s.id, s.title,
             (SELECT d.content FROM derivative d
              WHERE d.substrate_id = s.id AND d.content IS NOT NULL AND d.content <> ''
              ORDER BY CASE WHEN d.kind='markdown' THEN 0
                        WHEN d.kind LIKE 'translation%%zh%%' THEN 1 ELSE 2 END,
                length(d.content) DESC LIMIT 1) AS content
           FROM substrates s
           WHERE s.user_id = ?
             AND NOT EXISTS (SELECT 1 FROM substrate_layers l WHERE l.substrate_id = s.id AND l.layer = 'L0')
           ORDER BY s.created_at LIMIT ?""",
        (uid_hash, limit),
    ).fetchall()

print(f"targets: {len(rows)} substrates missing L0 (user {uid_hash})")
t0 = time.time()
ok = skipped = 0
for i, (sid, title, content) in enumerate(rows, 1):
    text = content or title or ""
    if not text:
        skipped += 1
        continue
    l0 = (title or "").strip()[:200] if len(text) < 500 else (title or text)[:200]
    if not l0.strip():
        l0 = text[:200]
    embedding = _get_embedding(l0.replace("\x00", ""))
    if not embedding:
        print(f"[{i}/{len(rows)}] {sid[:12]} embed FAILED")
        continue
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
    layer_id = _gen_id(f"sl-{sid}-L0")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO substrate_layers (id, substrate_id, layer, content, token_count, model_used, embedding)
               VALUES (?, ?, 'L0', ?, ?, ?, ?::vector)
               ON CONFLICT (substrate_id, layer) DO UPDATE
               SET content = EXCLUDED.content, token_count = EXCLUDED.token_count,
                   model_used = EXCLUDED.model_used, embedding = EXCLUDED.embedding,
                   generated_at = NOW()""",
            (layer_id, sid, l0, _estimate_tokens(l0), MODEL, emb_str),
        )
    ok += 1
    if i % 25 == 0:
        print(f"  [{i}/{len(rows)}] done={ok} skipped={skipped} elapsed={time.time()-t0:.0f}s")
print(f"L0 backfill complete: done={ok} skipped={skipped} elapsed={time.time()-t0:.0f}s")
