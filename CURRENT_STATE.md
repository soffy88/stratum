# CURRENT_STATE.md — AII 现状快照

> 生成于 2026-08-30。本文件只描述**现在**；历史演变见 `CHANGELOG.md`；
> 未来计划见 `ROADMAP.md`；已知技术债见 `TECHNICAL_DEBT.md`。
>
> 代号：AII — Personal Knowledge Infrastructure（`https://aiinote.com`）
> 仓库名 `stratum` 为历史实现壳，产品与架构主语已收敛至 **AII**（见 `docs/AII_ARCHITECTURE_CONTRACT.md`）。

## 一句话现状

**AII** 10/10 Architecture Closure 已完成：Canonical Knowledge Model、Provenance Graph、KnowledgeView 唯一检索平面、PostgreSQL + pgvector 权威收敛、AII 命名收敛、BU/Skill 溯源均已落地并由 `tests/architecture/test_aii_closure.py` 18项门禁守护。
飞轮链路（econ/math/paper/cs/misc/advmath/edu）在 `aii_kg` 上持续生产（32k KU，总队列表现在本轮审计中确认）。

## 生产在跑

- **AII Service Layer `stratum-sl` (:9304)**：唯一生产主入口（`AII Service Layer`），CORS 显式 allowlist（含 `aiinote.com`）。
- **legacy `:9302`**（`stratum-api`）：仅作 `/api/auth/*` 与裸 `/api/search` 兼容 fallback；`GET /api/notes/{id}` 已优先读取 `notes_sl`，真实 PG HTTP E2E 仍需部署验证。
- **AII 各飞轮**：`aii-flywheel-{econ-zh,misc,math-prog,paper,advmath,cs,edu}` 常驻 systemd，`aii-feeder` + `aii-gdrive-mount` 持续喂书；`aii-postgres:5435` + `aii-refined-postgres:5436` 健康；`aii-embed` 已迁笔记本（`ALLOW-AII-GPU` 条件），本机 CPU fallback。
- **检索平面**：`POST /api/v1/search`（fused）与 `POST /api/v1/retrieve` 均可经 `src/stratum/services/knowledge_view.py` 统一为 `KnowledgeView`（scope/user isolation/ranking/citation/provenance/filtering/result schema 一致）。

## 本轮 Closure 交付（2026-08-30）

- 新增 `docs/AII_ARCHITECTURE_CONTRACT.md`：Source/Fragment/Evidence/Claim/Concept/Relation/Note/Annotation/LearningObject/Skill 的八对象 + 六项 contract（owner/authority/lifecycle/version/provenance/projection）
- 新增 `src/stratum/knowledge/contract.py` + `src/stratum/knowledge/provenance.py`（机器可读宪法 + 校验）
- 新增 `src/stratum/services/knowledge_view.py`：`KnowledgeViewRequest/Result` + `search_knowledge_view` + `validate_result_schema`
- 新增 `src/stratum/services/skill_provenance.py`：`build_skill_manifest` + `is_skill_stale`（BU/skill 不成为第二 authority 的溯源检测）
- 新增 `scripts/check_aii_naming.py` 并接入 `.github/workflows/ci.yml`（禁止新增 `Stratum Knowledge/Agent/Layer/Runtime` 产品命名，回退至 `src/stratum` 路径与 `stratum-sl` 容器 allowlist）
- 新增 `tests/architecture/test_aii_closure.py` 18项门禁（Source/Fragment/Evidence/Claim/Note/Concept/Relation/BU/Skill/Retrieval/user isolation/projection rebuild/correction/stale/naming/DB/result schema/citation）
- `README.md` 重写为 AII 第一屏（`https://aiinote.com`，真实技术栈 PostgreSQL+pgvector，可选 Tantivy/LanceDB 仅 projection）
- `TECHNICAL_DEBT.md` 按 `still_open/already_fixed/obsolete/superseded` 重分类，旧 DuckDB/LanceDB/Tantivy/Stratum 命名债务归入 obsolete，已修复项指针保留
- `src/stratum/api/main.py` title 收敛至 `AII Service Layer`
- 历史债务与旧 Stratum 品牌材料归档预留 `docs/history/`（本轮仅预留目录，不批量搬运以控风险）

## 已知边界（非阻塞，人工/部署验收）

- Retrieval 真实 50–100 条 reviewed gold 与 baseline；parser 20–30 份真实 gold + OmniDocBench/olmOCR-Bench 实跑仍为候选（`scripts/check_eval_manifest_readiness.py` 明确 false）
- Concept 四表 / Relation 三表的全量 merge 仍需人工批准（`scripts/plan_legacy_knowledge_merge.py` 026/027 ledger 仅候选）
- `cx.learning_*` 多用户迁移与事件回填仍需可信身份映射（`scripts/plan_personal_model_migration.py` 仅 dry-run 候选）
- 部署 PostgreSQL 019–028、trigger/OpenAPI/并发 E2E、真实支付/TTS/五入口 UX 仍需部署环境执行
- aiinote.com DNS 与 SEARXNG 实例仍为占位，代码路径就绪等 env

## 🔒 Never（架构红线，绝对遵守）

- 总结覆盖原文；无锚点的「知识合并」。
- MVP 范围外功能抢主路径。
- 公网入口绕开 **aegis-caddy:8086**。
- 未过对抗金集的 B仓自动强并。
- 参见 `docs/AII_ARCHITECTURE_CONTRACT.md` 与 `src/stratum/knowledge/contract.py` 的六项 contract —— 任何知识都知道谁是 authority、从哪里来、谁写的、怎么被检索、怎么被修正。

## 参考

- 架构宪法: `docs/AII_ARCHITECTURE_CONTRACT.md`
- 机器契约: `src/stratum/knowledge/contract.py` + `src/stratum/knowledge/provenance.py`
- 统一检索: `src/stratum/services/knowledge_view.py` + `src/stratum/services/skill_provenance.py`
- 知识对象现状: `KNOWLEDGE_MODEL.md`
- 技术债: `TECHNICAL_DEBT.md`
- 未来路线: `ROADMAP.md`
