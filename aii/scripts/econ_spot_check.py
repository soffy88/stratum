"""经济学管道事后抽检 — 查入库质量/隔离等审查的书/随机采样KU.

子命令:
  list                      列出所有已入库经济学书(含质量指标)
  quarantine                列出质量门拦截等待人工审查的书
  sample <substrate_id> [N] 从指定书随机采样 N 个KU全文(默认5个)
  wiki <substrate_id>       查看指定书的BU(书级理解七项)
  report <substrate_id>     查看指定书的质量门报告JSON

Usage:
  python scripts/econ_spot_check.py list
  python scripts/econ_spot_check.py quarantine
  python scripts/econ_spot_check.py sample microecon_en_full_v2 3
  python scripts/econ_spot_check.py wiki microecon_en_full_v2
  python scripts/econ_spot_check.py report microecon_en_full_v2
"""
import asyncio, asyncpg, json, os, random, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
QUARANTINE = ROOT / "econ_pipeline" / "quarantine.json"
QUAL_DIR = ROOT / "econ_pipeline" / "qual"
RUN_LOG = ROOT / "econ_pipeline" / "run_log.jsonl"


async def cmd_list():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("""
        SELECT s.substrate_id, s.title, s.ku_count, s.deep_understood_at,
               (SELECT count(*) FROM aii.directed_edge_v2 d WHERE d.substrate_id=s.substrate_id) AS edges,
               (SELECT count(*) FROM aii.kc_onto k WHERE k.substrate_id=s.substrate_id AND k.synthesis_marker='AII章节KC') AS kcs,
               (SELECT count(*) FROM aii.bu_onto b WHERE b.substrate_id=s.substrate_id) AS has_bu
        FROM aii.ingested_substrate s
        WHERE s.subject='经济学'
        ORDER BY s.ingested_at DESC
    """)
    await conn.close()

    print(f"已入库经济学书: {len(rows)} 本\n")
    print(f"{'SUBSTRATE':<30} {'KU':>5} {'边':>5} {'KC':>4} {'BU':>3} {'讲透日期'}")
    print("-" * 75)
    for r in rows:
        bu = "✅" if r["has_bu"] else "❌"
        dt = r["deep_understood_at"].strftime("%m-%d") if r["deep_understood_at"] else "  --"
        print(f"{r['substrate_id'][:30]:<30} {(r['ku_count'] or 0):>5} {r['edges']:>5} {r['kcs']:>4} {bu:>3} {dt}")
        if len(r["title"]) > 0:
            print(f"  └─ {r['title'][:70]}")

    # 显示有质量报告的
    qual_files = list(QUAL_DIR.glob("*.json")) if QUAL_DIR.exists() else []
    if qual_files:
        print(f"\n质量报告文件({len(qual_files)}个) → {QUAL_DIR}/")
        for qf in sorted(qual_files)[:10]:
            try:
                d = json.loads(qf.read_text(encoding="utf-8"))
                verdict = d.get("verdict", "?")
                alarms = len(d.get("alarms", []))
                print(f"  {qf.stem[:35]:<35} {verdict} ({alarms}报警)")
            except Exception:
                pass


async def cmd_quarantine():
    if not QUARANTINE.exists():
        print("隔离区为空(文件不存在)")
        return
    d = json.loads(QUARANTINE.read_text(encoding="utf-8"))
    items = d.get("quarantined", [])
    print(f"质量门拦截(等待人工审查): {len(items)} 本\n")
    for item in items:
        status = item.get("status", "?")
        print(f"  [{status}] {item.get('substrate_id','')}")
        print(f"    书名: {item.get('title','')[:60]}")
        print(f"    原因: [{item.get('reason_type','')}] {item.get('reason_detail','')[:80]}")
        print(f"    时间: {item.get('ts','')[:16]}")
        qf = item.get("qual_json", "")
        if qf and Path(qf).exists():
            try:
                qd = json.loads(Path(qf).read_text(encoding="utf-8"))
                for alarm in qd.get("alarms", []):
                    print(f"    🚨 {alarm[:80]}")
            except Exception:
                pass
        print()


async def cmd_sample(sub: str, n: int = 5):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT ku_id, title, natural_text_zh, knowledge_type FROM aii.ku_onto"
        " WHERE substrate_id=$1 ORDER BY random() LIMIT $2", sub, n)
    await conn.close()

    if not rows:
        print(f"没有找到 {sub} 的 KU(可能未入库或substrate_id错误)")
        return

    print(f"随机抽样 {len(rows)} 个KU 来自: {sub}\n")
    for i, r in enumerate(rows, 1):
        print(f"{'='*60}")
        print(f"[{i}/{len(rows)}] {r['title']}  [{r['knowledge_type']}]")
        print(f"KU ID: {r['ku_id']}")
        print(f"{'─'*60}")
        zh = r["natural_text_zh"] or "(无中文)"
        print(zh[:800] + ("…(截断)" if len(zh) > 800 else ""))
        print()


async def cmd_wiki(sub: str):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    row = await conn.fetchrow(
        "SELECT * FROM aii.bu_onto WHERE substrate_id=$1 ORDER BY created_at DESC LIMIT 1", sub)
    await conn.close()

    if not row:
        print(f"没有找到 {sub} 的 BU(书级理解未生成或未入库)")
        return

    print(f"{'='*60}")
    print(f"书级理解(BU): {sub}")
    print(f"{'='*60}")
    fields = ["problem_statement", "overview_oneline", "learning_thread",
              "source_credibility", "doc_type", "grade"]
    for f in fields:
        v = row[f]
        if v:
            print(f"\n【{f}】")
            print(str(v)[:400])

    for f in ["core_takeaways", "main_claims", "argument_structure", "core_explanations"]:
        v = row[f]
        if v:
            print(f"\n【{f}】")
            items = v if isinstance(v, list) else [v]
            for item in items[:5]:
                print(f"  • {str(item)[:120]}")


async def cmd_report(sub: str):
    qf = QUAL_DIR / f"{sub}.json"
    if not qf.exists():
        print(f"质量报告文件不存在: {qf}")
        print(f"(先运行: python scripts/econ_quality_gate.py {sub} --json {qf})")
        return
    d = json.loads(qf.read_text(encoding="utf-8"))
    print(json.dumps(d, ensure_ascii=False, indent=2))


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == "list":
        await cmd_list()
    elif cmd == "quarantine":
        await cmd_quarantine()
    elif cmd == "sample":
        sub = sys.argv[2] if len(sys.argv) > 2 else "microecon_en_full_v2"
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        await cmd_sample(sub, n)
    elif cmd == "wiki":
        sub = sys.argv[2] if len(sys.argv) > 2 else "microecon_en_full_v2"
        await cmd_wiki(sub)
    elif cmd == "report":
        sub = sys.argv[2] if len(sys.argv) > 2 else "microecon_en_full_v2"
        await cmd_report(sub)
    else:
        print(f"未知子命令: {cmd}\n{__doc__}")


if __name__ == "__main__":
    asyncio.run(main())
