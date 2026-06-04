# Phase 17 实施前预核查报告

**日期**: 2026-06-03
**执行**: CC 只读核查 (R-4 不动代码)
**目的**: 暴露 17-A/17-B/17-C 真实状态，防止重复实施或漏洞假设

---

## 17-A: 输入 URL 抓网页 → substrate

### 后端 endpoint

**结论: 已存在，但模型是"客户端送 HTML"，不是"服务端抓 URL"**

```
POST /api/v1/inbox/web-clip
文件: src/stratum/api/routers/inbox.py:125
前缀: /api/v1/inbox (router prefix)
```

handler 接收 `url: str` + `html: str = None`（Form 参数）。流程：
1. 如果 `_HAS_INBOX` 为 False → 返回 `status: not_implemented`
2. 否则把 `html`（或空 HTML skeleton）写入 inbox dir，调用 `process_inbox_substrate`

**`_HAS_INBOX` 真实值: `True`** — `omodul.process_inbox_substrate` 可正常导入。

**实际工作路径已打通** — 路由存在、guard 满足、omodul 可调。

### omodul / oprim 符号

| 符号 | 状态 | 说明 |
|---|---|---|
| `omodul.ingest_web_clip` | ❌ 不存在 | omodul `__init__` 未导出 |
| `omodul.WebClipConfig` | ❌ 不存在 | 同上 |
| `oprim.parse_html` | ❌ 不存在 | oprim 顶层无 |
| `oprim.url_fetch` / `fetch_url` / `http_get` | ❌ 全不存在 | 服务端无 URL 抓取 |
| `omodul.knowledge.browser_extension.page_capture` | ✅ 存在 | **HTML → 纯文本提取**（readability + lxml），不是 URL fetcher |

### 核心差距

**服务端没有 URL → HTML 这一步**。`/web-clip` 接口设计预设客户端（浏览器扩展）负责抓取并把 HTML 发给服务端。若要支持"只输入 URL 服务端抓取"，需要：
- `oprim.fetch_url` 或 `oprim.http_get`（新增 oprim primitive）
- 或直接在 handler 里用 `httpx` / `aiohttp` 抓（更简单）

### 前端入口

**不存在**。stratum-web 无任何 URL 输入框 / web-clip 入口。属于纯新增前端工作。

### 17-A 真实工作量

| 项 | 状态 | 工作 |
|---|---|---|
| 后端路由 | ✅ 已有 | 无 |
| omodul 处理链 (_HAS_INBOX) | ✅ 已通 | 无 |
| 服务端 URL fetch | ❌ 缺 | 新增（~30 行 httpx） |
| 前端 URL 输入 UI | ❌ 缺 | 新增 |
| 前端调 /api/v1/inbox/web-clip | ❌ 缺 | 新增 |

---

## 17-B: 浏览器扩展真 wire

### 扩展代码真实状态

**扩展代码存在，已是独立 repo，但未 wire 到真实 Stratum API。**

- 位置: `~/projects/stratum-extension/` (独立 git repo，v0.2.0，commit `0cb7925`)
- 由 commit `7b9a3fce` 从 monorepo 剥出（2026-05-31）
- Manifest V3，名称 "Stratum Capture"，`permissions: ["activeTab"]`

**popup.js 真实内容（关键问题）**:
```js
// 发到 http://localhost:8000/api/v1/ingest  ← 错误端点
// 发 plain text content                     ← 不是 HTML + URL
// 无 Authorization header                   ← 无 auth
// 无 host_permissions for localhost:9305    ← Stratum 真实端口
```

**三处错误**:
1. 端点错: `/api/v1/ingest` → 应是 `/api/v1/inbox/web-clip`
2. 端口错: `localhost:8000` → 应是 `localhost:9305`（或 `stratum.uex.hk`）
3. 无 auth: 缺 `Authorization: Bearer <token>` header

### omodul.knowledge.browser_extension 真实状态

目录结构:
```
browser_extension/
├── __init__.py        # 导出 app, auth, page_capture, server, url_dedup
├── server.py          # FastAPI app: /ingest /sidebar-search /health (本地 sidecar 模式)
├── page_capture.py    # HTML → 纯文本 (readability + lxml), 已实现
├── url_dedup.py       # URL 规范化 + SQLite 去重 DB, 已实现
├── auth.py            # token 验证
└── __main__.py
```

**架构说明**: `browser_extension/server.py` 是一个**独立 FastAPI sidecar**（设计为本地跑在用户机器上），不是 Stratum 主 API 的一部分。扩展原设计是扩展 → 本地 sidecar → Stratum API。

这套 sidecar 模式未被 Stratum 主容器集成。

### 17-B 真实工作量

| 项 | 状态 | 工作 |
|---|---|---|
| 扩展代码骨架 (MV3) | ✅ 已有 | — |
| `page_capture.py` (HTML提取) | ✅ 已有 | — |
| `url_dedup.py` (去重) | ✅ 已有 | — |
| popup.js 端点 / 端口修正 | ❌ 错误 | 改 3 处 |
| auth token 注入 | ❌ 缺 | 新增（popup 读 token，header 注入）|
| `host_permissions` 修复 | ❌ 缺 | manifest.json 加 `host_permissions` |
| 发送 HTML（非纯文本） | ❌ 错误 | 改 popup 用 `document.documentElement.outerHTML` |
| sidecar vs 直连 Stratum 决策 | 未决 | 建议: 直连 Stratum，弃 sidecar 复杂度 |

---

## 17-C: RSS/Feed 跟踪

### SPEC v0.5 / v0.6 真实记录

**`feed` 在 SPEC 的含义是 `changefeed`（内部事件系统），不是 RSS 订阅。**

- SPEC v0.5 中所有 `feed` 出现 = `changefeed`（行为事件流）或 `/api/v1/content/feed`（平台内容列表，hevi 出品）
- SPEC v0.6 同：只有 `changefeed event 新类型` 条目
- **RSS / Atom / 订阅话题 = 0 次出现**

SPEC 确实没有规划 RSS 跟踪功能。这是纯新增，不在原设计范围。

### oprim / omodul RSS 真实状态

| 符号 | 状态 | 说明 |
|---|---|---|
| `oprim.fetch_rss` | ✅ 存在 | 已实现，但**是 stub** — 接收预取数据，不发 HTTP |
| `omodul.fetch_rss` / `omodul.*feed*` | ❌ 全不存在 | — |

**`oprim.fetch_rss` 真实实现**:
```python
async def fetch_rss(*, client: HttpClient, url: str) -> list[dict]:
    data = await client.get(url)         # 委托给 HttpClient
    if isinstance(data, list): return data
    return []                            # 实际上是一个未完成的 stub
```

HttpClient 的 `.get()` 返回 list 这个前提不成立（真实 HTTP 返回 bytes/str）。这个函数目前不能工作，需要加 feedparser 解析。

### 17-C 真实工作量

| 项 | 状态 | 工作 |
|---|---|---|
| `oprim.fetch_rss` 原型 | ⚠️ Stub，不可用 | 补 feedparser 解析 |
| omodul RSS agent | ❌ 缺 | 新增 |
| Stratum RSS endpoint | ❌ 缺 | 新增后端路由 |
| 订阅管理 DB 表 | ❌ 缺 | 新增 schema |
| 前端 RSS 订阅 UI | ❌ 缺 | 新增 |
| SPEC 支撑 | ❌ 无 | 需先写 mini-spec |

---

## 汇总: 真实工作量对比

| 功能 | 已有 | 真缺口 | 难度估计 |
|---|---|---|---|
| **17-A URL 抓网页** | 后端路由 + omodul 链 | 服务端 URL fetch + 前端 UI | **低** (~1天) |
| **17-B 浏览器扩展 wire** | 扩展骨架 + page_capture + url_dedup | popup 修复 (端点/端口/auth/HTML发送) | **低-中** (~0.5天) |
| **17-C RSS 跟踪** | oprim.fetch_rss stub | 几乎全部: agent + route + DB + UI + spec | **高** (~1周) |

### 建议实施顺序

1. **17-A** 最快可落地 — 后端已通，前端加 URL 输入框调 `/api/v1/inbox/web-clip` 即可
2. **17-B** 次之 — 扩展三处修复即可用，不需动 omodul
3. **17-C** 建议延后或列为独立 Phase — SPEC 未规划，工作量最大，依赖不存在的 omodul agent

---

*生成: CC Phase 17 预核查, 2026-06-03*
