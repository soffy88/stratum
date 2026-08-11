"""misc 飞轮恢复脚本 — 清理旧 quarantine/precheck_fail 数据，重新纳入飞轮。

修复后的变化:
  - 预检: 多格式章节检测(第N章/小数编号) + gap/dup 降级为 advisory
  - 质量门: misc 书阈值降低(KU密度 35%→20%, 双语率仅中文, rationale→warning)
  - Provider: httpx 网络错误自动重试(34本 exit(2) 的根因修复)
  - 预检通过书: ~178/228 (原来 ~77/228)

用法:
  cd /home/soffy/projects/AII && .venv/bin/python scripts/misc_recovery.py [--dry-run]
"""
import asyncio, json, os, sys, hashlib, re, glob
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
STATE_PATH = Path("misc_pipeline/flywheel_misc_state.json")
DB_URL = os.getenv("DATABASE_URL")

# ── 1. Load state ──
if not STATE_PATH.exists():
    print("State file not found. Nothing to do.")
    sys.exit(1)

state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
processed = state.get("processed", {})

# ── 2. Load all MD files ──
books_dir = "/home/soffy/books/MD/其它"
md_files = sorted(glob.glob(f"{books_dir}/*.md"))

# Build id→file mapping
id2file = {}
for md_file in md_files:
    stem = Path(md_file).stem
    h = hashlib.md5(stem.encode("utf-8")).hexdigest()[:10]
    id2file[h] = md_file

# ── 3. Re-run precheck on all quarantined/precheck_fail books ──
sys.path.insert(0, "aii")
from aii.service.md_quality_check import check_md_quality

will_pass = []  # (sid, title, old_status, old_reason)
will_fail = []  # (sid, title, old_status, hard_failures)

for sid, rec in processed.items():
    if rec.get("status") not in ("quarantine", "precheck_fail"):
        continue
    h = sid.split("_")[-1]
    md_file = id2file.get(h)
    if not md_file:
        will_fail.append((sid, "unknown", rec["status"], "file not found"))
        continue
    text = open(md_file, encoding="utf-8", errors="replace").read()
    q = check_md_quality(text, medium="book", title=Path(md_file).stem)
    if q["ok"]:
        will_pass.append((sid, Path(md_file).stem, rec["status"], rec.get("reason", "")[:120]))
    else:
        fails = [f["check"] for f in q["hard_failures"]]
        will_fail.append((sid, Path(md_file).stem, rec["status"], ";".join(fails)))

print(f"{'[DRY RUN] ' if DRY_RUN else ''}=== misc 飞轮恢复报告 ===")
print(f"历史 quarantine/precheck_fail: {len(will_pass) + len(will_fail)} 本")
print(f"  修复后预检通过(可恢复): {len(will_pass)}")
print(f"  仍失败(需人工/返工): {len(will_fail)}")
print()

if will_pass:
    print(f"--- 可恢复书明细 ({len(will_pass)}) ---")
    for sid, title, old_status, reason in sorted(will_pass):
        print(f"  {'✅' if not DRY_RUN else '🔄'} {sid}: {title[:50]} (旧:{old_status})")
    print()

if will_fail:
    print(f"--- 仍失败书 ({len(will_fail)}) ---")
    for sid, title, old_status, fail in sorted(will_fail):
        print(f"  ❌ {sid}: {title[:45]} → {fail[:60]}")
    print()

# ── 4. Apply changes ──
if DRY_RUN:
    print("[DRY RUN] 不做实际修改, 退出")
    sys.exit(0)

# Remove recoverable books from state (so discover finds them as NEW)
recovered_ids = [sid for sid, _, _, _ in will_pass]
for sid in recovered_ids:
    del processed[sid]

STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"已从 state 中移除 {len(recovered_ids)} 本可恢复书")

# ── 5. Clean DB data for recoverable books ──
if DB_URL and recovered_ids:
    async def _clean_db():
        import asyncpg
        conn = await asyncpg.connect(DB_URL)
        tables = [
            ("aii.ku_onto", "substrate_id"),
            ("aii.ku_concept_onto", "ku_id"),  # ku_id LIKE 'sid::%'
            ("aii.ku_cooccurrence", "substrate_id"),
            ("aii.kc_onto", "substrate_id"),
            ("aii.bu_onto", "substrate_id"),
            ("aii.ingested_substrate", "substrate_id"),
        ]
        total = 0
        for table, col in tables:
            for sid in recovered_ids:
                if col == "ku_id":
                    n = await conn.fetchval(
                        f"DELETE FROM {table} WHERE ku_id LIKE $1", f"{sid}::%"
                    )
                else:
                    n = await conn.fetchval(
                        f"DELETE FROM {table} WHERE {col}=$1", sid
                    )
                total += n
        await conn.close()
        return total

    print("\n清理 DB 旧数据...")
    n = asyncio.run(_clean_db())
    print(f"已清理 {n} 条 DB 记录")
else:
    print("\n未设置 DATABASE_URL, 跳过 DB 清理(管道 re-run 时 ON CONFLICT 会覆盖)")

print(f"\n{'='*60}")
print(f"恢复就绪! 下一步: cd /home/soffy/projects/AII && bash scripts/misc_flywheel.sh")
print(f"{'='*60}")
