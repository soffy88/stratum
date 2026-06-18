import asyncio
import os
import sys
import json
import duckdb
from pathlib import Path

# Add src to path
sys.path.append("/app/src")

from oprim.embedding import embed_text
from oprim.vector_db import open_vector_db
from oskill.knowledge._context import lancedb_path

async def backfill(limit=300):
    db_path = os.path.expanduser("~/.stratum/meta.duckdb")
    lancedb_dir = lancedb_path()
    
    print(f"Connecting to DuckDB: {db_path}")
    is_read_only = False
    try:
        conn = duckdb.connect(db_path, read_only=False)
    except Exception as e:
        print(f"Failed to connect for writing: {e}")
        print("Falling back to read-only mode")
        conn = duckdb.connect(db_path, read_only=True)
        is_read_only = True

    # 1. Find substrates missing embeddings for markdown kind
    query = """
    SELECT s.id, s.user_id, d.content, s.title
    FROM substrates s
    JOIN derivative d ON s.id = d.substrate_id
    WHERE d.kind = 'markdown' 
      AND (d.embedding_id IS NULL OR d.embedding_id = '')
    LIMIT ?
    """
    rows = conn.execute(query, [limit]).fetchall()
    print(f"Found {len(rows)} substrates to process (limit={limit})")
    
    if not rows:
        return

    # 2. Open LanceDB
    vdb = open_vector_db(lancedb_dir, "vectors_text", 1024)
    from oprim.vector_db import VectorRecord
    
    for sid, user_id, content, title in rows:
        print(f"Processing: {title} ({sid})")
        if not content:
            print(f"  Skipping: Empty content")
            continue
            
        try:
            # 3. Handle length limit (8192 for DashScope)
            # Use a safe margin
            if len(content) > 8000:
                print(f"  Warning: Content too long ({len(content)} chars), truncating to 8000")
                safe_content = content[:8000]
            else:
                safe_content = content

            # 4. Embed text
            vectors = embed_text([safe_content])
            if not vectors:
                print(f"  Error: Failed to get embedding")
                continue
            
            vector = vectors[0]
            emb_id = f"emb_{sid}"
            
            # 5. Upsert to LanceDB
            record = VectorRecord(
                id=emb_id,
                embedding=vector,
                metadata={
                    "substrate_id": sid,
                    "user_id": user_id,
                    "title": title,
                    "kind": "markdown"
                }
            )
            vdb.upsert([record])
            print(f"  Upserted to LanceDB: {emb_id}")
            
            # 6. Update DuckDB
            if not is_read_only:
                conn.execute(
                    "UPDATE derivative SET embedding_id = ?, embedding_dim = ? WHERE substrate_id = ? AND kind = 'markdown'",
                    [emb_id, len(vector), sid]
                )
                print(f"  Updated DuckDB")
            else:
                print(f"  Skipped DuckDB update (read-only)")
                
        except Exception as e:
            print(f"  Error processing {sid}: {e}")

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    asyncio.run(backfill(limit))
