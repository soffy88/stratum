"""数学管道 — 质量门通过后的正式入库.

流程:
  1. 调用 math_ingest.py 将暂存KU写入 aii.ku_onto
  2. INSERT/UPDATE aii.ingested_substrate (subject='数学')
  3. 写 math_pipeline/run_log.jsonl 审计记录

Usage: python scripts/math_register.py <substrate_id> <title> --staging <dir> [--subject 数学]
"""
import asyncio, asyncpg, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

RUN_LOG = ROOT / "math_pipeline" / "run_log.jsonl"
RUN_LOG.parent.mkdir(parents=True, exist_ok=True)

if len(sys.argv) < 3:
    print("Usage: math_register.py <substrate_id> <title> --staging <dir>", file=sys.stderr)
    sys.exit(1)

SUB = sys.argv[1]
TITLE = sys.argv[2]
STAGING = ""
SUBJECT = "数学"
args = sys.argv[3:]
for i, a in enumerate(args):
    if a == "--staging" and i + 1 < len(args):
        STAGING = args[i + 1]
    if a == "--subject" and i + 1 < len(args):
        SUBJECT = args[i + 1]

if not STAGING:
    print("❌ 必须提供 --staging <dir>", file=sys.stderr)
    sys.exit(1)


async def register():
    # ── Step 1: 调用 math_ingest.py 入 ku_onto ──
    PY = str(ROOT / ".venv" / "bin" / "python")
    ingest_script = str(ROOT / "scripts" / "math_ingest.py")
    print(f"  [1/3] math_ingest.py --substrate {SUB} --staging {STAGING}", flush=True)
    result = subprocess.run(
        [PY, ingest_script, "--substrate", SUB, "--staging", STAGING],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"❌ math_ingest.py 失败(exit={result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)

    # ── Step 2: 登记 ingested_substrate ──
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    ku_count = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
    await conn.execute("""
        INSERT INTO aii.ingested_substrate (substrate_id, title, medium, ku_count, subject)
        VALUES ($1, $2, 'book', $3, $4)
        ON CONFLICT (substrate_id) DO UPDATE
            SET title=EXCLUDED.title,
                ku_count=EXCLUDED.ku_count,
                subject=COALESCE(EXCLUDED.subject, aii.ingested_substrate.subject)
    """, SUB, TITLE[:300], ku_count, SUBJECT)
    await conn.close()

    # ── Step 3: 审计记录 ──
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "substrate_id": SUB,
        "title": TITLE,
        "subject": SUBJECT,
        "staging": STAGING,
        "ku_count": ku_count,
        "action": "registered",
    }
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"  ✅ 已入库: {SUB} | KU={ku_count}", flush=True)
    print(f"  审计记录 → {RUN_LOG}", flush=True)
    return ku_count


if __name__ == "__main__":
    asyncio.run(register())
