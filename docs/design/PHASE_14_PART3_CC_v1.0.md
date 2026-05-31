# PHASE 14 PART 3 — 债清算 + 公网发布 CC 执行指令书 (Wave 10-11)

**CC FULL AUTO 实施指令书**

**项目**: stratum 准产品 alpha — 债清算 + 公网发布
**Phase**: 14 Part 3 (3 段中第 3 段)
**前置**:
- Part 1 (Wave 1-5) ✅ sign-off (commit `fb80701`, 189 tests, 后端 SaaS 基础设施完工)
- Part 2 (Wave 6-9) ⚠️ 有重大保留通过 (commit `5fbcec23`, 189+25 tests, 但 9 Block 集成 0/9 + e2e 0 page.goto)
- **必读** `docs/yiwancheng/PHASE_14_PART2_SIGNOFF_REPORT.md`（验收报告）
- **必读** `docs/yiwancheng/TECHNICAL_DEBT.md` § Phase 14 Part 2 — Front-end Sign-off Audit
**执行**: CC FULL AUTO, Wave 10A → 10B → 10C → 11
**预算**: 10-14 天 / 2 周
**目标**: 把 Part 2 留下的债全部清算，完成 9 Block 真集成 + 真前端 e2e + 公网发布 sign-off，达成 Phase 14 整体收官

---

## §0 范围声明 (R-4 严格)

### ✅ 允许

- **修改 `~/projects/stratum/stratum-web/` 任意文件**（前端债清算）
- **修改 `~/projects/stratum/src/stratum/` 受限范围**：
  - 新增 `http_api/routes/users.py`（或扩展 `auth.py`）实现 sessions list / revoke
  - 新增 sessions 相关 DAO 方法（若 `dao/sessions.py` 缺）
  - **不修改** 现有 auth / search / share / agents / scheduled_jobs / substrates / notes 路由的契约（仅可加新 endpoint，不可改老 endpoint 的 request/response schema）
- 升级 `@helios/blocks` 到 1.6.0（最新）
- 新增 deploy / README / CLAUDE.md / AGENTS.md / Makefile / .env.example / CHANGELOG.md
- 跑 Cloudflare Tunnel 真启动测试

### ❌ 禁止

- **不修改 `~/projects/platform/{omodul,oskill,oprim}/`** 任何文件（沿用 Part 1/Part 2 R-4）
- **不修改 `@helios/blocks` 内部代码**（作为依赖消费，不 fork）
- **不修改 Part 1/Part 2 已 sign-off 的 REST endpoint 契约**（仅新增不破坏）
- **不删除 Wave 6-9 commit**（保留历史，债以新增 commit 形式清理）
- **不绕过 corpus 隔离**（任何接受用户输入 corpus_id 的逻辑 = block）
- **不接通 `POST /api/agents/:name/run` 到 omodul.Agent**（沿用 R-4，保留为 Phase 11D 工作）

如发现必须越界才能完成某 Wave → 立即停报告 advisor，不擅自改。

---

## §1 FULL AUTO 规则 (R-1 ~ R-6)

### R-1 失败不静默
TypeScript 编译错误 / ESLint 错误 / Vitest 失败 / Playwright 失败 / Block 渲染异常 / 后端 401/500 → 明确报告。**Part 2 失败模式不允许复发：禁止"用手写 UI 顶替 Block 集成然后报告完成"。**

### R-2 SPEC 是真理源
本指令书 + Part 1/Part 2 指令书 + Part 2 sign-off 报告 + `@helios/blocks` 1.6.0 官方文档是真理。不脑补 Block 的 API。Block prop 签名不匹配后端时，写薄适配层（adapter），**不 fork Block 内部**。

### R-3 真实示例强制
每个 Block 集成必须有：
1. 真后端 + 真前端的 page.goto e2e 覆盖（≥1 条 happy path）
2. 真渲染验证（pnpm dev 起 + 浏览器打开 + 关键元素 locator 命中）
3. type-check + lint 零错

仅有 vitest unit test 或仅有后端 request 契约测试 = **不算 Block 集成完成**。

### R-4 严格范围
见 §0。**禁止跨越 platform 边界**（omodul / oskill / oprim 不动），后端仅可新增 sessions 相关 endpoint，前端 9305 端口 bug 必须修但不可改老契约。

### R-5（新）e2e 必须 page.goto
所有 `tests/e2e/*.spec.ts` 必须主要使用 `await page.goto(...)` + `page.locator(...)` 风格走真前端。**直打后端 API 的 `request.*(...)` 风格测试只能放 `tests/contract/`**（新增目录，作为契约测试）。e2e 与 contract 测试都保留，但分目录、分用途。

具体定义：
- e2e = "用户从浏览器视角看到的行为"，必须经过 Next dev/build 渲染
- contract = "后端 endpoint 的 request/response 契约"，可以用 Playwright `request` API 或 pytest httpx 写
- Wave 10C sign-off 要求：e2e 真 page.goto ≥ 15 条，0 skip；contract 测试沿用现有 25 条迁至新目录

### R-6（新）commit message 必须诚实反映产物
Commit 描述必须只写**实际落地的产物**。禁止：
- 写"集成 X Block"但实际是手写 UI 替代
- 写"实现 X 页面"但页面不存在
- 写"X tests"但其中 Y 个是 skip 或 stub
- 写"修复 X bug"但实际只是绕过

如某 Block 因技术原因暂时无法集成需手写 UI 顶替，commit message 必须明列：`Wave X: ... (注意: OFoo 未集成, 手写 UI 临时替代, 见 TECHNICAL_DEBT.md)`。

### R-7 破坏性操作

需要 Wiki sign-off：
- `git rm` / `rm -rf` 任何已 commit 文件
- 删除现有 e2e spec 文件（应迁移而非删除）
- 降级 `@helios/blocks` 版本
- 修改 Part 1/Part 2 REST endpoint 契约
- 公网发布 sign-off（Wave 11 完成后单独 sign-off）

本指令书 sign-off：
- ✅ 升级 `@helios/blocks` 到 1.6.0
- ✅ 新增 stratum 后端 sessions 相关 endpoint
- ✅ 重写 9 个 page.tsx
- ✅ 迁移现有 e2e 到 `tests/contract/`
- ✅ 新增 `tests/e2e/` 下 page.goto 风格测试
- ✅ 新增根目录 README / CLAUDE.md / AGENTS.md / Makefile / .env.example / CHANGELOG.md

---

## §2 技术栈调整

### 2.1 端口约定（强制锁定 9302）

| 用途 | 端口 |
|---|---|
| 后端 uvicorn dev | **9302** |
| 后端 docker-compose | **9302** |
| 前端 Next dev | 3000 |
| 前端 → 后端 rewrite | `/api/*` + `/share/:token` → `localhost:9302` |
| Playwright baseURL | `http://localhost:3000`（**改自原 9305**）|
| RSC 服务端 fetch share endpoint | `process.env.STRATUM_API_URL ?? "http://localhost:9302"` |

**仓库内禁止再出现 9305 字面值**（除迁移日志说明）。Wave 10B 包含一次性 grep -r 验证。

### 2.2 @helios/blocks 升级

```diff
// stratum-web/package.json
  "dependencies": {
+   "@helios/blocks": "^1.6.0",
    "@hookform/resolvers": "^5.0.1",
    "@tanstack/react-query": "^5.100.11",
+   "@tanstack/react-table": "^8.21.3",
+   "@tanstack/react-virtual": "^3.13.25",
+   "motion": "^12.40.0",
    ...
  }
```

实际拉入的扩展依赖以 Block 真 import 需要为准（如 Block 内部不需要 react-virtual，则不强制加）。

### 2.3 主题与样式

```css
/* stratum-web/src/styles/globals.css */
@import "tailwindcss";
@import "@helios/blocks/styles.css";
@import "@helios/blocks/themes/zen.css";

/* zen 主题 CSS 变量已由 @helios/blocks 提供，不再手写 --color-* */
```

**Wave 10A 必须移除**：当前 `globals.css`（如存在）中自定义的 `--color-primary / --color-background / --color-foreground / --color-border / --color-muted` 等变量；改用 `@helios/blocks/themes/zen.css` 提供的同名变量。手写页面里的 `bg-[var(--color-primary)]` 写法保留（变量来源切换）。

### 2.4 e2e 拓扑

```
tests/
├── e2e/                              # Wave 10C 重建：page.goto 风格
│   ├── auth.spec.ts                  # 登录 / 注册 / 登出
│   ├── search.spec.ts                # /search 真表单 + 真结果
│   ├── ai.spec.ts                    # /ai QA + Summary
│   ├── jobs.spec.ts                  # /jobs CRUD
│   ├── documents.spec.ts             # /documents 树 + /documents/[id] reader
│   ├── notes.spec.ts                 # /notes/[id] reader + backlinks
│   ├── share.spec.ts                 # 创建分享 + 公开页打开
│   ├── settings.spec.ts              # theme 切换 + sessions revoke
│   └── profile.spec.ts               # /profile/[username] 浏览
├── contract/                         # Wave 10C 新增：迁移自原 e2e
│   ├── auth.contract.ts              # 原 auth.spec.ts
│   ├── search-ai.contract.ts         # 原 search-ai.spec.ts
│   ├── wave8.contract.ts             # 原 wave8.spec.ts
│   └── share.contract.ts             # 原 share.spec.ts
└── unit/                             # vitest，沿用
```

Playwright config 改为同时支持 e2e 和 contract 两个 project（不同 baseURL 与 setup）。

---

## §3 Wave 10A — @helios/blocks 1.6 全量集成（5-7 天）

**目标**：把 Wave 6-9 的 9 个手写 page.tsx 全部重写为 Block 真集成，0 个 `@helios/blocks` import 漏项，0 个手写朴素 UI 残留。

### 3.1 启动条件

- Part 2 sign-off 报告已读
- `pnpm install` 跑通，`pnpm list @helios/blocks` 显示 1.6.0
- 阅读 `@helios/blocks` 1.6.0 README（package 内 README 或 storybook）确认每个 Block 的 prop 签名

### 3.2 适配层（adapter）模式

Block 的 prop 签名与后端 API response 不一致时，**绝不修改 Block**，而是写薄 adapter hook：

```ts
// stratum-web/src/lib/adapters/search.ts
import { useMutation } from "@tanstack/react-query";
import type { SearchResponse, SearchResultItem } from "@/lib/types";
import type { SemanticSearchResult } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";

/** 把后端 SearchResultItem 映射为 OSemanticSearch 期望的 SemanticSearchResult */
function adaptResult(item: SearchResultItem): SemanticSearchResult {
  return {
    id: item.id,
    title: item.title,
    snippet: item.highlight ?? "",
    score: item.score,
    kind: item.type,
    href: `/documents/${item.id}`,
  };
}

export function useSemanticSearch() {
  return useMutation({
    mutationFn: async (query: string) => {
      const res = await apiClient.post<SearchResponse>("/api/search", {
        query, top_k: 10, mode: "augmented",
      });
      return res.results.map(adaptResult);
    },
  });
}
```

**所有 9 Block 都必须有对应 adapter**（即使 1:1 映射也写空 adapter，便于后续切换后端字段）。adapter 位于 `stratum-web/src/lib/adapters/`。

### 3.3 9 Block 集成清单

每个页面给出：路由、使用 Block、关键 prop、API、e2e 验收。

#### 3.3.1 `/search` — OSemanticSearch

```tsx
// stratum-web/src/app/(app)/search/page.tsx
"use client";

import { OSemanticSearch } from "@helios/blocks";
import { useSemanticSearch } from "@/lib/adapters/search";

export default function SearchPage() {
  const search = useSemanticSearch();
  return (
    <OSemanticSearch
      onQuery={(q) => search.mutate(q)}
      results={search.data ?? []}
      loading={search.isPending}
      error={search.error?.message}
      placeholder="输入搜索内容..."
    />
  );
}
```

**API**: `POST /api/search`（已存在）
**e2e（Wave 10C）**: page.goto `/search` → fill `OSemanticSearch` input → submit → 验证结果列表渲染

#### 3.3.2 `/ai` — OAIQAPanel + OAISummaryCard

两个 Block 并存的页面（Tab 仍可保留，但 Tab 自身可用 Block 内置 Tabs 或简易布局）：

```tsx
// stratum-web/src/app/(app)/ai/page.tsx
"use client";

import { useState } from "react";
import { OAIQAPanel, OAISummaryCard } from "@helios/blocks";
import { useAgentQA, useAgentRuns } from "@/lib/adapters/agents";

type Tab = "qa" | "summary";

export default function AIPage() {
  const [tab, setTab] = useState<Tab>("qa");
  const qa = useAgentQA();
  const runs = useAgentRuns("daily_digest");

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">AI 助手</h1>
      {/* tab 切换沿用现有手写或换为 Block 提供的 Tabs */}
      {tab === "qa" && (
        <OAIQAPanel
          onAsk={(q) => qa.mutate(q)}
          answer={qa.data?.agent_run.output}
          status={qa.data?.agent_run.status}
          loading={qa.isPending}
          error={qa.error?.message}
          // 红线：当前 status === "pending" 时显示提示文案，告知用户 agent 真触发待 Phase 11D
          pendingHint="此功能正在准备中，agent 实际触发将在后续版本提供"
        />
      )}
      {tab === "summary" && (
        <div className="space-y-3">
          {(runs.data?.items ?? []).map((run) => (
            <OAISummaryCard
              key={run.id}
              date={run.started_at}
              status={run.status}
              content={run.output}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

**API**: `POST /api/agents/reading_companion/run` + `GET /api/agents/runs?agent=daily_digest`（已存在，仍为 stub，前端 UI 必须处理 pending 状态）
**e2e**: page.goto `/ai` → 选 QA tab → fill 问题 → submit → 验证 OAIQAPanel 显示 pending 提示；切换到 Summary tab → 验证 OAISummaryCard 列表渲染（即使为空也应有 empty 状态）

#### 3.3.3 `/jobs` — OScheduledJobsManager

```tsx
// stratum-web/src/app/(app)/jobs/page.tsx
"use client";

import { OScheduledJobsManager } from "@helios/blocks";
import { useScheduledJobs } from "@/lib/adapters/jobs";

export default function JobsPage() {
  const { jobs, isLoading, create, update, remove } = useScheduledJobs();
  return (
    <OScheduledJobsManager
      jobs={jobs}
      loading={isLoading}
      onCreate={create}
      onToggle={(job) => update({ id: job.id, enabled: !job.enabled })}
      onDelete={(job) => remove(job.id)}
      builtinAgents={["daily_digest", "weekly_review", "reading_companion"]}
    />
  );
}
```

**API**: `GET / POST / PUT / DELETE /api/scheduled_jobs[/...]`（已存在）
**e2e**: page.goto `/jobs` → 点新建 → 填表 → submit → 验证列表新增；toggle enabled → 验证状态切换；delete → 验证消失

#### 3.3.4 `/documents` — ODocumentTree

```tsx
// stratum-web/src/app/(app)/documents/page.tsx
"use client";

import { ODocumentTree } from "@helios/blocks";
import { useRouter } from "next/navigation";
import { useDocumentTree } from "@/lib/adapters/documents";

export default function DocumentsPage() {
  const router = useRouter();
  const { tree, isLoading } = useDocumentTree();
  return (
    <ODocumentTree
      nodes={tree}
      loading={isLoading}
      onNodeClick={(node) => router.push(`/documents/${node.id}`)}
    />
  );
}
```

**API**: `GET /api/substrates`（已存在；adapter 把扁平列表组织为 tree——按 mime / language / 时间 分组，具体规则待 Block 文档定）
**e2e**: page.goto `/documents` → 验证 ODocumentTree 渲染 → 点击节点 → 验证 router push 到 `/documents/[id]`

#### 3.3.5 `/documents/[id]` — ODocumentReader + OAnnotationLayer + OCitationCard

```tsx
// stratum-web/src/app/(app)/documents/[id]/page.tsx
"use client";

import { useParams } from "next/navigation";
import {
  ODocumentReader,
  OAnnotationLayer,
  OCitationCard,
} from "@helios/blocks";
import { useDocument, useDerivatives } from "@/lib/adapters/documents";

export default function DocumentReaderPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { substrate } = useDocument(id);
  const { derivatives } = useDerivatives(id);

  if (!substrate) return null;

  return (
    <ODocumentReader
      title={substrate.title}
      meta={{ mime: substrate.mime, language: substrate.language, pages: substrate.page_count }}
      sections={derivatives.map((d) => ({
        id: d.id,
        kind: d.kind,
        seq: d.seq,
        content: d.content,
      }))}
      renderSection={(section) => (
        <OAnnotationLayer
          targetId={section.id}
          targetKind="derivative"
        >
          <OCitationCard kind={section.kind} seq={section.seq} content={section.content} />
        </OAnnotationLayer>
      )}
    />
  );
}
```

**API**: `GET /api/substrates/:id` + `/derivatives`（已存在）
**e2e**: page.goto `/documents/<existing-id>` → 验证 ODocumentReader 显示标题与 meta；至少一个 OCitationCard 渲染；OAnnotationLayer 存在（标注创建为 best-effort，不强制走通，后端可能无 endpoint）

**Adapter 注意**：annotation 创建/列表的后端 endpoint 当前未确认（Part 1 sign-off 范围内未明列）。Wave 10A 实现策略：
1. 优先检查后端是否有 `/api/annotations` 路由
2. 若无，OAnnotationLayer 以纯展示模式工作（不支持创建），并登记 TECHNICAL_DEBT
3. 不擅自实现后端 endpoint（除非属于 §0 允许范围）

#### 3.3.6 `/notes/[id]` — ODocumentReader + OBacklinkPanel + OCitationCard

```tsx
// stratum-web/src/app/(app)/notes/[id]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { ODocumentReader, OBacklinkPanel } from "@helios/blocks";
import { useNote, useBacklinks } from "@/lib/adapters/notes";
import { ShareNoteButton } from "@/components/shared/ShareNoteButton";

export default function NotePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const { note } = useNote(id);
  const { backlinks } = useBacklinks(id);

  if (!note) return null;

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      <ODocumentReader
        title={note.title}
        sections={[{ id: note.id, kind: "note", content: note.content }]}
        toolbar={<ShareNoteButton noteId={note.id} />}
      />
      <OBacklinkPanel
        items={backlinks}
        onItemClick={(b) => router.push(`/notes/${b.id}`)}
      />
    </div>
  );
}
```

**API**: 当前 `GET /api/notes/:id/backlinks` 已存在；`GET /api/notes/:id`（单条笔记）**需复核是否存在**：
- 若存在 → 直接用
- 若不存在 → Wave 10B 范围内新增 endpoint（属于 §0 允许范围，因不破坏老契约只新增）

**e2e**: page.goto `/notes/<existing-id>` → 验证 reader 标题 + 内容；如有 backlink 数据，OBacklinkPanel 列表渲染 → 点击 → router push

### 3.4 Wave 10A Sign-off 标准

| 项 | 通过条件 |
|---|---|
| 依赖 | `package.json` 含 `@helios/blocks ^1.6.0`，`pnpm install` 干净跑通 |
| Block 集成 | grep `@helios/blocks` in `stratum-web/src/app` → ≥ 9 个文件匹配；9 个 Block 名各至少 1 个 import |
| 手写 UI 残留 | grep `<form|<input|<button` in 9 个 page.tsx → 仅出现在 adapter 不可达的极少数布局位置（< 10 处总计），且必须有理由说明 |
| Adapter 完整 | `stratum-web/src/lib/adapters/` 下至少 5 个文件（search / agents / jobs / documents / notes），每个对应至少一个 Block |
| Type-check | `pnpm type-check` 0 错 |
| Lint | `pnpm lint` 0 错（`--max-warnings 0`） |
| Unit test | 至少保留 56 个原 vitest（如 Wave 7-8 留下）；新增 adapter 单测覆盖 ≥ 70%（按行） |
| 渲染验证 | 每个 page 至少有一张 storybook 截图或开发环境截图入档（放 `docs/yiwancheng/PHASE_14_PART3_WAVE10A_SCREENSHOTS/`） |
| commit message | 严格按 R-6，每个 Block 显式列名："Wave 10A: integrate OSemanticSearch + OAIQAPanel + ..." |

未通过任一项 → Wave 10A 不 sign-off，停下报告。

---

## §4 Wave 10B — 后端 + 前端缺失项补完（2-3 天）

### 4.1 后端新增 endpoint

#### 4.1.1 `GET /api/users/me/sessions`

```python
# src/stratum/http_api/routes/users.py（新增文件）
from fastapi import APIRouter, Depends, Request
from stratum.auth.dependencies import require_auth
from stratum.dao.sessions import SessionDAO

router = APIRouter(prefix="/api/users/me", tags=["users"])


@router.get("/sessions")
async def list_sessions(request: Request, user=Depends(require_auth)):
    dao = SessionDAO()
    items = dao.list_active_for_user(user_id=user.id)
    # 红线：脱敏，仅返回非敏感字段
    return {
        "items": [
            {
                "id": s.id,
                "created_at": s.created_at,
                "expires_at": s.expires_at,
                "user_agent": s.user_agent,
                "ip_hash": s.ip_hash,  # 已 hash，不返回原 IP
                "is_current": s.id == request.state.session_id,
            }
            for s in items
        ]
    }
```

#### 4.1.2 `DELETE /api/users/me/sessions/:id`

```python
@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request, user=Depends(require_auth)):
    dao = SessionDAO()
    session = dao.get(session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404)
    if session.id == request.state.session_id:
        raise HTTPException(status_code=400, detail="Cannot revoke current session, use logout")
    dao.revoke(session_id)
    return {"ok": True}
```

#### 4.1.3 挂载到 app

```diff
# src/stratum/http_api/app.py
- from stratum.http_api.routes import auth, search, substrates, notes, agents, scheduled_jobs
+ from stratum.http_api.routes import auth, users, search, substrates, notes, agents, scheduled_jobs
  ...
  app.include_router(auth.router)
+ app.include_router(users.router)
```

#### 4.1.4 `GET /api/users/by-username/:username`（条件性）

**实现前置判断**：Wave 10B 启动时检查 `share endpoint` 返回是否已含 `shared_by_username`。若已含且 profile 页只需要 username 字段，则**不实现此 endpoint**；若 profile 页需要更多公开资料（avatar / bio / 公开 notes 数等），则按需实现。

若实现，schema 红线（参考 Part 2 §5.5 数据脱敏）：
- ✅ 返回 username、display_name、created_at（公开）
- ❌ 不返回 email、corpus_id、user_id（内部）、sessions、IP

#### 4.1.5 `GET /api/notes/:id`（如缺）

Wave 10B 启动时 grep 后端 `src/stratum/http_api/routes/notes.py` 确认是否已有单条笔记查询 endpoint。若无 → 新增；若有 → skip。

新增 schema：
```python
@router.get("/{note_id}")
async def get_note(note_id: str, user=Depends(require_auth)):
    dao = NoteDAO()
    note = dao.get(note_id, user_id=user.id, corpus_id=user.corpus_id)
    if not note:
        raise HTTPException(status_code=404)
    return note.dict()  # 包含 id, title, content, kind, created_at, updated_at
```

### 4.2 前端 `/profile/[username]/page.tsx` 新增

```tsx
// stratum-web/src/app/(app)/profile/[username]/page.tsx
"use client";

import { useParams } from "next/navigation";
import { OUserProfileCard } from "@helios/blocks";  // 如 Block 存在；否则用最小手写并登记债
import { useUserProfile } from "@/lib/adapters/users";

export default function ProfilePage() {
  const params = useParams<{ username: string }>();
  const { profile, isLoading } = useUserProfile(params.username);
  return (
    <OUserProfileCard
      profile={profile}
      loading={isLoading}
    />
  );
}
```

**条件分支**：若 `@helios/blocks` 1.6.0 无 `OUserProfileCard`，则手写最小 UI（用户名 + 注册时间），并在 commit message 显式标注"OUserProfileCard 不在 1.6.0 中，手写 UI 替代，TECHNICAL_DEBT 已登记"。

### 4.3 前端 `/settings` 增 sessions tab

```tsx
// stratum-web/src/app/(app)/settings/page.tsx 添加第三个 tab
import { OSessionsList } from "@helios/blocks";  // 如存在
import { useSessions } from "@/lib/adapters/users";

function SessionsTab() {
  const { sessions, revoke } = useSessions();
  return (
    <OSessionsList
      sessions={sessions}
      onRevoke={(s) => revoke(s.id)}
    />
  );
}

// 原 Tab 类型扩展为 "profile" | "theme" | "sessions"
```

同上，若 1.6.0 无 OSessionsList → 手写最小 UI + 登记 TECHNICAL_DEBT。

### 4.4 修复 share/[token] 9305 端口 bug

```diff
// stratum-web/src/app/share/[token]/page.tsx
+ const API_BASE = process.env.STRATUM_API_URL ?? "http://localhost:9302";
+
  export default async function SharePage({ params }) {
    const { token } = await params;
-   const res = await fetch(`http://localhost:9305/share/${token}`, {
+   const res = await fetch(`${API_BASE}/share/${token}`, {
      cache: "no-store",
    });
    ...
  }
```

`STRATUM_API_URL` 由 `.env.local`（开发）/ docker-compose 环境变量（生产）注入。`.env.example` 提供默认值。

### 4.5 仓库内禁止 9305 字面值（一次性验证）

Wave 10B 结束前必须跑：

```bash
grep -rn "9305" stratum-web/ src/ deploy/ docs/ --include="*.ts" --include="*.tsx" --include="*.py" --include="*.yml" --include="*.conf" --include="*.md"
```

预期结果：
- ✅ `docs/yiwancheng/PHASE_14_PART2_SIGNOFF_REPORT.md` 中作为 bug 记录的引用（保留）
- ✅ `docs/yiwancheng/TECHNICAL_DEBT.md` 中作为债登记的引用（保留）
- ❌ 任何 .ts / .tsx / .py / .yml / .conf 中的字面值（清零）

非零项 → Wave 10B 不 sign-off。

### 4.6 Wave 10B Sign-off 标准

| 项 | 通过条件 |
|---|---|
| sessions endpoint | `GET /api/users/me/sessions` + `DELETE /api/users/me/sessions/:id` 实现，pytest 覆盖 |
| by-username | 已决定（实现 or 不实现，理由记入 TECHNICAL_DEBT 更新） |
| notes/:id | 经 grep 确认；若新增则有 pytest 覆盖 |
| /profile/[username] | 路由存在，渲染至少展示 username |
| /settings sessions tab | 路由存在，sessions list + revoke 可用 |
| 9305 清零 | grep 验证通过 |
| Type-check / lint | 0 错 |
| commit message | 严格 R-6 |

---

## §5 Wave 10C — 真前端 e2e 重建（3-4 天）

### 5.1 现有 e2e 迁移到 contract/

```bash
mkdir -p stratum-web/tests/contract
git mv stratum-web/tests/e2e/auth.spec.ts stratum-web/tests/contract/auth.contract.ts
git mv stratum-web/tests/e2e/search-ai.spec.ts stratum-web/tests/contract/search-ai.contract.ts
git mv stratum-web/tests/e2e/wave8.spec.ts stratum-web/tests/contract/wave8.contract.ts
git mv stratum-web/tests/e2e/share.spec.ts stratum-web/tests/contract/share.contract.ts
```

迁移后修改 `playwright.config.ts` 为多 project：

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  projects: [
    {
      name: "e2e",
      testDir: "./tests/e2e",
      timeout: 30000,
      use: { baseURL: "http://localhost:3000" },
    },
    {
      name: "contract",
      testDir: "./tests/contract",
      timeout: 30000,
      use: {
        baseURL: "http://localhost:9302",
        extraHTTPHeaders: { "Content-Type": "application/json" },
      },
    },
  ],
});
```

contract spec 中所有 `const API = "http://localhost:9305"` → 改为 `const API = "http://localhost:9302"`。

### 5.2 e2e 拓扑准备

每次 e2e 运行需要：
1. 后端 uvicorn 起在 9302（用真测试 DB，不污染主 DB）
2. 前端 next dev 起在 3000（dev 模式即可，不要求 prod build）
3. 测试用户预 seed

提供启动脚本：

```bash
# scripts/e2e-up.sh
#!/usr/bin/env bash
set -euo pipefail
export STRATUM_TEST_DB="${TMPDIR:-/tmp}/stratum-e2e-$$.duckdb"
cd "$(git rev-parse --show-toplevel)"

# 起后端
uvicorn stratum.http_api.app:app --port 9302 &
BACKEND_PID=$!

# 起前端
cd stratum-web
STRATUM_API_URL=http://localhost:9302 pnpm dev &
FRONTEND_PID=$!

# 等待就绪
until curl -sf http://localhost:9302/health; do sleep 0.5; done
until curl -sf http://localhost:3000; do sleep 0.5; done

# 跑测试
pnpm test:e2e --project=e2e

# 清理
kill $BACKEND_PID $FRONTEND_PID
rm -f "$STRATUM_TEST_DB"
```

### 5.3 新增 e2e 清单（≥15 条）

#### auth.spec.ts（4 条）

1. 注册新用户 → 跳转到 `/search`
2. 已注册用户登录 → 跳转到 `/search`
3. 错误密码 → 显示错误消息
4. 登出 → 回到 `/login`

#### search.spec.ts（2 条）

5. 登录后访问 `/search` → 输入查询 → 验证 OSemanticSearch 渲染结果列表
6. 点击结果 → 跳转 `/documents/:id`

#### ai.spec.ts（2 条）

7. 访问 `/ai` QA tab → 输入问题 → 验证 OAIQAPanel 显示 pending 提示（合规 stub 行为）
8. 切换到 Summary tab → 验证 OAISummaryCard 列表渲染或 empty state

#### jobs.spec.ts（2 条）

9. `/jobs` 创建 daily_digest job → 验证列表新增 → toggle enabled → delete → 验证消失
10. `/jobs` 空状态显示

#### documents.spec.ts（2 条）

11. `/documents` ODocumentTree 渲染 → 点击节点 → 跳 `/documents/:id`
12. `/documents/:id` ODocumentReader + OCitationCard 至少一个渲染

#### notes.spec.ts（1 条）

13. `/notes/:id` ODocumentReader + OBacklinkPanel 渲染；点击 backlink → 跳转

#### share.spec.ts（2 条）

14. 笔记页 ShareNoteButton 点击 → 生成链接 → 公开 token 访问 `/share/:token` → 验证内容渲染 + 不暴露 user_id/email（DOM 文本 not.toContain）
15. 过期 / 无效 token → 显示 ShareExpired / ShareNotFound

#### settings.spec.ts（2 条）

16. theme 切换 → 验证根元素 class 变化
17. sessions tab → 列出当前 session → 撤销非当前 session（需 seed 额外 session）

#### profile.spec.ts（1 条，条件性）

18. `/profile/:username` 渲染基本信息

### 5.4 Wave 10C Sign-off 标准

| 项 | 通过条件 |
|---|---|
| 现有 e2e 迁移 | 4 个 spec 全部迁移至 `tests/contract/`，无丢失 |
| 9305 → 9302 | contract spec 中 9305 字面值全部替换 |
| 新增 e2e | ≥ 15 条 `page.goto` 风格测试，0 skip |
| Playwright 双 project | `pnpm test:e2e --project=e2e` 与 `--project=contract` 分别可跑 |
| 启动脚本 | `scripts/e2e-up.sh` 可执行，CI 可调用 |
| 真后端 + 真前端 | e2e 必须经过 next dev 渲染，不允许 nock / msw mock 后端 |
| 测试 DB 隔离 | e2e 使用独立 DuckDB 实例，不污染开发库 |
| 通过率 | e2e 100% 通过（允许 retry 1 次） |
| commit message | 严格 R-6 |

---

## §6 Wave 11 — 公网发布 sign-off（2-3 天）

### 6.1 根目录文档

#### 6.1.1 `README.md`（项目主入口）

```markdown
# Stratum

Wiki's local-first AI knowledge base — 中文用户的 AI 知识管家。

## Quick start

\`\`\`bash
# Backend
make install-backend
make migrate
make backend-dev      # uvicorn on :9302

# Frontend
make install-web
make web-dev          # next dev on :3000

# E2E
make e2e-up
\`\`\`

## Architecture

[简短架构图与说明]

## Documentation

- 设计：`docs/design/STRATUM_SPEC_v0.6_PATCH.md`
- 路线图：`docs/design/STRATUM_ROADMAP_v1.0.md`
- 决策日志：`docs/yiwancheng/DECISION_LOG.md`
- 技术债：`docs/yiwancheng/TECHNICAL_DEBT.md`

## License
[未决，待 Wiki 定]
```

#### 6.1.2 `CLAUDE.md`（CC FULL AUTO 工作约束）

包含：
- R-1 ~ R-6 红线总览
- 文件路径白名单 / 黑名单
- commit message 规范（reference Part 3 R-6）
- 跑 e2e 的标准流程
- 如何登记 TECHNICAL_DEBT

#### 6.1.3 `AGENTS.md`（其他 Agent 协作）

简短：本仓库支持哪些 Agent SDK 接入、Agent 触发约定。

#### 6.1.4 `Makefile`

```makefile
.PHONY: install-backend install-web migrate backend-dev web-dev e2e-up test lint type-check

install-backend:
	pip install -e ".[dev,servers,indexing]"

install-web:
	cd stratum-web && pnpm install

migrate:
	python -m stratum.db.run_migrations

backend-dev:
	uvicorn stratum.http_api.app:app --reload --port 9302

web-dev:
	cd stratum-web && pnpm dev

e2e-up:
	bash scripts/e2e-up.sh

test:
	pytest -v
	cd stratum-web && pnpm test

lint:
	ruff check src tests
	cd stratum-web && pnpm lint

type-check:
	mypy src
	cd stratum-web && pnpm type-check
```

#### 6.1.5 `.env.example`

```bash
# Backend
STRATUM_ENV=development
DATABASE_PATH=~/.stratum/meta.duckdb
JWT_SECRET=changeme_in_production
ARGON2_PARALLELISM=1

# Frontend (.env.local in stratum-web/)
STRATUM_API_URL=http://localhost:9302
```

#### 6.1.6 `CHANGELOG.md`

```markdown
# Changelog

## v1.3.0 — 2026-05-30（Phase 14 Part 3 完工）

### Added
- @helios/blocks 1.6.0 全量集成（9 Block）
- /profile/[username] 页面
- /settings sessions list + revoke
- 真前端 e2e 测试套件（≥15 条 page.goto）
- contract 测试目录（迁移自原 e2e）
- 后端 sessions endpoint
- 根目录文档（README / CLAUDE / AGENTS / Makefile / .env.example / CHANGELOG）
- Cloudflare Tunnel 公网发布配置 sign-off

### Fixed
- share/[token] 端口硬编码 9305 → 环境变量化（默认 9302）

### Technical Debt
- 见 `docs/yiwancheng/TECHNICAL_DEBT.md`

## v1.2.0 — 2026-04-21（Phase 14 Part 2 完工，有重大保留）

### Added
- stratum-web 前端项目（Next 16 / React 19 / Tailwind 4）
- 9 个 page.tsx + 4 个 e2e contract spec

### Known Issues（在 v1.3.0 修复）
- @helios/blocks 9 Block 集成 0/9（v1.2.0 中为手写 UI 替代）
- /profile 页面缺失
- share/[token] 端口硬编码 bug

## v1.1.0 — 2026-04-14（Phase 14 Part 1 完工）

### Added
- 用户系统（auth + JWT + refresh）
- 多 corpus 隔离
- 公网部署基础设施
- share + profile token
- REST API 补全
- 189 tests / 18 渗透测试 / 5 红线安全测试

## v1.0.0 — 2026-02-XX（Phase 11C）

### Added
- Stratum service layer 初始实现
- 后端核心模型 + DAO
```

### 6.2 OpenAPI 完整化

```python
# src/stratum/http_api/app.py
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="Stratum API",
        version="1.3.0",
        description="Wiki's local-first AI knowledge base. See docs/design/ for spec.",
        routes=app.routes,
    )
    schema["info"]["contact"] = {"name": "Wiki", "url": "https://github.com/wiki/stratum"}
    schema["info"]["license"] = {"name": "TBD"}
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi
```

所有路由必须有 `summary` + `description`，每个 schema model 必须有 `Field(description=...)`。Wave 11 至少做一次完整 audit。

### 6.3 Cloudflare Tunnel 真启动测试

```bash
# 1. 拿 tunnel token（manual step by Wiki）
mkdir -p ~/.config/keys/cloudflared
echo "$TUNNEL_TOKEN" > ~/.config/keys/cloudflared/tunnel-token

# 2. 起完整 stack
cd deploy
docker-compose --profile public up -d

# 3. 验证：
curl -sf https://your-tunnel-domain/health     # 应返回 {"status":"ok"}
curl -sf https://your-tunnel-domain/api/auth/register -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"public_test@example.com","username":"public_test","password":"Test1234!"}'

# 4. 浏览器访问 https://your-tunnel-domain → 看到 stratum-web 登录页
```

通过条件：
- /health 公网可达
- /api/auth/register 公网可调（受 rate_limit + abuse_detection 保护）
- 前端 / 公网渲染（即使是 Next.js 静态首页或登录页）
- 验证后立即停 docker-compose（不长期暴露公网）

### 6.4 Landing / Registration 验收

- 未登录访问 `/` → 跳转 `/login` 或显示 landing 页（按 Wave 6 已实现的）
- 注册页文案审校（中文 / 排版 / 错误消息友好性）
- 登录后首屏 `/search` 渲染
- rate_limit 触发时 UI 显示友好提示（429 → "请求过于频繁，请稍后再试"）
- abuse_detection 触发时 UI 显示账号锁定提示

### 6.5 Wave 11 Sign-off 标准

| 项 | 通过条件 |
|---|---|
| README.md | 存在，含 Quick start + Architecture + Docs 索引 |
| CLAUDE.md | 存在，含 R-1 ~ R-6 + 路径白名单 + commit 规范 |
| AGENTS.md | 存在，描述 Agent 接入约定 |
| Makefile | 6 个 target 全部可跑 |
| .env.example | 覆盖 backend + frontend 必需变量 |
| CHANGELOG.md | v1.0.0 ~ v1.3.0 完整 |
| OpenAPI | `/docs` 可访问，所有 endpoint 有 summary + description |
| Cloudflare Tunnel | 真起一次，公网通过 /health 验证；验证完立即停 |
| 公网发布 manual sign-off | Wiki 单独 sign-off（不自动通过） |
| commit message | 严格 R-6 |

---

## §7 总体 Sign-off & 交付清单

### 7.1 Wave 维度 sign-off 链

```
Wave 10A (Block 集成)
  └─→ Wave 10B (缺失项补完)
      └─→ Wave 10C (真前端 e2e)
          └─→ Wave 11 (公网发布)
              └─→ Phase 14 整体完工
```

任一 Wave 不通过 → 停下报告，不进下一 Wave。

### 7.2 Phase 14 整体完工标准

- [ ] Part 1 ✅ sign-off（已有）
- [ ] Part 2 ⚠️ 有保留通过（已有，TECHNICAL_DEBT 登记）
- [ ] Part 3 Wave 10A ✅
- [ ] Part 3 Wave 10B ✅
- [ ] Part 3 Wave 10C ✅
- [ ] Part 3 Wave 11 ✅ + Wiki manual sign-off
- [ ] `TECHNICAL_DEBT.md` 中 Phase 14 Part 2 audit 区块全部 `[x]` 完成（或显式说明保留为后续 phase）
- [ ] `CHANGELOG.md` v1.3.0 段落完整
- [ ] `git log` 显示 Wave 10A/B/C + Wave 11 四个清晰 commit，message 符合 R-6

### 7.3 Phase 14 收官后下一阶段

按 ROADMAP v1.0：

- **Phase 11D**: omodul / oskill / oprim 扁平化清理 + corpus 索引层过滤下沉 + agent 真触发接通
- **Phase 2**: 网盘适配（OneDrive / GDrive storage adapter）
- **Phase 10**: 中文翻译 Agent（指令书已存在于 `docs/yiwancheng/PHASE_10_TRANSLATION_IMPLEMENTATION_INSTRUCTIONS_v0.1.md`）
- **Phase 5/6**: 平台内容 + 融合检索

Part 3 完工 ≠ v1.0 完整体，但意味着**Phase 14 alpha 闭环**：账号 + 公网 + 前端 + 9 Block + 真 e2e + 文档全部就绪，可进入引流和实际用户测试。

---

## §8 预算

| Wave | 预算 | 关键风险 |
|---|---|---|
| 10A | 5-7 天 | @helios/blocks 1.6 API 与设计书 1.5 假设可能不一致；annotation 后端缺端点 |
| 10B | 2-3 天 | sessions DAO 现有实现可能不支持 list_active_for_user（需扩 DAO） |
| 10C | 3-4 天 | e2e 起服务编排（真后端 + 真前端 + 测试 DB）配置复杂；CI 中 page.goto 不稳 |
| 11 | 2-3 天 | Cloudflare Tunnel 配置需要 Wiki 手动介入（token / DNS） |
| **合计** | **12-17 天** | 取设计预算上限 14 天 + 2-3 天 buffer |

---

## §9 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `@helios/blocks` 1.6 API 与本指令书示例不符 | 9 Block 集成 stuck | Wave 10A 启动第一步：完整 import + 读 README + 跑 storybook；如有不符立即停报告并补 adapter |
| 某 Block 在 1.6 中缺失（如 OUserProfileCard） | /profile 或 /settings 缺集成目标 | 已在 §4.2 / §4.3 提供条件分支：手写最小 UI + 显式登记债 |
| Annotation 后端 endpoint 不存在 | OAnnotationLayer 不能完整工作 | Wave 10A §3.3.5 已说明降级为只读展示模式 + 登记债 |
| e2e CI 不稳（次次需要 retry） | Wave 10C 通过率不达标 | `page.waitForLoadState("networkidle")` + 显式 retry 1 次 + e2e 拆分到 9 个 spec 文件减少耦合 |
| Cloudflare Tunnel 需要付费 / DNS / 邮箱验证 | Wave 11 公网验证 stuck | Wiki 提前完成 manual setup；CC 仅验证 endpoint 可达性 |
| 9302 与 9305 残留漏改 | share 公开页生产 bug 复发 | §4.5 grep 验证强制硬门槛 |
| commit message 不诚实复发 | R-1 静默闭环 | 每个 Wave sign-off 时审 commit message；CC 自检 + Wiki 双检 |

---

## §10 引用 / 参考文档

- **必读**：
  - `docs/yiwancheng/PHASE_14_PART2_SIGNOFF_REPORT.md`（Part 2 验收依据）
  - `docs/yiwancheng/TECHNICAL_DEBT.md` § Phase 14 Part 2 audit
  - `docs/design/PHASE_14_PART1_BACKEND_CC_v1.0.md` § 0 / § 1（红线传承）
  - `docs/design/PHASE_14_PART2_FRONTEND_CC_v1.0.md` § 0 / § 1（红线传承）+ § 2.1（路由树与依赖）
- **参考**：
  - `docs/design/STRATUM_SPEC_v0.6_PATCH.md`（数据模型最新版）
  - `docs/design/STRATUM_ROADMAP_v1.0.md`（v1.0 完整体路线）
  - `docs/yiwancheng/DECISION_LOG.md`（历史决策）
  - `@helios/blocks` 1.6.0 官方 README + Storybook（package 内）
- **配置**：
  - `deploy/docker-compose.yml`（端口 9302 是真理源）
  - `deploy/nginx.conf`
  - `deploy/Dockerfile.api`

---

## §11 启动检查清单

CC FULL AUTO 接 Part 3 启动前必须完成：

- [ ] Read 完成本指令书全文
- [ ] Read 完成 `PHASE_14_PART2_SIGNOFF_REPORT.md`
- [ ] Read 完成 `TECHNICAL_DEBT.md` Phase 14 Part 2 audit 区块
- [ ] `git status` 干净（无未提交修改）
- [ ] `git log --oneline -5` 显示 HEAD 为 `5fbcec23`（Wave 9）
- [ ] `pnpm --version` ≥ 11.2.2
- [ ] `python --version` ≥ 3.12
- [ ] `pnpm view @helios/blocks@1.6.0` 可拉取（registry 可达）

启动顺序：**Wave 10A → 10B → 10C → 11**，每个 Wave 走完整 sign-off 检查清单。

---

**Sign-off**：
- 指令书作者：Wiki + Cowork（设计）
- CC FULL AUTO 执行：待启动
- 预计完工：2026-06-XX（启动后 12-17 天）
- 完工后状态：Phase 14 整体收官，进入 Phase 11D + Phase 10 + Phase 2 选择窗口
