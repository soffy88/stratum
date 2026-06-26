#!/usr/bin/env python3
"""
test_semantic_search.py — 验证本地 embedding 向量搜索恢复

用法:
  python3 test_semantic_search.py [--query "查询文本"] [--n 5]

§20: stratum/scripts/ 层。不改主库。
"""
from __future__ import annotations
import sys, os, argparse, logging

sys.path.insert(0, '/app/src')
os.environ.setdefault('STRATUM_ENV', 'prod')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)

QUERIES = [
    # 中文（经济学/微积分/物理）
    ("中文-经济", "价格弹性与需求变动的关系"),
    ("中文-数学", "微积分导数与极限的定义"),
    ("中文-概率", "贝叶斯定理在条件概率中的应用"),
    # 英文（OpenStax/arxiv papers）
    ("EN-econ",   "price elasticity demand supply equilibrium"),
    ("EN-math",   "calculus derivative limit continuous function"),
    ("EN-ml",     "transformer attention mechanism self-supervised learning"),
    # 混合/双语
    ("混合-统计", "statistical learning theory generalization bounds"),
]


def search(query: str, n: int = 5) -> list[dict]:
    """向量搜索：embed query → 查 LanceDB top-N。"""
    from oprim.embedding import embed_text
    from oprim._config import cfg
    from oskill.ingest_substrate import lancedb_path, _VECTOR_TABLE

    provider = str(cfg.get('EMBEDDING_PROVIDER', 'qwen3_dashscope'))
    vecs = embed_text([query], provider=provider, dim=1024)
    q_vec = vecs[0]

    import lancedb
    vdb = lancedb.connect(str(lancedb_path()))
    tbl = vdb.open_table(_VECTOR_TABLE)
    results = tbl.search(q_vec).limit(n).to_list()
    return results


def get_substrate_title(substrate_id: str) -> str:
    """从 DuckDB 查 substrate 标题（可选，在 service 运行时有效）。"""
    try:
        from stratum.db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT title FROM substrates WHERE id=?", (substrate_id,)
            ).fetchone()
        return row[0] if row else substrate_id[:16]
    except Exception:
        return substrate_id[:16]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--query', '-q', default='', help='Single query (overrides default list)')
    p.add_argument('--n', type=int, default=5, help='Top-N results')
    p.add_argument('--no-db', action='store_true', help='Skip DuckDB title lookup')
    args = p.parse_args()

    queries = [(('custom', args.query),)] if args.query else [(label, q) for label, q in QUERIES]
    if args.query:
        queries = [('custom', args.query)]
    else:
        queries = QUERIES

    all_ok = True
    for label, query in queries:
        log.info("─── [%s] %s", label, query)
        try:
            results = search(query, n=args.n)
            if not results:
                log.warning("  No results!")
                all_ok = False
                continue
            for i, r in enumerate(results, 1):
                sid_chunk = r.get('id', '')
                sid = sid_chunk.split('#')[0] if '#' in sid_chunk else sid_chunk[:26]
                chunk_idx = sid_chunk.split('#')[1] if '#' in sid_chunk else '?'
                score = r.get('_distance', r.get('score', '?'))
                title = '' if args.no_db else get_substrate_title(sid)
                log.info("  %d. [%.4f] %s chunk#%s  %s", i, float(score) if score != '?' else 0,
                         sid[:12], chunk_idx, title[:50])
        except Exception as e:
            log.error("  FAILED: %s", e)
            all_ok = False

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
