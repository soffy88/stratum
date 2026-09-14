# AII — Personal Knowledge Infrastructure

把你读过、研究过和理解过的东西，
变成持续生长、可追溯、可检索、可复用的个人知识系统。

**https://aiinote.com**

> 历史仓库名 `stratum` 仅作为实现壳保留（`src/stratum/`、`stratum-sl` 容器）。
> 产品与架构主语统一为 **AII**。详见 `docs/AII_ARCHITECTURE_CONTRACT.md`。

---

## AII 是什么

AII 不是 PDF 编辑器、普通笔记软件或"带 AI 的资料库"。那些只是 Capture / Experience 层；AII 的核心是 **Personal Knowledge Infrastructure**：

- **多源摄取** — PDF、网页、RSS、论文、Markdown、EPUB、图片
- **Evidence-grounded 理解** — 每个 AI 结论可追溯到原文 Fragment → Source
- **知识图谱** — Concept / Relation 单一 authority，Relation 必须带 provenance
- **混合检索** — lexical + dense + graph + temporal + user-authored + learning，统一 `KnowledgeView` contract
- **学习层** — BU 作为 Learning Projection（不是第二套事实库）
- **自主飞轮** — 8 个领域飞轮持续把新资料编译为 32k KU
- **Skill 导出** — 可携带 `concept_refs / claim_refs / evidence_refs / source_refs` 的可复用知识包
- **Provenance** — 任何知识都知道谁是 authority、从哪里来、谁写的、怎么被检索、怎么被修正
- **个人所有权** — 你删 = 真删；user/AI ownership 永不混淆

北极星：**WUKR（Weekly Useful Knowledge Reuse，周度有效知识复用）**

当前版本: **v1.0 OSS baseline**。实现目录仍叫 `src/stratum/`，但产品、API
和文档的 canonical 名称是 **AII**。

---

## 核心闭环

| 阶段 | 能力 |
|---|---|
| Acquire | 上传文件 / URL 抓取 / RSS 订阅 / AI 研究员 |
| Parse | 稳定 Fragment + anchor + content_hash + version |
| Understand | Evidence → Claim（必须 grounded），Concept/Relation 唯一 authority |
| Ground | 引用链 Claim → Evidence → Fragment → Source 永远可追溯 |
| Structure | Concept/Relation 单一表，禁止平行权威 |
| Connect | 图谱 neighborhood + 反向链接 |
| Retrieve | 统一 KnowledgeView（search / retrieve / companion / agent / skill 同一底层） |
| Learn | LearningObject 投影 + FSRS 复习 + Skill 复用 |

---

## 技术栈（真实）

- **前端**: Next.js 15 + TypeScript + Tailwind + @helios/blocks + ReactFlow
- **后端**: FastAPI + Python 3.14 + **PostgreSQL + pgvector** (canonical store `aii_kg`)
- **索引**: pgvector `vector(1024)` 为 dense authority；Tantivy/LanceDB 仅作可选 rebuildable projection
- **AI**: DashScope (Qwen3) + edge-tts + wanxiang
- **基础库**: obase / oprim / oskill / omodul (3O paradigm)
- **部署**: Docker Compose + Cloudflare Tunnel + nginx

> LanceDB / DuckDB 已不再是 canonical runtime；详见 `docs/AII_ARCHITECTURE_CONTRACT.md §5`

---

## Fresh-machine install

唯一推荐的可移植启动路径是 Docker Compose。它只要求一台安装了 Docker
Compose v2 的 Linux/macOS 主机，不依赖固定开发者路径、本地 Python 环境
或开发者的 3O checkout。

```bash
git clone <canonical-repository-url> aii
cd aii
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env，至少设置 AII_DB_PASSWORD、JWT_SECRET 和 AII_PUBLIC_ORIGIN
docker compose --env-file deploy/.env -f deploy/docker-compose.oss.yml up -d --build
docker compose --env-file deploy/.env -f deploy/docker-compose.oss.yml run --rm api \
  python -m stratum.db.run_pg_migrations upgrade
curl -fsS http://127.0.0.1:9302/health
```

配置、迁移、备份和恢复合同见 [`docs/deployment-contract.md`](docs/deployment-contract.md)。

## 本地开发

```bash
# Backend (AII API :9302; PostgreSQL required)
uv sync
uv run python -m stratum.db.run_pg_migrations upgrade
uv run python -m pytest tests/ -q
uv run python scripts/check_aii_naming.py --all   # AII 命名收敛门禁

# Frontend
cd aii-web && pnpm install && pnpm dev            # http://localhost:3101

# Docker 全栈
cd deploy && docker compose up -d
```

环境变量由 `deploy/.env` 或部署平台 secret store 提供；不要把 secret 写进仓库。
DashScope 是可选 provider，未配置时不应阻止 core boot。PostgreSQL 的
`STRATUM_PG_*` 连接唯一 canonical authority DB。
Legacy `:9302` 的 CORS 通过 `STRATUM_CORS_ALLOWED_ORIGINS` 显式 allowlist。
JWT 轮换: `JWT_SECRETS=new,old`（首个签发，全部验证）。

---

## 知识宪法

- `docs/AII_ARCHITECTURE_CONTRACT.md` — 唯一知识对象契约 + 六项 contract + provenance + KnowledgeView
- `src/stratum/knowledge/contract.py` — 机器可读权威定义
- `src/stratum/knowledge/provenance.py` — provenance 校验
- `src/stratum/services/knowledge_view.py` — 唯一检索平面
- `tests/architecture/test_aii_closure.py` — 18 项架构收敛测试

---

## 反馈

页面右下角 FeedbackWidget，或 `wiki@helios-plat.com`。

## OSS governance

- [Deployment contract](docs/deployment-contract.md)
- [Observability](docs/observability.md)
- [Backup and restore](docs/backup-restore.md)
- [Privacy and retention](docs/privacy-retention.md)
- [Contributing](CONTRIBUTING.md)
