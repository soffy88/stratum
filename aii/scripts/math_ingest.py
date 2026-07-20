"""数学KU暂存→正式入库.
Usage: uv run python scripts/math_ingest.py [--substrate SUBSTRATE] [--staging DIR]
默认 substrate = shufen_huadong_full, staging = scripts/_staging/math_full/
"""

import asyncio, os, json, sys, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "aii" / ".env", override=True)
except ImportError:
    pass
sys.path.insert(0, str(ROOT / "scripts"))

import asyncpg
from pgvector.asyncpg import register_vector
from aii.api._provider import register_providers
from oprim import vector_encode

register_providers()


def _ku_type(t):
    """暂存type → DB knowledge_type."""
    return {
        "定理": "rationale",
        "推论": "rationale",
        "引理": "rationale",
        "命题": "rationale",
        "例子": "procedural",
        "定义": "conceptual",
        "知识点": "conceptual",
    }.get(t, "conceptual")


async def main(substrate: str, staging_dir: Path, dry_run: bool = False):
    kus_all = []
    for chf in sorted(staging_dir.glob("ch*.json")):
        txt = chf.read_text().strip()
        if not txt:  # 空 staging 文件 → 跳过(不让整本崩)
            print(f"  ⚠ 跳过空文件 {chf.name}", flush=True)
            continue
        try:
            kus = json.loads(txt)
        except json.JSONDecodeError as e:  # 损坏 JSON → 跳过该章
            print(f"  ⚠ 跳过损坏 {chf.name}: {e}", flush=True)
            continue
        kus_all.extend(kus)
    print(f"★ 准备入库: substrate={substrate}, KU数={len(kus_all)}", flush=True)

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL 未设置")

    conn = await asyncpg.connect(dsn)
    await register_vector(conn)

    # 检查是否已有数据
    existing = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", substrate
    )
    if existing > 0:
        print(
            f"  ★警告: substrate {substrate} 已有 {existing} 条, 将 UPSERT (覆盖旧内容)", flush=True
        )

    ok = skip = err = 0
    # ── 阶段1: 收集非空 KU ──
    rows = []
    for k in kus_all:
        embed_text = (k.get("en", "") or k.get("zh", "")).strip()
        if not embed_text:
            print(
                f"  ★skip empty: {substrate}::{k.get('chapter', 0)}::{k.get('point', '')}",
                flush=True,
            )
            skip += 1
            continue
        rows.append((k, embed_text))

    # ── 阶段2: 批量嵌入(分块调共享服务; 整块失败降级逐条, 保证不整批挂) ──
    embs = []
    B = 64
    for i in range(0, len(rows), B):
        chunk = [t for _, t in rows[i : i + B]]
        try:
            embs.extend(vector_encode(texts=chunk, provider="default"))
        except Exception as e:
            print(f"  ★batch embed fail @{i} 降级逐条: {e}", flush=True)
            for t in chunk:
                try:
                    embs.append(vector_encode(texts=[t], provider="default")[0])
                except Exception as e2:
                    print(f"  ★embed fail: {e2}", flush=True)
                    embs.append(None)
        print(f"  嵌入 {min(i + B, len(rows))}/{len(rows)}", flush=True)

    # ── 阶段3: 插入 ──
    for (k, embed_text), emb in zip(rows, embs):
        if emb is None:
            err += 1
            continue
        ch = k.get("chapter", 0)
        pt = k.get("point", "")
        ku_id = f"{substrate}::{ch}::{pt}"
        title = k.get("label") or pt
        zh = k.get("zh", "")
        en = k.get("en", "")
        ktype = _ku_type(k.get("type", "知识点"))
        provenance = {
            "chapter": ch,
            "key_terms": k.get("key_terms", []),
        }
        if k.get("facet_exempt"):
            provenance["facet_exempt"] = k["facet_exempt"]

        if dry_run:
            print(f"  [DRY] {ku_id} | {title[:40]} | {ktype}")
            ok += 1
            continue

        try:
            await conn.execute(
                """
                INSERT INTO aii.ku_onto
                    (ku_id, substrate_id, title, natural_text, knowledge_type,
                     provenance, embedding, natural_text_zh, grade)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'unverified')
                ON CONFLICT (ku_id) DO UPDATE SET
                    title=EXCLUDED.title,
                    natural_text=EXCLUDED.natural_text,
                    natural_text_zh=EXCLUDED.natural_text_zh,
                    knowledge_type=EXCLUDED.knowledge_type,
                    provenance=EXCLUDED.provenance,
                    embedding=EXCLUDED.embedding,
                    updated_at=now()
                """,
                ku_id,
                substrate,
                title,
                en,
                ktype,
                json.dumps(provenance, ensure_ascii=False),
                emb,
                zh,
            )
            ok += 1
            if ok % 50 == 0:
                print(f"  进度: {ok}/{len(kus_all)}", flush=True)
        except Exception as e:
            print(f"  ★insert fail {ku_id}: {e}", flush=True)
            err += 1

    await conn.close()
    print(f"\n★ 入库完成: ok={ok} skip={skip} err={err}", flush=True)
    print(
        f"  substrate={substrate}, 验证: SELECT count(*) FROM aii.ku_onto WHERE substrate_id='{substrate}';",
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--substrate", default="shufen_huadong_full")
    p.add_argument("--staging", default=str(ROOT / "scripts" / "_staging" / "math_full"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.substrate, Path(args.staging), args.dry_run))
