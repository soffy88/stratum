#!/usr/bin/env python3
"""
无 embedding 基底批量补跑脚本。

现在使用本地 Ollama qwen3-embedding:0.6b（不再依赖 DashScope）。

【重要】：脚本要求在服务停止时运行（DuckDB 单写锁）

用法:
  # Step 1: 停服务
  docker stop stratum-sl

  # Step 2: 确认本地 embedding 可用:
  docker run --rm -v ~/.stratum:/root/.stratum \
    -e EMBEDDING_PROVIDER=qwen3_local -e OLLAMA_BASE_URL=http://172.17.0.1:11434 \
    <image> python3 /app/scripts/batch_reembed.py --test

  # Step 3: 补跑所有缺 embedding 的基底:
  docker run --rm -v ~/.stratum:/root/.stratum \
    -v /home/soffy/shared/stratum-to-aii:/data/shared/stratum-to-aii \
    -e EMBEDDING_PROVIDER=qwen3_local -e OLLAMA_BASE_URL=http://172.17.0.1:11434 \
    <image> python3 /app/scripts/batch_reembed.py --run

  # Step 4: 重启服务
  docker start stratum-sl

  # 只补 paper 类:
  python3 batch_reembed.py --run --medium paper

§20: 只调 oprim/oskill 的公开 API，不改库代码。
"""
import sys, os, argparse, pathlib, json, time, logging

sys.path.insert(0, '/app/src')
os.environ.setdefault('STRATUM_ENV', 'prod')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ── 1. 找无 embedding 的 substrate ─────────────────────────────────────────────

def find_no_embedding_substrates(medium_filter=None):
    """Return list of (substrate_id, medium, filepath) lacking chunk #0 in vector DB."""
    from oskill.ingest_substrate import lancedb_path, _VECTOR_TABLE
    import lancedb

    vdb = lancedb.connect(str(lancedb_path()))
    tbl = vdb.open_table(_VECTOR_TABLE)

    data_root = pathlib.Path('/root/.stratum/data/substrate')
    missing = []

    for medium_dir in sorted(data_root.iterdir()):
        if not medium_dir.is_dir():
            continue
        if medium_filter and medium_dir.name != medium_filter:
            continue
        for f in sorted(medium_dir.iterdir()):
            if not f.is_file():
                continue
            substrate_id = f.name.split('--')[0]
            cnt = tbl.count_rows(filter=f"id = '{substrate_id}#0'")
            if cnt == 0:
                missing.append((substrate_id, medium_dir.name, str(f)))

    return missing


# ── 2. 获取 markdown 内容 ────────────────────────────────────────────────────────

def get_markdown(substrate_id: str) -> str | None:
    """Get markdown from shared export dir. Handles both naming conventions:
    - ULID-based: {substrate_id}.md  (old export path)
    - Title-based: {Title}_{substrate_id[:8]}.md  (omodul export convention)
    Falls back to triggering export_one when service is stopped (DuckDB accessible).
    """
    md_dir = pathlib.Path('/data/shared/stratum-to-aii')

    # Fast path: ULID-named file
    md_file = md_dir / f'{substrate_id}.md'
    if md_file.exists():
        content = md_file.read_text(encoding='utf-8', errors='replace').strip()
        if content:
            return content

    # omodul exports as {Title}_{substrate_id[:8]}.md — search by short ULID suffix
    short_id = substrate_id[:8]
    for candidate in sorted(md_dir.glob(f'*{short_id}*.md')):
        content = candidate.read_text(encoding='utf-8', errors='replace').strip()
        if content:
            return content

    # Slow path: trigger md export (requires DuckDB access — only works while service stopped)
    try:
        from stratum.services.md_export_service import export_one
        export_one(substrate_id)
        # After export, re-check both naming conventions
        if md_file.exists():
            content = md_file.read_text(encoding='utf-8', errors='replace').strip()
            if content:
                return content
        for candidate in sorted(md_dir.glob(f'*{short_id}*.md')):
            content = candidate.read_text(encoding='utf-8', errors='replace').strip()
            if content:
                log.info('  md from export_one: %d chars', len(content))
                return content
    except Exception as e:
        log.warning('  export_one failed: %s', e)

    return None


def get_markdown_from_oskill(substrate_id: str, file_path: str) -> str | None:
    """Use oskill's generate_derivative to get/regenerate markdown."""
    from oskill.ingest_substrate import generate_derivative
    import asyncio
    result = asyncio.run(generate_derivative(substrate_id, pathlib.Path(file_path), 'book'))
    return result.get('markdown')


# ── 3. 补 embedding ─────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 400, max_chunk_chars: int = 1400) -> list[str]:
    """Chunk text for embedding. Hard-limits each chunk to max_chunk_chars to stay within
    qwen3-embedding:0.6b's 4096-token context (1400 chars ≈ 2800 tokens for Chinese, safe)."""
    import re
    # Split on sentence endings AND paragraph/header breaks (catches tables, equations, code blocks)
    sents = re.split(r'(?<=[.!?。！？])\s+|\n{2,}|(?=\n#{1,3}\s)', text)
    chunks, current, current_len = [], [], 0
    for sent in sents:
        # Hard-split any sentence that would exceed the token limit alone
        if len(sent) > max_chunk_chars:
            if current:
                chunks.append(' '.join(current))
                current, current_len = [], 0
            for i in range(0, len(sent), max_chunk_chars):
                part = sent[i:i + max_chunk_chars].strip()
                if part:
                    chunks.append(part)
            continue
        wlen = len(sent.split())
        current_chars = sum(len(s) for s in current)
        if (current_len + wlen > chunk_size or current_chars + len(sent) > max_chunk_chars) and current:
            chunks.append(' '.join(current))
            current, current_len = [], 0
        current.append(sent)
        current_len += wlen
    if current:
        chunks.append(' '.join(current))
    return [c for c in chunks if c.strip()]


def embed_one(substrate_id: str, markdown: str) -> int:
    """Embed markdown and write to vector DB. Returns number of chunks embedded."""
    from oprim.embedding import embed_text
    from oprim._config import cfg
    from oprim.vector_db import open_vector_db, VectorRecord
    from oskill.ingest_substrate import lancedb_path, _VECTOR_TABLE, _VECTOR_DIM

    chunks = _chunk_text(markdown)
    if not chunks:
        log.warning('  No chunks for %s', substrate_id)
        return 0

    provider = str(cfg.get('EMBEDDING_PROVIDER', 'qwen3_dashscope'))
    embeddings = embed_text(chunks, provider=provider, dim=_VECTOR_DIM)

    vdb_path = lancedb_path()
    vdb_path.mkdir(parents=True, exist_ok=True)
    vdb = open_vector_db(vdb_path, table_name=_VECTOR_TABLE, dim=_VECTOR_DIM)
    records = [
        VectorRecord(
            id=f'{substrate_id}#{i}',
            embedding=emb,
            metadata=json.dumps({'substrate_id': substrate_id, 'chunk_idx': i}),
        )
        for i, emb in enumerate(embeddings)
    ]
    vdb.upsert(records)
    return len(records)


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='Test DashScope + count missing')
    parser.add_argument('--run', action='store_true', help='Actually run re-embedding')
    parser.add_argument('--medium', help='Filter: book|paper|other')
    parser.add_argument('--limit', type=int, default=0, help='Max substrates to process (0=all)')
    args = parser.parse_args()

    # Test embedding provider
    if args.test:
        from oprim._config import cfg
        provider = str(cfg.get('EMBEDDING_PROVIDER', 'qwen3_dashscope'))
        log.info('Testing embedding provider: %s', provider)
        try:
            from oprim.embedding import embed_text
            result = embed_text(['test calculus vector embedding'], provider=provider, dim=1024)
            log.info('  %s OK, dim=%d', provider, len(result[0]))
        except Exception as e:
            log.error('  %s FAILED: %s', provider, e)
            if provider == 'qwen3_dashscope':
                log.error('  → Recharge DashScope account or switch EMBEDDING_PROVIDER=qwen3_local')
            elif provider == 'qwen3_local':
                log.error('  → Check Ollama is running: ollama list | grep qwen3-embedding')
            return 1

        log.info('Counting substrates without embedding...')
        missing = find_no_embedding_substrates(args.medium)
        log.info('  Missing embeddings: %d substrates', len(missing))
        by_medium = {}
        for sid, med, _ in missing:
            by_medium[med] = by_medium.get(med, 0) + 1
        for m, c in sorted(by_medium.items()):
            log.info('    %s: %d', m, c)
        return 0

    if not args.run:
        print(__doc__)
        return 0

    # Run re-embedding
    log.info('Finding substrates without embedding...')
    missing = find_no_embedding_substrates(args.medium)
    log.info('Found %d substrates to re-embed', len(missing))

    if args.limit:
        missing = missing[:args.limit]
        log.info('(Limited to first %d)', args.limit)

    md_dir = pathlib.Path('/data/shared/stratum-to-aii')
    ok, skipped, failed = 0, 0, 0

    for i, (substrate_id, medium, filepath) in enumerate(missing, 1):
        log.info('[%d/%d] %s (%s)', i, len(missing), substrate_id, medium)

        # Get markdown
        markdown = get_markdown(substrate_id)
        if markdown:
            log.info('  md: %d chars', len(markdown))

        if not markdown:
            log.warning('  No markdown found, skipping')
            skipped += 1
            continue

        try:
            n_chunks = embed_one(substrate_id, markdown)
            log.info('  Embedded %d chunks', n_chunks)
            ok += 1
        except Exception as e:
            log.error('  Failed: %s', e)
            failed += 1
            if 'Arrearage' in str(e) or 'Access denied' in str(e):
                log.error('  → DashScope still overdue, aborting')
                break

        time.sleep(0.5)  # rate limit

    log.info('Done: ok=%d skipped=%d failed=%d', ok, skipped, failed)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
