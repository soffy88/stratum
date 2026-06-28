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
    return {'定理': 'rationale', '推论': 'rationale',
            '定义': 'conceptual', '知识点': 'conceptual'}.get(t, 'conceptual')

async def main(substrate: str, staging_dir: Path, dry_run: bool = False):
    kus_all = []
    for chf in sorted(staging_dir.glob('ch*.json')):
        kus = json.loads(chf.read_text())
        kus_all.extend(kus)
    print(f'★ 准备入库: substrate={substrate}, KU数={len(kus_all)}', flush=True)

    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        raise SystemExit('DATABASE_URL 未设置')

    conn = await asyncpg.connect(dsn)
    await register_vector(conn)

    # 检查是否已有数据
    existing = await conn.fetchval(
        'SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1', substrate)
    if existing > 0:
        print(f'  ★警告: substrate {substrate} 已有 {existing} 条, 将 UPSERT (覆盖旧内容)', flush=True)

    ok = skip = err = 0
    for k in kus_all:
        ch = k.get('chapter', 0)
        pt = k.get('point', '')
        ku_id = f"{substrate}::{ch}::{pt}"
        title = k.get('label') or pt
        zh = k.get('zh', '')
        en = k.get('en', '')
        ktype = _ku_type(k.get('type', '知识点'))
        provenance = {
            'chapter': ch,
            'key_terms': k.get('key_terms', []),
        }
        if k.get('facet_exempt'):
            provenance['facet_exempt'] = k['facet_exempt']

        # embedding 用 en (英文内容)
        embed_text = en or zh  # fallback to zh if no en
        if not embed_text.strip():
            print(f'  ★skip empty: {ku_id}', flush=True)
            skip += 1
            continue

        try:
            emb = vector_encode(texts=[embed_text], provider='default')[0]
        except Exception as e:
            print(f'  ★embed fail {ku_id}: {e}', flush=True)
            err += 1
            continue

        if dry_run:
            print(f'  [DRY] {ku_id} | {title[:40]} | {ktype}')
            ok += 1
            continue

        try:
            await conn.execute("""
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
                ku_id, substrate, title, en, ktype,
                json.dumps(provenance, ensure_ascii=False), emb, zh)
            ok += 1
            if ok % 50 == 0:
                print(f'  进度: {ok}/{len(kus_all)}', flush=True)
        except Exception as e:
            print(f'  ★insert fail {ku_id}: {e}', flush=True)
            err += 1

    await conn.close()
    print(f'\n★ 入库完成: ok={ok} skip={skip} err={err}', flush=True)
    print(f'  substrate={substrate}, 验证: SELECT count(*) FROM aii.ku_onto WHERE substrate_id=\'{substrate}\';', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--substrate', default='shufen_huadong_full')
    p.add_argument('--staging', default=str(ROOT / 'scripts' / '_staging' / 'math_full'))
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    asyncio.run(main(args.substrate, Path(args.staging), args.dry_run))
