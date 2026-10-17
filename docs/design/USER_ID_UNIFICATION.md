# user_id 存储格式统一（审计 🟡19）设计说明

状态：**提案，未执行**。本 PR 只提交迁移脚本 `scripts/migrate_unify_user_id_hash.py` 和本说明，没有对任何数据库运行过它，也没有改任何读写代码。

## 现状

- `stratum.utils.user_id_hash.hash_user_id(raw) = sha256(raw).hexdigest()[:16]`。
- `substrates`、`evidence` 两张表同时存在两种 user_id：16 位 hex 哈希（新写入）和 JWT `sub` 原值（历史写入，ULID 或 email）。
- 读取侧有 15 处兼容分支：`user_id = ? OR user_id = ?` / `user_id IN (?, ?)`。主要位置：
  `api/routers/substrates.py`（79/138/167/200）、`api/routers/knowledge.py`（86/94/434/469）、`api/routers/highlights.py:59`、`api/routers/quality.py:202`、`services/document_deletion.py`（78/501）、`services/personal_model.py`（48/131）、`utils/ownership.py:31`、`services/retrieval_engine.py`（`_user_owner_ids`）。
- `personal_model._OBJECT_OWNERS` 已经显式区分：`knowledge_claims`/`concepts`/`notes_sl` 存原值（raw），`highlights` 存哈希（hash），`substrates`/`evidence` 是混存（raw_or_hash）。

## 风险

- 新写的越权检查只要漏掉其中一种格式，就会出现“看不到自己的数据”或“多看到别人的数据”。
- 统计、迁移、按用户导出/删除都要记得双写双查。

## 方案

目标格式：**哈希**（与 oskill `InboxConfig.user_id_hash`、highlights 一致，且是当前写入路径）。

分三步，分别上线：

1. **数据迁移**（本脚本）：把 `substrates`、`evidence` 中非 16 位 hex 的 user_id 改写为 `left(encode(sha256(convert_to(user_id,'UTF8')),'hex'),16)`。
   - 默认 dry-run，只读事务，输出每表总行数、已是哈希的行数、**待改写行数**、不同原值用户数、唯一约束冲突数、PG/Python 哈希一致性抽样。
   - `--apply` 时单事务执行：先把（run_id、表、主键、旧值、新值）写入 `stratum.user_id_migration_backup`，再 UPDATE，再复核没有剩余原值；任一步失败整体回滚。存在唯一约束冲突或哈希不一致时拒绝执行。
   - DSN 只从 `STRATUM_PG_DSN` / `--dsn` 读取，脚本里没有默认密码。
2. **写入路径收口**：确认所有写 `substrates`/`evidence` 的代码都用 `hash_user_id()`（迁移后跑一次 dry-run，待改写行数应保持为 0；可以加一个 CHECK 约束 `user_id ~ '^[0-9a-f]{16}$'` 防止回退）。
3. **删 OR 分支**：把上面 15 处改为单值 `user_id = ?`（传哈希），`owner_ids()` / `_user_owner_ids()` 只返回哈希。这一步涉及路由权限代码，应和鉴权修复（🔴3/🔴4）协调后单独开 PR。

## 执行建议（需要人工决定）

1. 先在测试库（5435）跑 dry-run，再在生产库跑 dry-run，把输出贴进 issue。
2. 生产执行前做 `pg_dump` 备份，选低峰时段，执行 `--apply`。
3. 执行后观察一周，确认无回退写入，再做第 2、3 步。

## 不在本 PR 范围

- `knowledge_claims`/`concepts`/`notes_sl`（纯原值）和 `highlights`（纯哈希）格式各自一致，不迁移；是否统一到同一种格式另议。
- http_api 的 access token `sub` 是 email（🟡22），与 SL 的 ULID 不同源，本迁移不处理。
