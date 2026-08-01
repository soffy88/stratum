# AII Note / Stratum MVP — 代码审计续篇

**日期**: 2026-07-29  
**范围**: MVP 第 1–6 周新落地代码 + 并行 OpenViking 层（layers / retrieval / sessions / metrics / cornell / vault）  
**性质**: 安全 / 多租户隔离 / 数据完整性 / 测试缺口（非产品愿景差距；愿景见 `STRATUM_REALITY_AUDIT_v1.0.md`）  
**方法**: 静态通读服务层 + 路由 + 单测；不替换人工 E2E

---

## 摘要

| 等级 | 数量 | 主题 |
|------|------|------|
| **P0** | 5 | 跨用户读/写（IDOR）：layers、retrieval、sessions、trajectory、folder_watch 任意路径 |
| **P1** | 6 | vault 默认根过宽、export 相对路径未防逃逸、metrics 全局泄露、康奈尔机器笔记可删、概念图 user_id 混用、账户删除与 STATUS 表述不一致 |
| **P2** | 5 | purge 级联不全、vault export 无配额、测试多为 mock、rate limit 无 vault/export 特判、硬删后 orphan 引用 |

**做得好的部分**

- Notes / concepts 默认 hard-delete 有 `user_id` 校验；`purge_substrate` 接受 raw + hash。
- Vault 路径有 `assert_safe_vault_path` + 单测拒绝 `/etc/passwd`。
- Vault ZIP 导出用 `_slug` 清洗文件名；`export/markdown` 有 medium allowlist。
- `knowledge_lint` / `daily_digest` 按 user 过滤并写 notes_sl。
- AII 路由 API key + 独立限流；inbox delete 走 purge。

---

## P0 — 必修（多租户 / 任意路径）

### P0-1 · Layers API 无所有权校验（读 + 生成）

**文件**: `src/stratum/api/routers/layers.py`

- `POST /layers/generate`：仅 `SELECT title, source_path FROM substrates WHERE id = ?`，**不**校验 `user_id`。
- `GET /layers/substrate/{id}`：任意登录用户可读任意 substrate 的 L0/L1/L2。
- `GET /layers/ku/{id}`：全库 KU 层可读（若 B 仓共享可接受，需在 SPEC 中明确）。
- 生成路径还会按 `source_path` 读服务器本地文件（`.md/.txt/...`），无 path allowlist。

**影响**: 用户 A 猜到/枚举 substrate_id → 读 B 的摘要与正文层；可能触发对他人文档的 LLM 生成（成本 + 隐私）。

**建议**: 与 `substrates.py` 一致：`user_id = hash OR raw`；生成前 `403/404`；`source_path` 仅允许用户 inbox 或配置 roots。

---

### P0-2 · Retrieval 跨用户混合检索

**文件**: `src/stratum/services/retrieval_engine.py`  
- `_vector_search_layers` / `_text_search_layers`：`FROM substrate_layers WHERE layer=?` **无 user 过滤**。  
- 调用方 `retrieve(..., user_id=)` 只用于 trajectory 日志，不参与候选过滤。

**影响**: 混合检索 / agent context 可能返回他人文档片段 → 隐私与合规事故。

**建议**: layers 表关联 substrates 后 `WHERE s.user_id IN (uh, uid)`；或 layers 冗余 `user_id` 并建索引。

---

### P0-3 · Sessions 无所有权：读/删/写消息

**文件**:  
- `src/stratum/api/routers/sessions.py` — `get_session` / `delete_session` / `add_message` / `get_messages` / `archive` / `working-memory` 未比对 `user_id`。  
- `src/stratum/services/session_manager.py` — `delete_session(session_id)` 直接 DELETE，无 owner 参数。

**影响**: 知 session_id → 读对话、注入消息、删他人会话。

**建议**: 所有 mutating/reading 路径：`WHERE id=? AND user_id=?`；服务层函数强制 `user_id` 参数。

---

### P0-4 · Retrieval trajectory 跨用户读

**文件**: `src/stratum/api/routers/retrieval.py` `GET /trajectory/{id}`  
- `get_trajectory(id)` 不返回/不校验 `user_id`。

**影响**: 可读取他人查询与结果摘要（含内容片段）。

**建议**: SELECT 带 `user_id`，不匹配则 404。

---

### P0-5 · Folder watch 任意服务器路径

**文件**: `src/stratum/api/routers/folder_watch.py`  
- `body.path` 原样入库；扫描 `Path(path).rglob`，**无** `STRATUM_VAULT_SYNC_ROOTS` 类 allowlist。

**影响**: 登录用户可让服务端递归读任意可读目录并 ingest（SSRF 类本地文件读 + 磁盘/LLM 成本）。

**建议**: 复用 `assert_safe_vault_path`（或更严的 `STRATUM_FOLDER_WATCH_ROOTS`）；拒绝 `..` 与 symlink 逃逸。

---

## P1 — 尽快修

### P1-1 · Vault 默认可写根过宽

**文件**: `src/stratum/services/vault_sync_service.py`  
`_DEFAULT_ROOTS = "/data/shared:/mnt/user:/home:/root/.stratum:/tmp/aii-vault"`

- 含 **`/home`**：多用户机上可写/读他户 home 下任意子路径（resolve 后仍在 root 下即通过）。  
- 含宽 `/data/shared`：多租户共享挂载时互踩。

**建议**: 生产默认仅 ` /tmp/aii-vault` 或强制 env；每个用户子目录 `/{uid_hash}/`。

---

### P1-2 · Vault export 相对路径未二次校验（潜在写逃逸）

**文件**: `export_vault_to_path`：`dest = root / rel` 后 `write_text`，**未** `resolve().relative_to(root)`。

当前 `build_vault_files` 用 `_slug` 生成 rel，自身较安全；若将来 rel 来自 DB 标题异常或恶意扩展，`../` 可逃出 vault 根（已用 Python 验证 `root/"../x"` escape）。

**建议**: 写盘前统一：

```python
dest = (root / rel).resolve()
dest.relative_to(root)  # ValueError → skip/raise
```

import 侧已限制在 `notes_dir.rglob`，风险较低。

---

### P1-3 · Metrics 全局可见

**文件**: `src/stratum/api/routers/metrics.py`  
任意 JWT 可 `GET /api/v1/metrics` / Prometheus 文本。

**建议**: admin only 或内网；至少去掉用户可访问的 Prometheus 端点。

---

### P1-4 · Cornell 机器笔记任意登录用户可软删

**文件**: `src/stratum/api/routers/cornell.py` `delete_cornell`  
`source == "machine"` 时 `pass`，注释写「暂允许登录用户软删」。

**影响**: 共享机器笔记可被任意用户删除（破坏公共题库）。

**建议**: machine → 403 或 admin role；human 维持本人。

---

### P1-5 · Concepts 关联 substrates 的 user_id 混用

**文件**: `concepts.py`  
`WHERE $cid = ANY(concept_refs) AND user_id = $uid` 使用 **raw** JWT sub。  
substrates 入库普遍为 **hash**（见 inbox/substrates）。

**影响**: related_substrates / graph 边常为空（功能回归），非直接越权。

**建议**: `user_id IN (uid, uh)` 与 substrates 路由一致。

---

### P1-6 · 账户删除策略文档不一致

- `STATUS.md` Backlog：账户删除「soft + 30 天 grace」。  
- `account.py`：对 notes/concepts/substrates **立即 hard purge**（账户 tombstone 仍保留）。

**建议**: 二选一更新文档或代码；若真删，确认是否清理 agent_runs、folder_watches、memories、sessions、changefeed。

---

## P2 — 技术债 / 质量

| ID | 问题 | 位置 |
|----|------|------|
| P2-1 | `purge_concept` / `purge_note` 不清理反向引用、wikilinks、graph 边 | `purge_service.py` |
| P2-2 | `purge_substrate` 子表列表可能漏 `search_*` / annotations / bookmarks | 同上 |
| P2-3 | 整库 ZIP 无体积/条目上限 → 大户 DoS | `export.py` + `vault_export_service` |
| P2-4 | week56 测试几乎全 mock，无 IDOR / 集成测 | `tests/service_layer/test_mvp_week56.py` |
| P2-5 | `hard_delete`/`execute` 表名 f-string：当前调用点常量安全；禁止外部传入 table | `db/__init__.py` |

---

## 已核对通过（本轮）

| 区域 | 结论 |
|------|------|
| Notes CRUD + hard/soft delete | Owner 校验正确；默认 hard |
| Concepts delete | Owner 校验正确 |
| Substrate delete via substrates/inbox | hash+raw 校验 + purge cascade 尽力 |
| Vault path reject `/etc/passwd` | 单测覆盖 |
| Vault ZIP slug | 过滤危险字符 |
| Lint / daily digest 写笔记 | 按 user_id |
| Agents lint/digest 入口 | 走 jwt_auth + native agents |
| api-client timeout | 已 60s（源码；镜像需 rebuild） |
| Rate limit 默认 60/min/user | 存在；export 未特判 |

---

## 与 2026-06 愿景审计的关系

旧文档 `STRATUM_REALITY_AUDIT_v1.0.md` 偏产品完成度。自那以后 MVP 周包补齐了：vault 导出/同步、真删、lint、日报、检索锚点、Cornell、layers 等。

**当前阻塞公网的不是功能列表，而是：**

1. **多租户隔离缺口**（本审计 P0）  
2. **aiinote.com DNS**（STATUS Needs Human）  
3. **人工 E2E** 主链路  

---

## 建议修复顺序（1–2 天）

1. Sessions + trajectory 全路径加 `user_id`（改动面小、风险高）  
2. Retrieval / layers 查询 join substrates 过滤  
3. Folder watch + vault roots 收紧 + export rel 二次 resolve  
4. Cornell machine delete 403；metrics 限 admin  
5. 补 5–10 个 IDOR 单测（两个用户 fixture）  
6. 对齐 account delete 与 STATUS 文案  

---

## 命令备忘

```bash
# 现有 MVP 单测（不覆盖 IDOR）
pytest tests/service_layer/test_mvp_week1.py \
       tests/service_layer/test_mvp_week34.py \
       tests/service_layer/test_mvp_week56.py -q
```


---

## 修复状态（2026-07-29 同日落地）

| ID | 状态 | 说明 |
|----|------|------|
| P0-1 Layers | ✅ | `_assert_owns_substrate`；generate/get/fs-read substrate 校验 |
| P0-2 Retrieval | ✅ | vector/text search JOIN substrates + user filter |
| P0-3 Sessions | ✅ | get/delete/archive/messages/context 强制 user_id |
| P0-4 Trajectory | ✅ | `get_trajectory(id, user_id=)` |
| P0-5 Folder watch | ✅ | `assert_safe_watch_path` |
| P1-1 Vault roots | ✅ | 默认仅 `/tmp/aii-vault` + `/root/.stratum` |
| P1-2 Export rel | ✅ | `_safe_dest_under_root` |
| P1-3 Metrics | ✅ | `X-Admin-Secret` / `ADMIN_SECRET` |
| P1-4 Cornell machine | ✅ | 403 |
| P1-5 Concepts user_id | ✅ | raw OR hash |
| vfs tree/ls 全局 | ⏳ | `context_directory` 无 user 列，未做 schema 级隔离 |

单测：`tests/service_layer/test_mvp_security_idor.py`（25 passed with aii venv）。
