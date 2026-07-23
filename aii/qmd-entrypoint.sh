#!/bin/sh
# qmd container entrypoint — register the read-only corpus collection once,
# then run the MCP HTTP daemon in the foreground (PID 1, so Docker can manage
# lifecycle/signals — NOT `--daemon`, that backgrounds and forks).
set -e

COLLECTION_NAME="${QMD_COLLECTION_NAME:-aii-books}"
CORPUS_DIR="${QMD_CORPUS_DIR:-/corpus}"

if ! qmd collection add "$CORPUS_DIR" --name "$COLLECTION_NAME" --mask '**/*.md'; then
  echo "[qmd-entrypoint] collection add failed or already exists for '$COLLECTION_NAME' — continuing" >&2
fi

# Embedding (first run downloads ~333MB embeddinggemma-300M over the proxy, then
# embeds every pending doc on CPU — can take minutes). Don't block MCP startup on
# it: BM25 keyword search already works without vectors, only `query`'s vector/
# hybrid modes need this. Runs once in the background; safe to re-run (only
# embeds pending docs).
( qmd embed > /root/.cache/qmd/embed.log 2>&1; echo "[qmd-entrypoint] embed exited $?" >> /root/.cache/qmd/embed.log ) &

exec qmd mcp --http --port 8181
