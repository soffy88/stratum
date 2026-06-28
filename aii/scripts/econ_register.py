"""经济学管道 — 质量门通过后的正式入库登记.

流程:
  1. 从 ku_onto 计算实际 KU 数
  2. INSERT/UPDATE ingested_substrate (substrate_id, title, medium, ku_count, subject='经济学')
  3. 若 BU 已生成则标记 deep_understood_at
  4. 写 econ_pipeline/run_log.jsonl 审计记录(可追溯)

Usage: python econ_register.py <substrate_id> <title> [--medium book] [--subject 经济学]
"""
import asyncio, asyncpg, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

RUN_LOG = ROOT / "econ_pipeline" / "run_log.jsonl"
RUN_LOG.parent.mkdir(parents=True, exist_ok=True)

if len(sys.argv) < 3:
    print("Usage: econ_register.py <substrate_id> <title> [--medium book] [--subject 经济学]",
          file=sys.stderr)
    sys.exit(1)

SUB = sys.argv[1]
TITLE = sys.argv[2]
MEDIUM = "book"
SUBJECT = "经济学"
args = sys.argv[3:]
for i, a in enumerate(args):
    if a == "--medium" and i + 1 < len(args):
        MEDIUM = args[i + 1]
    if a == "--subject" and i + 1 < len(args):
        SUBJECT = args[i + 1]


async def register():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

    # 从 ku_onto 数实际 KU 数
    ku_count = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)

    # 入库 ingested_substrate
    await conn.execute("""
        INSERT INTO aii.ingested_substrate (substrate_id, title, medium, ku_count, subject)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (substrate_id) DO UPDATE
            SET title=EXCLUDED.title,
                medium=EXCLUDED.medium,
                ku_count=EXCLUDED.ku_count,
                subject=COALESCE(EXCLUDED.subject, aii.ingested_substrate.subject)
    """, SUB, TITLE[:300], MEDIUM, ku_count, SUBJECT)

    # 若 BU 已生成 → 标记 deep_understood_at
    has_bu = await conn.fetchval(
        "SELECT count(*) FROM aii.bu_onto WHERE substrate_id=$1", SUB)
    if has_bu:
        await conn.execute(
            "UPDATE aii.ingested_substrate SET deep_understood_at=NOW() WHERE substrate_id=$1",
            SUB)

    await conn.close()

    # 审计记录
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "substrate_id": SUB,
        "title": TITLE,
        "medium": MEDIUM,
        "subject": SUBJECT,
        "ku_count": ku_count,
        "action": "registered",
        "has_bu": bool(has_bu),
    }
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ 已入库: {SUB} | KU={ku_count} | BU={'已' if has_bu else '未'}")
    print(f"  审计记录 → {RUN_LOG}")
    return ku_count


if __name__ == "__main__":
    asyncio.run(register())
