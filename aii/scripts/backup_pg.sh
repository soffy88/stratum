#!/bin/bash
# AII 知识库每日备份(今天最痛教训:数据不能只靠 volume)
set -e
BACKUP_DIR="$HOME/projects/AII/backups"
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$BACKUP_DIR/aii_kg_$STAMP.sql.gz"

# dump(容器内 pg_dump,gzip 压缩)
docker exec aii-postgres pg_dump -U aii -d aii_kg | gzip > "$OUT"
echo "[backup] $OUT ($(du -h "$OUT" | cut -f1))"

# 滚动保留最近 14 天,删更老的
find "$BACKUP_DIR" -name "aii_kg_*.sql.gz" -mtime +14 -delete
echo "[backup] 保留最近14天,当前 $(ls "$BACKUP_DIR"/aii_kg_*.sql.gz | wc -l) 份"
