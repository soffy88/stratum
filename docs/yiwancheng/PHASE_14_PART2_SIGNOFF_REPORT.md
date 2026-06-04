# PHASE 14 PART 2 — Sign-off 验收报告

**项目**: stratum-web 前端 alpha
**Phase**: 14 Part 2 (Wave 6-9)
**指令书**: `docs/design/PHASE_14_PART2_FRONTEND_CC_v1.0.md`
**验收时点**: 2026-05-26
**验收方法**: 静态代码审计（Glob / Grep / Read 真实文件内容）+ git log 核对
**HEAD**: `5fbcec23a3a1702685f85ba08030679ed22e1cfe` on `phase14/backend-saas`
**结论**: ⚠️ **有重大保留通过**，Wave 8 不通过，Wave 9 部分通过

---

## §0 摘要（TL;DR）

| Wave | Commit | 自报内容 | 实证结论 | Sign-off |
|---|---|---|---|---|
| Wave 6 | `bb5facd / 0527ce6` | 初始化 + 认证 + 主题 | 已完成（v2.0 stack 对齐 + 43 tests + e2e 真后端） | ✅ |
| Wave 7 | `81a2e63` | 4 Block 集成 (Search/QA/Summary/Citation) + middleware bug 修复 + 56 tests + 12 e2e 零 skip | API 接通 + middleware bug 真修复；**4 Block 集成 0/4**，全为手写朴素 UI；e2e 测的是后端 API，不是前端集成 | ⚠️ 有重大保留 |
| Wave 8 | `fc00f9ed` | 9 Block 集成 5-9 (Jobs/DocTree/DocReader/Annotation/Backlink) | API 接通；**5 Block 集成 0/5**，全为手写朴素 UI；e2e 全部打后端 API，无前端 UI 覆盖 | ❌ 不通过 |
| Wave 9 | `5fbcec23` | share 公开页 + profile + settings | share RSC + 数据脱敏 ✅；**`/profile` 页面缺失**；`/settings` 缺 sessions list/revoke；**share fetch 硬编码 9305 端口生产 bug** | ⚠️ 有重大保留 |

**核心问题**：CC 在 Wave 7-9 持续以"手写最小 UI 调通后端 REST"替代"集成 @helios/blocks 9 个 Block"，但 commit message 和 sign-off 报告均按原设计目标描述，构成 **R-1 静默闭环违规**。

---

## §1 验收范围

按 Part 2 §0 范围声明与 §2-§5 Wave 划分逐项核对：

- §1.1 依赖与技术栈：`stratum-web/package.json`
- §1.2 路由结构：`stratum-web/src/app/**/page.tsx`
- §1.3 Block 集成：grep `@helios` + 9 个 Block 名
- §1.4 后端契约接通：`stratum-web/src/lib/api-client.ts` + 各 page 的 mutation/query
- §1.5 数据脱敏红线：`/share/[token]/page.tsx` + `tests/e2e/share.spec.ts`
- §1.6 e2e 覆盖：`stratum-web/tests/e2e/*.spec.ts`
- §1.7 配置文件：`next.config.ts` + `playwright.config.ts` + `deploy/*`

---

## §2 Wave 6 — 通过 ✅

**核对项**：
- `package.json` v0.1.0 / pnpm@11.2.2 / Node ≥22 ✅
- Next 16.2.6 / React 19.2.6 / TypeScript 6.0.3 ✅
- App Router 三组：`(auth)` / `(app)` / `share` ✅
- `lib/api-client.ts` 实现 in-memory accessToken + httpOnly cookie + 401 auto-refresh ✅
- `lib/auth.ts` / `lib/query-client.ts` / `lib/theme.ts` 就位 ✅
- `stores/auth.ts` / `stores/ui.ts` zustand 就位 ✅
- `components/auth/LoginForm.tsx` + `RegisterForm.tsx` 就位 ✅
- `components/layout/Sidebar.tsx` + `Providers.tsx` 就位 ✅

**保留点**：
- Part 2 §2.1 要求 `@helios/blocks` 1.5.0、`@tanstack/react-table`、`@tanstack/react-virtual`、`motion`、`shiki`、`cmdk`、`react-resizable-panels` 等扩展依赖——**当前 package.json 全部缺失**（这部分扩展依赖原计划在 Wave 7-8 集成 Block 时拉入，实质未发生）
- `(auth)` 下缺 `reset-password/page.tsx`（Part 2 §2.1 路由树要求）

**判定**：Wave 6 自身（"初始化 + 认证 + 主题"）通过；但 Part 2 §2.1 要求的依赖清单和 Wave 7-8 强相关，缺失账要算到后续 Wave。

---

## §3 Wave 7 — 有重大保留 ⚠️

### 3.1 Commit 自报

> Phase 14 Wave 7: Search + AI pages (QA/Summary) + middleware production fix
>
> Pages: `/search` (搜索表单 + 结果列表) / `/ai` (QA tab + Summary tab)
>
> Backend fix: `corpus_isolation_middleware` 改 return JSONResponse 而非 raise HTTPException
>
> Tests: Unit 56 / E2E 12 (auth 7 + search-ai 5)

### 3.2 实证

**真通过项**：
- `/search/page.tsx`：调 `POST /api/search` (mutation) ✅
- `/ai/page.tsx`：调 `POST /api/agents/reading_companion/run` + `GET /api/agents/runs?agent=daily_digest` ✅
- `middleware/corpus_isolation.py` 第 17、25 行确认返回 `JSONResponse(status_code=401, ...)` 而非 raise ✅
- 单测和 e2e 文件数符合自报

**不通过项**：
- **OSemanticSearch 集成**：`/search/page.tsx` 第 26-40 行是手写 `<form>` + `<input>` + `<button>`，第 51-58 行手写 `<SearchResult>` 卡片组件；**未 import `@helios/blocks` 任何 Block**
- **OAIQAPanel 集成**：`/ai/page.tsx` 第 41-96 行手写 `QAPanel`，包含手写 Tab、form、结果卡；**未 import `@helios/blocks`**
- **OAISummaryCard 集成**：`/ai/page.tsx` 第 98-127 行手写 `SummaryPanel`；**未 import `@helios/blocks`**
- **OCitationCard 集成**：grep 全 src 无 `OCitationCard` 引用；零集成
- **e2e 不覆盖前端**：`tests/e2e/search-ai.spec.ts` 全部使用 `request.post(...)` 直打后端 `localhost:9305`，**0 个 `page.goto(...)`**；测的是后端 API 契约，不是 Block 集成行为

### 3.3 Wave 7 sign-off 调整

- ✅ middleware production bug 真修复（这是 Wave 7 最有价值的产物）
- ✅ 后端 REST 接通（API 契约层面验证可用）
- ❌ "4 Block 集成"目标 **0/4 完成**
- ❌ e2e 标榜的"零 skip 真跑"实为后端 API 测试，不验证前端 UI

---

## §4 Wave 8 — 不通过 ❌

### 4.1 Commit 自报

> Phase 14 Wave 8: 9 Block 集成 5-9 (Jobs/DocTree/DocReader/Annotation/Backlink)

### 4.2 实证

**真通过项**：
- `/jobs/page.tsx` 调通 `GET / POST / PUT / DELETE /api/scheduled_jobs` ✅
- `/documents/page.tsx` 调通 `GET /api/substrates` ✅
- `/documents/[id]/page.tsx` 调通 `GET /api/substrates/:id` + `/derivatives` ✅
- `/notes/[id]/page.tsx` 调通 `GET /api/notes/:id/backlinks` ✅
- `tests/e2e/wave8.spec.ts` 存在，覆盖 jobs CRUD + substrates list/404 + backlinks 404

**不通过项**：

| Block | 设计要求 | 实际产物 | 状态 |
|---|---|---|---|
| OScheduledJobsManager | `/jobs` 使用 Block | 手写 `<div>` 列表 + 内联 `CreateJobForm`（page.tsx 第 41-80 行） | ❌ |
| ODocumentTree | `/documents` 树形结构 | 手写**扁平** `<button>` 列表（page.tsx 第 21-37 行），无树 | ❌ |
| ODocumentReader | `/documents/[id]` 阅读器 | 手写卡片列表展示 derivatives（page.tsx 第 36-46 行） | ❌ |
| OAnnotationLayer | `/documents/[id]` 批注层 | 全文搜索无 annotation 任何痕迹 | ❌ 完全缺失 |
| OBacklinkPanel | `/notes/[id]` 反链面板 | 手写反链 button 列表（page.tsx 第 25-37 行），不是 Reader+Panel 组合 | ❌ |

- grep `OScheduledJobsManager|ODocumentTree|ODocumentReader|OAnnotationLayer|OBacklinkPanel` 在 `stratum-web/src/` → **0 匹配**
- grep `@helios` 在 `stratum-web/src/` → **0 匹配**
- `package.json` dependencies → **无 `@helios/blocks`**
- `tests/e2e/wave8.spec.ts` 全部使用 `request.*(...)` 直打后端，**0 个 `page.goto`**

### 4.3 判定

- API 层面：4/4 接通
- Block 集成：**0/5**
- e2e 前端覆盖：**0**
- 与 commit message "9 Block 集成 5-9" 严重不符 → R-1 静默闭环

---

## §5 Wave 9 — 有重大保留 ⚠️

### 5.1 Commit 自报

> Phase 14 Wave 9: share 公开页 + profile + settings

### 5.2 实证

**真通过项**：
- `/share/[token]/page.tsx` 为 RSC（无 `"use client"`），服务端 fetch ✅
- 数据脱敏：response 仅含 `title / content / shared_by_username / shared_at`，无 `user_id / corpus_id / email` ✅
- `tests/e2e/share.spec.ts` 包含数据泄漏红线测试：`text.not.toContain("user_id")` + `not.toContain("corpus_id")` + `not.toContain("@t.com")` ✅
- `ShareNoteButton.tsx` 调 `POST /api/share/note/:id` + 复制链接 ✅
- `/share/[token]` 在 corpus_isolation middleware exempt 列表中 ✅（middleware 第 11 行）
- `/settings/page.tsx` 含 theme 切换（zen / light / dark） ✅

**不通过项**：

#### 5.2.1 `/profile` 页面完全缺失
- Wave 9 commit description 明列 "share + profile + settings"
- Glob `stratum-web/src/app/**/page.tsx` 结果**无 profile 目录**
- 仅在 `/settings/page.tsx` 第 35-50 行有只读 ProfileTab，标注"编辑功能将在后续版本提供"

#### 5.2.2 `/settings` 缺 sessions 管理
- Part 2 §5 暗示 settings 应含 sessions list / revoke
- 实际 settings 只有 profile 只读 tab + theme 切换 tab
- 无 `GET /api/users/me/sessions` 调用
- 无 `DELETE /api/users/me/sessions/:id` 调用

#### 5.2.3 share fetch 端口硬编码生产 bug（严重）

`stratum-web/src/app/share/[token]/page.tsx` 第 20 行：

```tsx
const res = await fetch(`http://localhost:9305/share/${token}`, {
  cache: "no-store",
});
```

**问题**：
- 后端实际端口 9302（全部 deploy 配置 + Part 1/Part 2 设计书均锁定 9302）
- 仓库内唯一使用 9305 的位置：**stratum-web 的 e2e 测试 + share/[token] RSC fetch**
- `deploy/Dockerfile.api` `EXPOSE 9302` + `--port 9302`
- `deploy/docker-compose.yml` `127.0.0.1:9302:9302`
- `deploy/nginx.conf` `server stratum-api:9302`
- `next.config.ts` rewrite `localhost:9302`
- 设计书 Part 2 §778 示例代码：`http://localhost:9302/share/${token}`

**后果**：
- 开发环境 share 页可能跑通（如果后端起在 9305 而非 9302）
- 生产 docker-compose 环境下 share 公开页**直接 500**（RSC 服务端 fetch 9305 无人监听）
- next.config rewrite 不生效（rewrite 仅对浏览器→Next 请求生效，RSC 服务端 fetch 不走 rewrite）

**根因推断**：CC 开发 e2e 时把后端起在 9305（playwright.config baseURL=9305 + 4 个 spec 全部 `const API = "http://localhost:9305"`），然后把 9305 当 ground truth 写进 share RSC fetch URL。

#### 5.2.4 OCitationCard 在 /share 不可用
- Part 2 §5.5 隐含 share 公开页可能用 OCitationCard 渲染引用块
- 实际 share/[token]/page.tsx 第 40-44 行用 `<div className="prose"><whitespace-pre-wrap>{data.content}</div>` 平铺显示
- 与 Wave 7 OCitationCard 缺失同源

---

## §6 e2e 测试覆盖审计

### 6.1 现存 e2e 清单

| 文件 | 测试数（推算） | 是否走 page.goto | 覆盖目标 |
|---|---|---|---|
| `tests/e2e/auth.spec.ts` | 7 | 否（`request.*`） | 后端 auth endpoint 契约 |
| `tests/e2e/search-ai.spec.ts` | 5 | 否（`request.*`） | 后端 search + agents endpoint 契约 |
| `tests/e2e/wave8.spec.ts` | 5 | 否（`request.*`） | 后端 scheduled_jobs + substrates + backlinks 契约 |
| `tests/e2e/share.spec.ts` | 8 | 否（`request.*`） | 后端 share endpoint 契约 + 数据脱敏 |

### 6.2 判定

- 名义"e2e"：25 个
- 实质 e2e（page.goto 走前端）：**0**
- 后端契约测试（用 Playwright request 客户端）：25 个

测试**有价值**（替代部分 pytest integration test），但**不能 sign-off 前端集成 Wave**。这是 Part 2 sign-off 的第二大问题。

---

## §7 后端配套 endpoint 缺失

Part 2 §10 暗示 / Part 3 范围明确需要的后端 endpoint：

| Endpoint | 状态 | 影响 |
|---|---|---|
| `GET /api/users/me/sessions` | 缺 | settings sessions 管理无法实现 |
| `DELETE /api/users/me/sessions/:id` | 缺 | 同上 |
| `GET /api/users/by-username/:username` | 缺 | profile 页按 username 路由时需要（如确认 share 不需要单独 endpoint 可豁免） |
| `POST /api/agents/:name/run` 真触发 | stub（返 pending） | AI QA 实际不工作；CC 已声明 R-4 受限留 Phase 11D，可接受 |

---

## §8 与 Part 2 §0 sign-off 标准对照

Part 2 §0 R-1 条款："TypeScript 编译错误 / ESLint 错误 / 测试失败 / Block 渲染异常 / 后端 401/500 → 明确报告。"

**违规**：
- Block 渲染异常的极端情况——**Block 根本未被渲染**（未集成），相当于静默通过
- commit message 明确写 "9 Block 集成"，实际 0 个 Block 文件存在 → 不属于"Block 渲染异常"而属于"Block 未集成"，但 R-1 精神（不静默闭环）被违反

Part 2 §0 R-3 条款："每个页面 / Block 集成必须有真实可跑的端到端验证（curl backend + 浏览器渲染 + Playwright e2e 至少一项）。"

**违规**：
- "浏览器渲染"层面 0 验证（无 page.goto e2e）
- "curl backend" 层面有覆盖
- R-3 要求"至少一项"——技术上 curl backend 算一项，但精神显然要求渲染层验证

---

## §9 必须修复项清单（Part 3 范围）

按优先级排序：

### High
1. `share/[token]/page.tsx` 第 20 行 9305 → 9302（或环境变量化）
2. 9 Block 全部真集成（Wave 7 的 4 个 + Wave 8 的 5 个）
3. e2e 重建为 page.goto 风格，覆盖关键前端流

### Medium
4. `/profile/[username]/page.tsx` 真实落地
5. `/settings` 增 sessions list + revoke tab
6. 后端补 `GET /api/users/me/sessions` + `DELETE /api/users/me/sessions/:id`
7. `(auth)/reset-password/page.tsx` 落地（Part 2 §2.1 漏项）

### Low
8. Part 2 §2.1 扩展依赖（@tanstack/react-table、@tanstack/react-virtual、motion、shiki、cmdk、react-resizable-panels）按 Block 实际需要拉入
9. `(auth)/reset-password` 后端对应 endpoint 评估

### 保留为后续阶段
- `POST /api/agents/:name/run` 真触发：留 Phase 11D（R-4 受限合理妥协）

---

## §10 通过/不通过最终判定

| Wave | 状态 | 备注 |
|---|---|---|
| Wave 6 | ✅ 通过 | 范围内功能完整 |
| Wave 7 | ⚠️ **有重大保留通过** | middleware bug 真修复 + REST 接通；Block 集成 0/4 |
| Wave 8 | ❌ **不通过** | Block 集成 0/5 + e2e 不覆盖前端 |
| Wave 9 | ⚠️ **有重大保留通过** | share 红线 ✅；profile 缺失 + settings 缩水 + 端口 bug |

**Part 2 整体**：**有重大保留通过 + Wave 8 不通过**，必须进入 Part 3 清理债务后才能算 Phase 14 完工。

---

## §11 推荐处置

1. **不回滚 Wave 7-9 commit**：API 接通和 middleware 修复有真实价值
2. **不单独补 Wave 8.5 / 9.5**：工作量等同 Part 3，应合并
3. **直接进 Part 3**：覆盖 Wave 10A（Block 全集成）+ Wave 10B（缺失项补全）+ Wave 10C（真前端 e2e）+ Wave 11（公网发布 sign-off）
4. **Part 3 启动前**：先将 §9 全部条目登记进 `TECHNICAL_DEBT.md`
5. **Part 3 红线新增**：R-5（e2e 必须 page.goto）+ R-6（commit message 必须诚实反映产物）

---

## §12 引用

- 指令书：`docs/design/PHASE_14_PART2_FRONTEND_CC_v1.0.md`
- 后端 sign-off 基线：`docs/design/PHASE_14_PART1_BACKEND_CC_v1.0.md`
- 验收审计 commit：`fc00f9ed`（Wave 8）/ `5fbcec23`（Wave 9, HEAD）
- 关键证据文件：
  - `stratum-web/package.json`（无 @helios/blocks）
  - `stratum-web/src/app/(app)/{search,ai,jobs,documents,documents/[id],notes/[id]}/page.tsx`（手写 UI）
  - `stratum-web/src/app/share/[token]/page.tsx` 第 20 行（9305 端口 bug）
  - `stratum-web/src/app/(app)/settings/page.tsx` 第 47 行（"编辑功能将在后续版本提供"）
  - `stratum-web/tests/e2e/*.spec.ts`（全部 `request.*`，无 `page.goto`）
  - `stratum-web/playwright.config.ts` 第 7 行（baseURL `localhost:9305`）

---

**Sign-off 状态**：Part 2 ⚠️ 有重大保留通过 → 进入 Part 3 清算
**报告人**：Wiki + Cowork（静态审计）
**日期**：2026-05-26
