"""为 kc_onto 知识簇摘要补向量(global 检索修复的一部分).

应用 0004 迁移(加 embedding 列)后, 对每个 KC 的 community_label+summary(优先英文 summary_en)
编码 BGE-M3 写回. 幂等: 只补 embedding IS NULL 的(传 --all 全量重算).

用法: python3 scripts/embed_kc_summaries.py [--all]
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg  # noqa: E402
import numpy as np  # noqa: E402
from aii.api._provider import register_providers  # noqa: E402
from aii import embedding_client  # noqa: E402
from obase import ProviderRegistry  # noqa: E402


def _norm(v):
    a = np.array(v, dtype="float32")
    n = float(np.linalg.norm(a))
    return [float(x) / n for x in a] if n > 0 else [float(x) for x in a]


async def main():
    do_all = "--all" in sys.argv
    register_providers()
    embed_fn = ProviderRegistry.get()._generic.get("embedding", {}).get("default")
    is_eg2 = embedding_client.backend() == "eg2"
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # 确保迁移已应用
    await conn.execute(open(ROOT / "migrations" / "0004_kc_embedding.sql").read())
    where = "" if do_all else "WHERE embedding IS NULL"
    rows = await conn.fetch(f"""
        SELECT kc_id, community_label, summary, summary_en FROM aii.kc_onto {where}
    """)
    print(f"embedding {len(rows)} KC summaries...", flush=True)
    n = 0
    for r in rows:
        if is_eg2:
            # eg2 统一口径: doc_text(community_label, summary or summary_en)
            text = embedding_client.doc_text(r["community_label"], r["summary"] or r["summary_en"])
        else:
            text = " — ".join(
                filter(None, [r["community_label"], r["summary_en"] or r["summary"]])
            )[:2000]
        if not text.strip():
            continue
        vec = _norm(embed_fn([text])[0])
        await conn.execute(
            "UPDATE aii.kc_onto SET embedding = $1 WHERE kc_id = $2", str(vec), r["kc_id"]
        )
        n += 1
    print(f"DONE: embedded {n} KC", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
