"""For manual QA: show source 2000-char chunk -> KUs (en+zh) extracted from it.
Picks chunks from 3 separated batches. Reconstructs source via the same split logic."""
import asyncio, os, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
from run_first3 import strip_frontmatter, split_batches
import asyncpg

F = "/home/soffy/shared/stratum-to-aii/Principles_of_Microeconomics_The_Way_We__01KVAJCX.md"


def split_chunks(text, size=2000):
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        if end < len(text):
            b = text.rfind("。", start, end)
            if b == -1:
                b = text.rfind(". ", start, end)
            if b != -1 and b > start:
                end = b + 1
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


async def main():
    sub = "microecon_en_full"
    text = strip_frontmatter(Path(F).read_text(encoding="utf-8"))
    batches = split_batches(text, 50000)
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # pick chunks from batches 2, 10, 18 that have 3-6 KUs
    for bi in (2, 10, 18):
        btext = batches[bi]
        bchunks = split_chunks(btext, 2000)
        # find a local chunk with several KUs
        for local in range(len(bchunks)):
            ci = bi * 10000 + local
            rows = await conn.fetch(
                "SELECT knowledge_type, natural_text, natural_text_zh FROM aii.ku_onto "
                "WHERE substrate_id=$1 AND ku_id LIKE $2 ORDER BY ku_id",
                sub, f"%::ku_c{ci}_%")
            if 3 <= len(rows) <= 6:
                print("\n" + "=" * 90)
                print(f"### SOURCE  batch {bi}, chunk_idx {ci}  ({len(rows)} KUs)")
                print("=" * 90)
                print(bchunks[local][:1400])
                print("\n--- KUs EXTRACTED ---")
                for r in rows:
                    print(f"[{r['knowledge_type']}]")
                    print(f"  EN: {r['natural_text']}")
                    print(f"  ZH: {r['natural_text_zh']}")
                break
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
