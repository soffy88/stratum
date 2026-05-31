# Stratum

**个人知识库 SaaS** — 多语料库、语义搜索、AI Agent 驱动的知识管理平台。

> 当前版本: **v1.0-alpha** (Phase 14 complete)

---

## 功能概览

- 多语料库隔离 (corpus isolation) — 每个用户拥有独立知识空间
- 混合搜索 (BM25 + 向量) — `oskill.hybrid_search` 驱动
- AI Agent 任务调度 — 定时任务 + 手动触发
- 文档树 / 反向链接 / 引用卡片 — `@helios/blocks` 前端组件
- 分享链接 (share tokens) — 公开只读访问
- 用户系统 — 注册 / 登录 / JWT 刷新 / 会话管理 / 个人资料

## 快速开始

### 注册

1. 访问 `https://your-domain/register`
2. 填写用户名、邮箱、密码
3. 登录后自动创建默认语料库

### 本地开发

```bash
# Backend
cd /path/to/stratum
python -m venv .venv && source .venv/bin/activate
pip install -e ".[servers,dev]"
uvicorn stratum.http_api.app:app --port 9305

# Frontend
cd stratum-web
pnpm install && pnpm dev
```

### Docker 部署

```bash
cd deploy
docker compose up -d
```

## 技术栈

| 层 | 技术 |
|---|---|
| Backend API | FastAPI + DuckDB + Python 3.14 |
| Frontend | Next.js 15 + React 19 + TailwindCSS + @helios/blocks |
| Search | oskill (BM25 + vector hybrid) |
| Auth | JWT (access + refresh) + bcrypt |
| Deploy | Docker Compose + Nginx reverse proxy |

## 项目结构

```
src/stratum/          # Python 后端
  http_api/           # FastAPI 路由 + schemas
  dao/                # 数据访问层 (DuckDB)
  service/            # 业务逻辑 (search, agents)
  auth/               # JWT + password
  middleware/         # rate-limit, corpus isolation, abuse detection
stratum-web/          # Next.js 前端
  src/app/            # App Router pages
  src/components/     # UI 组件 + @helios/blocks adapters
deploy/               # Docker + Nginx 配置
tests/                # pytest 214 tests
```

## API 文档

完整 API 规范见 [docs/STRATUM_API_v1.md](docs/STRATUM_API_v1.md) (27 routes, OpenAPI 3.1)。

## 相关独立 Repo

| Repo | 位置 | 说明 |
|------|------|------|
| stratum-cli | `~/projects/stratum-cli` | 命令行客户端 (Python, v0.1.0) |
| stratum-extension | `~/projects/stratum-extension` | 浏览器扩展 (Chrome/Edge, v0.2.0) |
| helios-blocks | Helios 独立 repo | 前端 UI 组件库 (@helios/blocks) |

> stratum-cli 和 stratum-extension 各为独立 git repo，不是本 repo 的 submodule。
> monorepo vs 独立 repo 整体策略待 v1.1 评估。

## 许可证

Private — Wiki 内部项目。
