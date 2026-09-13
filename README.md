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

当前版本: **alpha v1.0**，Knowledge Contract 已收敛见 `docs/AII_ARCHITECTURE_CONTRACT.md`

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

## 本地开发

```bash
# Backend (AII Service Layer :9304; PostgreSQL required)
uv sync
uv run python scripts/bootstrap_pg_schema.py
uv run python -m pytest tests/ -q
uv run python scripts/check_aii_naming.py --all   # AII 命名收敛门禁

# Frontend
cd stratum-web && pnpm install && pnpm dev        # http://localhost:3000
cd aii-web && pnpm install && pnpm dev            # http://localhost:3101

# Docker 全栈
cd deploy && docker compose up -d
```

环境变量见 `/home/soffy/.config/keys/.env` — 需要 `DASHSCOPE_API_KEY`, `JWT_SECRET`, `STRATUM_PG_*`。
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
