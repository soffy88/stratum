#!/usr/bin/env python3
"""统一 user_id 存储格式: 把混存的原始 user_id 改写为 hash_user_id 格式 (审计 🟡19).

背景
----
``substrates`` / ``evidence`` 两张表同时存在两种 user_id:
  - 哈希值: ``hash_user_id(raw) = sha256(raw).hexdigest()[:16]`` (新写入路径)
  - 原始值: JWT ``sub`` (ULID 或 email, 历史写入路径)
读取侧到处是 ``user_id = ? OR user_id = ?`` / ``user_id IN (?, ?)`` 兼容分支,
越权检查容易漏掉其中一种. 本脚本把原始值一次性改写为哈希值, 之后才能删掉 OR 分支.

安全性
------
* **默认 dry-run**: 只做 SELECT 统计, 不写库. 必须显式 ``--apply`` 才会执行 UPDATE.
* ``--apply`` 时整个迁移在单个事务里: 先把将被改写的 (表, 主键, 旧 user_id) 备份到
  ``stratum.user_id_migration_backup``, 再 UPDATE, 最后复核; 任何一步失败整体回滚.
* 主键冲突/唯一约束冲突会在 dry-run 中预先报出 (同一逻辑用户的 raw 行与 hash 行在
  唯一键上撞车), 有冲突时 ``--apply`` 拒绝执行, 需人工处理.
* DSN 只从环境变量 ``STRATUM_PG_DSN`` (或 ``--dsn``) 读取, 脚本内不含任何默认密码.

用法
----
    STRATUM_PG_DSN=postgresql://... python scripts/migrate_unify_user_id_hash.py            # dry-run
    STRATUM_PG_DSN=postgresql://... python scripts/migrate_unify_user_id_hash.py --json     # dry-run, JSON 输出
    STRATUM_PG_DSN=postgresql://... python scripts/migrate_unify_user_id_hash.py --apply    # 真正执行 (先备份库!)

回滚
----
    UPDATE stratum.<table> t SET user_id = b.old_user_id
      FROM stratum.user_id_migration_backup b
     WHERE b.table_name = '<table>' AND b.row_pk = t.id::text AND b.run_id = '<run_id>';
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone

# 混存表 (见 src/stratum/services/personal_model.py::_OBJECT_OWNERS 中 raw_or_hash 的条目,
# 以及 routers/substrates.py、routers/knowledge.py、services/document_deletion.py 的 OR 分支).
DEFAULT_TABLES = ("substrates", "evidence")
SCHEMA = "stratum"
HASH_RE = "^[0-9a-f]{16}$"
# PG 端与 stratum.utils.user_id_hash.hash_user_id 等价的表达式
PG_HASH_EXPR = "left(encode(sha256(convert_to(user_id, 'UTF8')), 'hex'), 16)"
BACKUP_TABLE = f"{SCHEMA}.user_id_migration_backup"


def py_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _unique_key_sets(cur, table: str) -> list[list[str]]:
    """返回包含 user_id 列的唯一约束/唯一索引的列集合 (用于冲突预检)."""
    cur.execute(
        """
        SELECT array_agg(a.attname ORDER BY k.ord)
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
         WHERE n.nspname = %s AND c.relname = %s AND i.indisunique
         GROUP BY i.indexrelid
        """,
        (SCHEMA, table),
    )
    return [cols for (cols,) in cur.fetchall() if "user_id" in cols]


def analyze_table(cur, table: str) -> dict:
    fq = f"{SCHEMA}.{table}"
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name='user_id')",
        (SCHEMA, table),
    )
    if not cur.fetchone()[0]:
        return {"table": table, "skipped": "no user_id column / table missing"}

    cur.execute(
        f"SELECT count(*), "
        f"count(*) FILTER (WHERE user_id ~ %s), "
        f"count(*) FILTER (WHERE user_id IS NOT NULL AND user_id !~ %s), "
        f"count(*) FILTER (WHERE user_id IS NULL), "
        f"count(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL AND user_id !~ %s) "
        f"FROM {fq}",
        (HASH_RE, HASH_RE, HASH_RE),
    )
    total, hashed, raw, null, distinct_raw = cur.fetchone()

    # 抽样校验 PG 哈希表达式与 Python 实现一致
    cur.execute(
        f"SELECT user_id, {PG_HASH_EXPR} FROM {fq} "
        f"WHERE user_id IS NOT NULL AND user_id !~ %s LIMIT 20",
        (HASH_RE,),
    )
    hash_mismatch = sum(1 for raw_v, pg_h in cur.fetchall() if py_hash(raw_v) != pg_h)

    conflicts = []
    for cols in _unique_key_sets(cur, table):
        other = [c for c in cols if c != "user_id"]
        join_other = " AND ".join(f"h.{c} IS NOT DISTINCT FROM r.{c}" for c in other) or "TRUE"
        cur.execute(
            f"SELECT count(*) FROM {fq} r JOIN {fq} h "
            f"ON h.user_id = left(encode(sha256(convert_to(r.user_id, 'UTF8')), 'hex'), 16) "
            f"AND {join_other} "
            f"WHERE r.user_id !~ %s",
            (HASH_RE,),
        )
        n = cur.fetchone()[0]
        if n:
            conflicts.append({"unique_key": cols, "conflicting_rows": n})

    return {
        "table": table,
        "total_rows": total,
        "hashed_rows": hashed,
        "raw_rows_to_rewrite": raw,
        "null_user_id_rows": null,
        "distinct_raw_user_ids": distinct_raw,
        "hash_expr_mismatch_in_sample": hash_mismatch,
        "unique_conflicts": conflicts,
    }


def apply_table(cur, table: str, run_id: str) -> int:
    fq = f"{SCHEMA}.{table}"
    cur.execute(
        f"INSERT INTO {BACKUP_TABLE} (run_id, table_name, row_pk, old_user_id, new_user_id) "
        f"SELECT %s, %s, id::text, user_id, {PG_HASH_EXPR} FROM {fq} "
        f"WHERE user_id IS NOT NULL AND user_id !~ %s",
        (run_id, table, HASH_RE),
    )
    backed_up = cur.rowcount
    cur.execute(
        f"UPDATE {fq} SET user_id = {PG_HASH_EXPR} "
        f"WHERE user_id IS NOT NULL AND user_id !~ %s",
        (HASH_RE,),
    )
    updated = cur.rowcount
    if updated != backed_up:
        raise RuntimeError(f"{table}: backed up {backed_up} rows but updated {updated}")
    cur.execute(f"SELECT count(*) FROM {fq} WHERE user_id IS NOT NULL AND user_id !~ %s", (HASH_RE,))
    left = cur.fetchone()[0]
    if left:
        raise RuntimeError(f"{table}: {left} raw rows remain after update")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dsn", default=os.getenv("STRATUM_PG_DSN"), help="默认读 STRATUM_PG_DSN")
    ap.add_argument("--tables", default=",".join(DEFAULT_TABLES), help="逗号分隔, 默认 substrates,evidence")
    ap.add_argument("--apply", action="store_true", help="真正执行 UPDATE (默认只 dry-run 统计)")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出统计")
    args = ap.parse_args()

    if not args.dsn:
        print("需要 --dsn 或环境变量 STRATUM_PG_DSN", file=sys.stderr)
        return 2
    tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    for t in tables:
        if not t.replace("_", "").isalnum():
            print(f"非法表名: {t!r}", file=sys.stderr)
            return 2

    import psycopg2  # 延迟导入, 便于在无驱动环境下 --help

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if not args.apply:
                cur.execute("SET TRANSACTION READ ONLY")
            report = [analyze_table(cur, t) for t in tables]
            total_raw = sum(r.get("raw_rows_to_rewrite", 0) for r in report)
            blocked = [r for r in report if r.get("unique_conflicts") or r.get("hash_expr_mismatch_in_sample")]

            if args.json:
                print(json.dumps({"mode": "apply" if args.apply else "dry-run", "tables": report,
                                  "total_rows_to_rewrite": total_raw}, ensure_ascii=False, indent=2))
            else:
                print(f"mode: {'APPLY' if args.apply else 'dry-run (只读, 未写库)'}")
                for r in report:
                    print("  " + json.dumps(r, ensure_ascii=False))
                print(f"total rows to rewrite: {total_raw}")

            if not args.apply:
                conn.rollback()
                return 0
            if blocked:
                print("存在唯一约束冲突或哈希表达式不一致, 拒绝执行; 请先人工处理:", file=sys.stderr)
                for r in blocked:
                    print("  " + json.dumps(r, ensure_ascii=False), file=sys.stderr)
                conn.rollback()
                return 3

            run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} ("
                "run_id text NOT NULL, table_name text NOT NULL, row_pk text NOT NULL, "
                "old_user_id text NOT NULL, new_user_id text NOT NULL, "
                "migrated_at timestamptz NOT NULL DEFAULT now())"
            )
            for t in tables:
                n = apply_table(cur, t, run_id)
                print(f"  {t}: rewrote {n} rows")
            conn.commit()
            print(f"done. run_id={run_id} (回滚见脚本文档)")
            return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
