"""同济重抽章节入库: 先删旧(ch{N}_ku*)再插新(颗粒化KU).
Usage: uv run python scripts/tongji_ingest.py [--dry-run]
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

SUBSTRATE = 'advmath_tongji_full'
STAGING = ROOT / 'scripts' / '_staging' / 'tongji'
# 重抽的章节(上册Ch1/3/5/7), 对应旧ku_id前缀
REPLACED_CHAPTERS = [1, 3, 5, 7, 9, 10, 11, 12]

def _ku_type(t):
    return {'定理': 'rationale', '推论': 'rationale',
            '定义': 'conceptual', '知识点': 'conceptual'}.get(t, 'conceptual')

async def main(dry_run: bool = False):
    kus_all = []
    for ch in sorted(REPLACED_CHAPTERS):
        chf = STAGING / f'ch{ch}.json'
        if not chf.exists():
            print(f'★警告: {chf} 不存在, 跳过', flush=True)
            continue
        kus = json.loads(chf.read_text())
        kus_all.extend(kus)
    print(f'★ 准备入库: substrate={SUBSTRATE}, 新KU={len(kus_all)}', flush=True)

    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        raise SystemExit('DATABASE_URL 未设置')

    conn = await asyncpg.connect(dsn)
    await register_vector(conn)

    # 统计将被删除的旧行 (用 _ku% 避免 ch1_% 误匹配 ch10_, ch11_, ch12_)
    for ch in REPLACED_CHAPTERS:
        old_pattern = f'{SUBSTRATE}::ch{ch}_ku%'
        cnt = await conn.fetchval(
            "SELECT count(*) FROM aii.ku_onto WHERE ku_id LIKE $1", old_pattern)
        print(f'  Ch{ch}: 旧行={cnt}条 (将删除)', flush=True)

    if dry_run:
        print('\n[DRY-RUN] 跳过实际DB操作', flush=True)
        for k in kus_all[:5]:
            ch = k.get('chapter'); pt = k.get('point')
            print(f'  [DRY] {SUBSTRATE}::{ch}::{pt} | {k["label"][:30]}')
        print(f'  ... 共{len(kus_all)}条')
        await conn.close()
        return

    # 删除旧行
    for ch in REPLACED_CHAPTERS:
        old_pattern = f'{SUBSTRATE}::ch{ch}_ku%'
        await conn.execute(
            "DELETE FROM aii.ku_onto WHERE ku_id LIKE $1", old_pattern)
    print('★ 旧行已删除', flush=True)

    # 插入新行
    ok = skip = err = 0
    for k in kus_all:
        ch = k.get('chapter', 0)
        pt = k.get('point', '')
        ku_id = f"{SUBSTRATE}::{ch}::{pt}"
        title = k.get('label') or pt
        zh = k.get('zh', '')
        en = k.get('en', '')
        ktype = _ku_type(k.get('type', '知识点'))
        provenance = {'chapter': ch, 'key_terms': k.get('key_terms', [])}
        if k.get('facet_exempt'):
            provenance['facet_exempt'] = k['facet_exempt']

        embed_text = en or zh
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
                ku_id, SUBSTRATE, title, en, ktype,
                json.dumps(provenance, ensure_ascii=False), emb, zh)
            ok += 1
            if ok % 30 == 0:
                print(f'  进度: {ok}/{len(kus_all)}', flush=True)
        except Exception as e:
            print(f'  ★insert fail {ku_id}: {e}', flush=True)
            err += 1

    await conn.close()
    print(f'\n★ 入库完成: ok={ok} skip={skip} err={err}', flush=True)
    print(f"  验证: SELECT count(*) FROM aii.ku_onto WHERE substrate_id='{SUBSTRATE}';", flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    asyncio.run(main(args.dry_run))
