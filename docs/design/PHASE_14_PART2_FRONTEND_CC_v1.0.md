# PHASE 14 PART 2 — 前端 CC 执行指令书 (Wave 6-9)

**CC FULL AUTO 实施指令书**

**项目**: stratum-web 准产品 alpha — 前端
**Phase**: 14 Part 2 (3 段中第 2 段)
**前置**: Part 1 后端完工 (commit fb80701, 189 tests, 8 REST endpoint ready)
**执行**: CC FULL AUTO, Wave 6-9
**预算**: 2.4-3.0 月

---

## §0 范围声明 (R-4 严格)

✅ 允许:
- `~/projects/stratum/stratum-web/` 新建子项目 (monorepo subdir)
- 完全按 HELIOS_FRONTEND_STACK v2.0 stack 实施
- 接 Part 1 后端 REST API (localhost:9302)
- 集成 @helios/blocks v1.5.0 (9 Block)
- Vitest + Playwright + Storybook 测试 / 文档

❌ 禁止:
- **不修改 ~/projects/stratum/src/** (Part 1 后端代码)
- **不修改 ~/projects/platform/{omodul,oskill,oprim}/** 任何文件
- **不修改 @helios/blocks 内部代码** (作为依赖消费, 不 fork)
- 不在前端绕过 corpus 隔离 (任何接受用户输入 corpus_id 的逻辑 = block)
- 不擅自加付费 / 社区功能 (Step 11 RFC 锁定 alpha 不含)

如发现必须改后端才能完成某 Wave → 立即停报告 advisor, 不擅自改。

---

## §1 FULL AUTO 规则 (R-1 ~ R-6)

### R-1 失败不静默
TypeScript 编译错误 / ESLint 错误 / 测试失败 / Block 渲染异常 / 后端 401/500 → 明确报告。

### R-2 SPEC 是真理源
本指令书 + HELIOS_FRONTEND_STACK v2.0 + Helios v1.5.0 Block 文档是真理。不脑补不在范围的元素。

### R-3 真实示例强制
每个页面 / Block 集成必须有真实可跑的端到端验证 (curl backend + 浏览器渲染 + Playwright e2e 至少一项)。

### R-4 严格范围
见 §0。前端不动后端任何文件。

### R-5 namespace 隔离

新建路径:
```
~/projects/stratum/stratum-web/
├── package.json
├── pnpm-lock.yaml
├── next.config.ts
├── tsconfig.json
├── tailwind.config.ts (Tailwind 4 配置)
├── vitest.config.ts
├── playwright.config.ts
├── .storybook/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   ├── register/page.tsx
│   │   │   └── reset-password/page.tsx
│   │   ├── (app)/                # 已登录 layout
│   │   │   ├── layout.tsx
│   │   │   ├── search/page.tsx
│   │   │   ├── documents/page.tsx
│   │   │   ├── documents/[id]/page.tsx
│   │   │   ├── ai/page.tsx
│   │   │   ├── jobs/page.tsx
│   │   │   ├── notes/[id]/page.tsx
│   │   │   ├── settings/page.tsx
│   │   │   └── profile/[username]/page.tsx
│   │   └── share/[token]/page.tsx  # public, no auth
│   ├── lib/
│   │   ├── api-client.ts         # HTTP REST 客户端 (fetch + httpOnly cookie)
│   │   ├── auth.ts               # JWT 管理 (in-memory access token)
│   │   ├── query-client.ts       # TanStack Query setup
│   │   └── theme.ts              # zen 主题配置
│   ├── stores/
│   │   ├── auth.ts               # zustand: current user
│   │   └── ui.ts                 # zustand: sidebar open / theme
│   ├── components/
│   │   ├── layout/
│   │   ├── auth/
│   │   └── shared/
│   └── styles/
│       └── globals.css           # Tailwind 4 入口
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/                      # Playwright
```

### R-6 破坏性操作

需要 Wiki sign-off:
- `git rm` / `rm -rf` 任何已 commit 文件
- Block 集成时降级 @helios/blocks 版本
- 改后端代码

本指令书 sign-off:
- ✅ 新建 stratum-web/ 目录
- ✅ pnpm install (任何 dependencies)
- ✅ 跑 e2e 测试启动 dev server

---

## §2 Wave 6 — 项目初始化 + 认证 (0.5 月)

### 2.1 项目初始化

```bash
cd ~/projects/stratum
mkdir -p stratum-web
cd stratum-web
```

`package.json` 完全按 HELIOS_FRONTEND_STACK v2.0 锁版本:

```json
{
  "name": "stratum-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint . --max-warnings 0",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "test:e2e": "playwright test",
    "storybook": "storybook dev -p 6006"
  },
  "dependencies": {
    "next": "^16.2.6",
    "react": "^19.2.6",
    "react-dom": "^19.2.6",
    "@helios/blocks": "1.5.0",
    "@tanstack/react-query": "^5.100.11",
    "@tanstack/react-table": "^8.21.3",
    "@tanstack/react-virtual": "^3.13.25",
    "zustand": "^5.0.13",
    "motion": "^12.40.0",
    "lucide-react": "^1.16.0",
    "sonner": "^2.0.7",
    "react-hook-form": "^7.x",
    "zod": "^3.x",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
    "remark-math": "^6.0.0",
    "rehype-katex": "^7.0.1",
    "katex": "^0.17.0",
    "shiki": "^4.1.0",
    "rehype-pretty-code": "^0.14.3",
    "cmdk": "^1.1.1",
    "react-resizable-panels": "^4.11.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.6.0",
    "class-variance-authority": "^0.7.1"
  },
  "devDependencies": {
    "typescript": "^6.0.3",
    "tailwindcss": "^4.3.0",
    "tw-animate-css": "^1.4.0",
    "@tailwindcss/vite": "^4.3.0",
    "vite": "^8.0.14",
    "@vitejs/plugin-react": "^6.0.2",
    "vitest": "^4.1.7",
    "@testing-library/react": "^16.3.2",
    "@testing-library/user-event": "^14.6.1",
    "jsdom": "^29.1.1",
    "playwright": "^1.60.0",
    "@playwright/test": "^1.60.0",
    "eslint": "^9.39.4",
    "@eslint/js": "^9.39.4",
    "typescript-eslint": "^8.59.4",
    "eslint-plugin-react": "^7.37.5",
    "eslint-plugin-react-hooks": "^7.1.1",
    "storybook": "^10.4.1",
    "@storybook/react-vite": "^10.4.1",
    "@storybook/addon-docs": "^10.4.1",
    "@storybook/addon-a11y": "^10.4.1",
    "@storybook/addon-themes": "^10.4.1",
    "jest-axe": "^9.x",
    "axe-core": "^4.x"
  },
  "packageManager": "pnpm@11.2.2",
  "engines": {
    "node": ">=22.0.0",
    "pnpm": ">=11.0.0"
  }
}
```

### 2.2 配置文件

`next.config.ts`:
```typescript
import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  experimental: {
    typedRoutes: true,
  },
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost" },
    ],
  },
  rewrites: async () => [
    // 开发时代理 /api/* 到后端 9302 (生产由 nginx 处理)
    {
      source: "/api/:path*",
      destination: "http://localhost:9302/api/:path*",
    },
    {
      source: "/share/:token",
      destination: "http://localhost:9302/share/:token",
    },
  ],
};
export default config;
```

`tsconfig.json`: strict + `noUncheckedIndexedAccess` + Next.js 16 推荐

`tailwind.config.ts`: Tailwind 4 风格 (单行 `@import 'tailwindcss';` 在 globals.css), config 文件最小化

`src/styles/globals.css`:
```css
@import "tailwindcss";
@import "tw-animate-css";

/* Import @helios/blocks themes */
@import "@helios/blocks/styles.css";
@import "@helios/blocks/themes/zen.css";

@theme {
  /* 自定义 design tokens */
}

html[data-theme="zen"] {
  /* zen 主题已在 @helios/blocks/themes/zen.css 定义 */
}
```

### 2.3 lib/ 基础设施

#### `lib/api-client.ts`

```typescript
/**
 * HTTP REST 客户端
 * 
 * 设计:
 * - access token 内存中保存 (zustand auth store), 不放 localStorage (XSS 风险)
 * - refresh token 走 httpOnly cookie (后端设置, 浏览器自动带)
 * - 401 自动调 /api/auth/refresh 续期 + 重试原请求
 * - refresh 失败 → 跳 /login
 */

class ApiClient {
  private accessToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;
  
  setAccessToken(token: string | null) { this.accessToken = token; }
  
  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    // 1. 加 Authorization header
    // 2. credentials: 'include' (httpOnly cookie)
    // 3. 401 时 await refresh, 重试一次
    // 4. 仍 401 → throw AuthRequiredError, 触发跳 /login
    // 5. 其他错误 throw ApiError 含 status + message
  }
  
  get<T>(path: string) { return this.request<T>("GET", path); }
  post<T>(path: string, body: unknown) { return this.request<T>("POST", path, body); }
  // ... put, patch, delete
}

export const apiClient = new ApiClient();
```

错误处理类:
- `AuthRequiredError` — 401 不能 refresh, 调用方应跳 /login
- `ApiError` — 其他 4xx/5xx, 含 status + message + correlation_id
- `RateLimitError` — 429, 含 retry_after

#### `lib/query-client.ts`

```typescript
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: (failureCount, error) => {
        if (error instanceof AuthRequiredError) return false;
        return failureCount < 3;
      },
    },
  },
});
```

#### `stores/auth.ts` (zustand)

```typescript
import { create } from "zustand";

interface AuthState {
  user: UserPublic | null;
  accessToken: string | null;
  isLoading: boolean;
  
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
  loadCurrentUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // ... implementation
}));
```

⚠️ **关键安全**: accessToken 仅内存, 刷新页面后调 `loadCurrentUser` (用 refresh cookie 续 access token) 恢复。

### 2.4 路由结构

#### `app/layout.tsx` — 根 layout

```typescript
import { Providers } from "@/components/Providers";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" data-theme="zen" data-locale="zh-CN">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

`components/Providers.tsx`: QueryClientProvider + Toaster (sonner) + ThemeProvider (来自 @helios/blocks)

#### `app/(auth)/` 路由组

- `login/page.tsx` — react-hook-form + zod schema + 调 `useAuthStore.login`
- `register/page.tsx` — 同, 加 username 唯一性提示
- `reset-password/page.tsx` — Wave 6 暂跳过 (alpha 自助重置走邮件链接, 邮件发送 v1.1+ 接 SMTP)

#### `app/(app)/layout.tsx` — 已登录 layout (Sidebar + 顶 nav)

```typescript
'use client';
import { redirect } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuthStore();
  if (isLoading) return <LoadingScreen />;
  if (!user) redirect("/login");
  
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <TopNav />
        {children}
      </main>
    </div>
  );
}
```

Sidebar:
- /search (OSemanticSearch 入口)
- /documents (ODocumentTree)
- /ai (OAIQAPanel + OAISummaryCard)
- /jobs (OScheduledJobsManager)
- /settings (profile / sessions / theme)

### 2.5 测试

```
tests/unit/lib/test_api_client.test.ts          (≥10)
tests/unit/stores/test_auth.test.ts             (≥10)
tests/unit/components/test_login_form.test.tsx  (≥8)
tests/unit/components/test_register_form.test.tsx (≥8)
tests/e2e/auth.spec.ts                          (≥5: register → login → logout 全链)
```

红线 e2e:
```typescript
// tests/e2e/auth.spec.ts
test('register → login → /api/users/me → logout → redirect to login', async ({ page }) => {
  // 真后端 (localhost:9302) + 前端 (localhost:3000)
  // 全链路验证
});

test('expired access token auto-refresh', async ({ page, context }) => {
  // 模拟 access token 过期 → 自动 refresh → 重试成功
});

test('refresh expired → redirect to login', async ({ page }) => {
  // refresh cookie 也过期 → 跳 /login
});
```

### 2.6 Wave 6 Gate

```bash
cd ~/projects/stratum/stratum-web
pnpm install
pnpm type-check         # 0 errors
pnpm lint               # 0 errors / 0 warnings
pnpm test               # 全过, 覆盖率 ≥80% (前端业务代码)

# 启动后端 (在另一个 terminal)
cd ~/projects/stratum && uvicorn stratum.http_api.app:app --port 9302 &
sleep 3

# 启动前端
pnpm dev &
sleep 5

# e2e
pnpm test:e2e          # 全过

# 手动浏览器验证
echo "open http://localhost:3000/register in browser"
# 注册 → 自动跳 /search → 显示 sidebar + nav

# 关闭服务
pkill -f "uvicorn stratum"
pkill -f "next dev"

cd ~/projects/stratum
git add stratum-web/
git commit -m "Phase 14 Wave 6: stratum-web 初始化 + 认证页 + App Router + zen 主题"
```

报告:
```
Wave 6 ✅ (stratum-web 项目初始化 + 认证)
- 项目结构按 v2.0 stack 完整 (Next.js 16 / React 19 / Tailwind 4 / pnpm 11)
- lib/api-client: 401 auto-refresh + AuthRequiredError 流程
- stores/auth: zustand, accessToken 内存保存
- 路由: (auth)/login + register, (app)/layout 鉴权 redirect
- 测试: <N> 个 (>=46), 单元 + e2e 全过
- 类型检查 / lint: 0 errors
- 端到端 register → login → me → logout 验证通过
- commit: <hash>
进 Wave 7
```

---

## §3 Wave 7 — 9 Block 集成前 4 (0.7 月)

### 3.1 前 4 Block 接入清单

| Block | 路由 | 数据源 |
|---|---|---|
| OCitationCard | 嵌入其他 Block 内 | 复用 |
| OSemanticSearch | `/search` | POST /api/search |
| OAIQAPanel | `/ai` 子 tab "QA" | POST /api/agents/reading_companion/run |
| OAISummaryCard | `/ai` 子 tab "Summary" | GET /api/agents/runs?agent=daily_digest&latest=true |

### 3.2 OSemanticSearch — `/search` 页

`app/(app)/search/page.tsx`:

```typescript
'use client';
import { OSemanticSearch } from "@helios/blocks";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export default function SearchPage() {
  const searchMutation = useMutation({
    mutationFn: async (req: SearchRequest) => {
      return apiClient.post<SearchResponse>("/api/search", req);
    },
  });
  
  return (
    <div className="container max-w-4xl py-8">
      <OSemanticSearch
        onSearch={searchMutation.mutate}
        results={searchMutation.data?.results ?? []}
        metadata={searchMutation.data?.metadata}
        isLoading={searchMutation.isPending}
        error={searchMutation.error}
        // v1.0 限制
        features={{
          rerank: true,
          expand: true,
          // matchedLanguage: false  (v1.0 未暴露)
        }}
      />
    </div>
  );
}
```

⚠️ 跟 Helios v1.0 限制对齐:
- `StratumFeature.TTS = false`
- char-level fragment 关闭

### 3.3 OAIQAPanel — `/ai` 页 QA tab

```typescript
'use client';
import { OAIQAPanel, OCitationCard } from "@helios/blocks";
import { useMutation } from "@tanstack/react-query";

export default function AIPage() {
  const qaMutation = useMutation({
    mutationFn: async (query: string) => {
      return apiClient.post<RunAgentResponse>(
        "/api/agents/reading_companion/run",
        { params: { query } }
      );
    },
  });
  
  return (
    <OAIQAPanel
      onAsk={qaMutation.mutate}
      agentRun={qaMutation.data?.agent_run}
      citations={qaMutation.data?.citations ?? []}
      isLoading={qaMutation.isPending}
      // v1.0: 非流式, OAIQAPanel 用 Promise + loading
      streaming={false}
    />
  );
}
```

⚠️ **POST /api/agents/:name/run 当前是 stub (Wave 5 注明)**, agent_run 返回 `status: "pending"`。Wave 7 实施时:
1. 先用 mock 响应渲染 OAIQAPanel UI 流程
2. 标 TECHNICAL_DEBT: "OAIQAPanel 真触发 omodul agent 等 Phase 11D 或专项补"
3. 不擅自改后端 (R-4)

报告 advisor: stub agent 影响前端真实体验, 建议 Phase 14 Part 3 集成阶段考虑专项 "agent stub → 真触发" 补丁。

### 3.4 OAISummaryCard — `/ai` 页 Summary tab

```typescript
const { data, isLoading } = useQuery({
  queryKey: ["daily-digest-latest"],
  queryFn: () => apiClient.get<{ agent_run: AgentRun; citations: Citation[] }>(
    "/api/agents/runs?agent=daily_digest&latest=true"
  ),
});

<OAISummaryCard
  agentRun={data?.agent_run}
  citations={data?.citations ?? []}
  isLoading={isLoading}
/>
```

### 3.5 OCitationCard

@helios/blocks 已 export, 嵌入 OAIQAPanel / OSemanticSearch 内部使用, Wave 7 无独立页面。

确保 Citation 数据契约对齐: 后端 SearchResult.citation + AgentResult.citations 含 `{anchor: object, ...}` (Phase 11C v1.3.4 已对齐)。

### 3.6 测试

```
tests/unit/pages/search.test.tsx                  (≥10)
tests/unit/pages/ai.test.tsx                      (≥10)
tests/e2e/search.spec.ts                          (≥5: 输入 query → 返回 results → 点 result → 跳 /documents/:id)
tests/e2e/ai-qa.spec.ts                           (≥3)
tests/e2e/ai-summary.spec.ts                      (≥3)
```

### 3.7 Wave 7 Gate

```bash
cd ~/projects/stratum/stratum-web
pnpm type-check && pnpm lint && pnpm test
pnpm test:e2e

# 手动验证: 浏览器登录后访问 /search /ai, 验证 4 Block 渲染 + 真后端交互
git add -A && git commit -m "Phase 14 Wave 7: 9 Block 集成 1-4 (Citation/SemanticSearch/QA/Summary)"
```

报告:
```
Wave 7 ✅ (前 4 Block 集成)
- /search /ai (QA + Summary) 页面实施
- OCitationCard 嵌入复用
- TECHNICAL_DEBT 登记: agent stub 真触发待补
- 测试: <N> 个 (>=31), 全过
- commit: <hash>
进 Wave 8
```

---

## §4 Wave 8 — 9 Block 集成后 5 (0.7 月)

### 4.1 后 5 Block 接入清单

| Block | 路由 | 数据源 |
|---|---|---|
| OScheduledJobsManager | `/jobs` | GET/POST/PUT/DELETE /api/scheduled_jobs |
| ODocumentTree | `/documents` 左侧 | GET /api/substrates |
| ODocumentReader | `/documents/[id]` 主区 | GET /api/substrates/:id + GET /api/substrates/:id/derivatives |
| OAnnotationLayer | 嵌入 ODocumentReader | derivatives (chunk-level v1.0) |
| OBacklinkPanel | `/notes/[id]` 右侧 | GET /api/notes/:id/backlinks |

### 4.2 OScheduledJobsManager — `/jobs` 页

```typescript
const { data: jobs } = useQuery({
  queryKey: ["scheduled-jobs"],
  queryFn: () => apiClient.get<{ items: ScheduledJob[] }>("/api/scheduled_jobs"),
});

const updateJob = useMutation({
  mutationFn: (job: ScheduledJob) => apiClient.put(`/api/scheduled_jobs/${job.id}`, job),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] }),
});

const { data: runs } = useQuery({
  queryKey: ["job-runs", selectedJobId],
  queryFn: () => apiClient.get(`/api/scheduled_jobs/${selectedJobId}/runs`),
  enabled: !!selectedJobId,
});

<OScheduledJobsManager
  jobs={jobs?.items ?? []}
  runs={runs}
  onJobUpdate={updateJob.mutate}
  onJobDelete={...}
  selectedJobId={selectedJobId}
  onSelectJob={setSelectedJobId}
/>
```

### 4.3 ODocumentTree — `/documents` 左侧

```typescript
const { data: substrates } = useInfiniteQuery({
  queryKey: ["substrates", filterMedium],
  queryFn: ({ pageParam }) => apiClient.get<ListSubstratesResponse>(
    `/api/substrates?cursor=${pageParam ?? ""}&medium=${filterMedium}&limit=50`
  ),
  getNextPageParam: (last) => last.next_cursor,
});

<ODocumentTree
  substrates={substrates?.pages.flatMap(p => p.items) ?? []}
  onSelect={(id) => router.push(`/documents/${id}`)}
  onLoadMore={() => fetchNextPage()}
  groupBy="medium"
/>
```

### 4.4 ODocumentReader + OAnnotationLayer — `/documents/[id]`

```typescript
const { data: substrate } = useQuery({
  queryKey: ["substrate", id],
  queryFn: () => apiClient.get<Substrate>(`/api/substrates/${id}`),
});

const { data: derivatives } = useQuery({
  queryKey: ["derivatives", id],
  queryFn: () => apiClient.get<{ items: Derivative[] }>(
    `/api/substrates/${id}/derivatives`
  ),
});

<ODocumentReader
  substrate={substrate}
  derivatives={derivatives?.items ?? []}
  annotationLayer={
    <OAnnotationLayer
      fragments={derivatives?.items?.flatMap(d => d.fragments) ?? []}
      // v1.0: chunk-level only, char-level disabled
      mode="chunk"
    />
  }
/>
```

### 4.5 OBacklinkPanel — `/notes/[id]` 右侧

```typescript
const { data: backlinks } = useQuery({
  queryKey: ["backlinks", noteId],
  queryFn: () => apiClient.get<{ items: Note[] }>(
    `/api/notes/${noteId}/backlinks`
  ),
});

<OBacklinkPanel
  notes={backlinks?.items ?? []}
  onNoteClick={(n) => router.push(`/notes/${n.id}`)}
/>
```

### 4.6 测试

```
tests/unit/pages/jobs.test.tsx                    (≥8)
tests/unit/pages/documents.test.tsx               (≥10)
tests/unit/pages/document_reader.test.tsx         (≥10)
tests/unit/pages/note_view.test.tsx               (≥8)
tests/e2e/document_workflow.spec.ts               (≥5: 列表 → 选 doc → reader → 选 fragment 跳 note)
tests/e2e/scheduled_jobs_workflow.spec.ts         (≥5: 列表 → 改 enabled → 看 runs)
```

### 4.7 Wave 8 Gate

```bash
cd ~/projects/stratum/stratum-web
pnpm type-check && pnpm lint && pnpm test && pnpm test:e2e

# 手动浏览器验证 5 Block 渲染 + 真后端交互 + 数据契约对齐
git add -A && git commit -m "Phase 14 Wave 8: 9 Block 集成 5-9 (Jobs/DocTree/DocReader/Annotation/Backlink)"
```

报告:
```
Wave 8 ✅ (后 5 Block 集成)
- /jobs /documents /documents/:id /notes/:id 全部实施
- ODocumentTree 走 infinite query
- OAnnotationLayer chunk-level mode (v1.0 限制对齐)
- 测试: <N> 个 (>=46), 全过
- commit: <hash>
进 Wave 9
```

---

## §5 Wave 9 — share + profile + settings (0.3 月)

### 5.1 share 公开页 — `/share/[token]` (无 auth)

⚠️ 这是唯一**不需要登录**的页面, layout 不能用 `(app)/layout.tsx`。

`app/share/[token]/page.tsx`:

```typescript
// 不是 'use client', 是 Server Component (RSC)

import { headers } from "next/headers";

export default async function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  
  // 服务端 fetch (不带任何 auth)
  const res = await fetch(`http://localhost:9302/share/${token}`, {
    cache: "no-store",
  });
  
  if (res.status === 410) return <ShareExpired />;
  if (res.status === 404) return <ShareNotFound />;
  if (!res.ok) return <ShareError />;
  
  const data = await res.json();
  
  return (
    <div className="container max-w-3xl py-12">
      <ShareHeader sharer={data.shared_by_username} sharedAt={data.shared_at} />
      <PublicNoteRenderer note={data.note} />
      <ShareFooter />     {/* "Powered by Stratum + 注册引导" */}
    </div>
  );
}
```

`ShareHeader` / `PublicNoteRenderer` / `ShareFooter` 是新建组件 (不依赖 @helios/blocks 的认证 context)。

### 5.2 profile 页 — `/profile/[username]`

可选: 已登录用户看自己 profile 显示 edit / share list, 看别人 profile 只显示公开信息。

```typescript
const { data: profile } = useQuery({
  queryKey: ["profile", username],
  queryFn: () => apiClient.get(`/api/users/by-username/${username}`),
});

// 自己看 → 显示 edit
// 别人看 → 只显示 display_name + bio + 公开 share 列表
```

⚠️ 后端 Part 1 没暴露 `/api/users/by-username/:username` (Wave 5 缺), 需 Part 3 补 1 个 endpoint。Wave 9 mock 数据先实施 UI, Part 3 补真接口。

### 5.3 settings 页 — `/settings`

3 个 tab:
- Profile (display_name / bio / avatar 上传 - Wave 9 接 POST /api/users/me/avatar + PATCH /api/users/me)
- Sessions (列表 + revoke - 调 GET /api/users/me/sessions + DELETE /api/users/me/sessions/:id)
- Theme (zen / terminal-light / academic 切换 - 改 html data-theme + localStorage)

⚠️ Sessions endpoint Wave 5 未实施, Wave 9 同 profile mock + Part 3 补。

### 5.4 share 触发组件 (嵌入 /documents 等)

```typescript
// components/shared/ShareNoteButton.tsx
function ShareNoteButton({ noteId }: { noteId: string }) {
  const createShare = useMutation({
    mutationFn: () => apiClient.post(`/api/share/note/${noteId}`, {
      allow_anonymous: true,
    }),
    onSuccess: (data) => {
      navigator.clipboard.writeText(data.share_url);
      toast.success("已复制 share 链接");
    },
  });
  return <Button onClick={() => createShare.mutate()}>分享</Button>;
}
```

### 5.5 测试

```
tests/unit/pages/share.test.tsx                   (≥10: token 有效 / 过期 / 不存在 / 数据脱敏渲染)
tests/unit/pages/settings.test.tsx                (≥10)
tests/unit/components/share_button.test.tsx       (≥5)
tests/e2e/share_workflow.spec.ts                  (≥8: A 创建 note → A 分享 → 复制链接 → 无痕浏览器访问 → 不显示 user_id/email)
tests/e2e/settings_theme.spec.ts                  (≥3: 切换 theme → 持久化 → 刷新仍生效)
```

红线 e2e (任一 fail block):

```typescript
test('public share page does not expose user_id/corpus_id/email', async ({ page }) => {
  // 调 GET /share/:token
  const response = await page.goto(`/share/${validToken}`);
  const html = await response.text();
  expect(html).not.toContain("user_id");
  expect(html).not.toContain("corpus_id");
  expect(html).not.toContain("@");  // email 含 @
});

test('public share page accessible without login', async ({ page, context }) => {
  // 清空 cookies (无 auth)
  await context.clearCookies();
  await page.goto(`/share/${validToken}`);
  // 应该正常显示, 不跳 /login
  await expect(page.locator("article")).toBeVisible();
});
```

### 5.6 Wave 9 Gate

```bash
cd ~/projects/stratum/stratum-web
pnpm type-check && pnpm lint && pnpm test && pnpm test:e2e

# 端到端 share workflow
# 1. 用户 A 登录, 创建 note, share
# 2. 无痕浏览器访问 share 链接, 验证数据脱敏

git add -A && git commit -m "Phase 14 Wave 9: share 公开页 + profile + settings"
```

报告:
```
Wave 9 ✅ (share + profile + settings)
- /share/[token] 公开页 (Server Component + RSC, 无 auth)
- /profile/[username] (部分 mock, 待 Part 3 后端补 endpoint)
- /settings (3 tab: profile/sessions/theme, 部分 mock)
- ShareNoteButton 组件
- 数据脱敏红线 e2e 全过
- 测试: <N> 个 (>=36), 全过
- commit: <hash>
进 Part 3 (集成 + ship)
```

---

## §6 Part 2 完工 + 跨 Wave 整合

### 6.1 完工 SELF_CHECK

CC 完工时附 `SELF_CHECK_PHASE14_PART2.md`:
- Wave 6-9 全部 Gate 通过
- 9 Block 全部接入 + 数据契约对齐
- v1.0 限制全部正确处理 (TTS / chunk-level / 非流式 / list_substrates)
- 端到端用户旅程: register → login → ingest → search → ai qa → reader → 标注 → 反链 → share → 匿名访问 全链
- type-check / lint / 单元 / e2e 全过
- Storybook stories (每个页面 ≥ 1 story) 覆盖

### 6.2 TECHNICAL_DEBT 登记

Part 2 期间发现需 Part 3 / 后续补的:
- Wave 7: agent stub → 真触发 omodul agents (R-4 受限, 留 Phase 11D 或专项补丁)
- Wave 9: GET /api/users/by-username/:username (Part 3 后端补)
- Wave 9: GET/DELETE /api/users/me/sessions (Part 3 后端补)
- 邮件验证 (Wave 1 暂跳, v1.1+ 接 SMTP)
- 实时通信 (v1.1+ SSE)
- char-level fragment (v1.1+ / Phase 15)

### 6.3 跨项目通知

跟 Helios 前端组同步:
- 9 Block 全接入完成
- v1.0 限制全部正确实施
- 任何 Block 行为问题 → 走 helios-blocks issue tracker

---

## §7 异常处理 (R-1)

立即停 + 报告:
- pnpm install 失败 (依赖冲突 / 版本不兼容)
- TypeScript 编译错误 (v2.0 stack 不兼容)
- @helios/blocks 1.5.0 行为跟文档不符
- 后端 REST 返回跟前端预期 schema 不符 (Part 1 接口契约可能跟 v1.0 文档微差)
- e2e 红线测试 fail (数据脱敏 / share 无 auth 可访问)

非阻塞继续:
- 部分 Block 配色微调 (zen 主题已默认, 不深调)
- profile / settings 部分 mock (Part 3 补)
- 邮件验证 / SMTP (v1.1+)
- 实时流式 (v1.1+)

---

## §8 时间预算总览

| Wave | 工作 | 月 |
|---|---|---|
| 6 | 项目初始化 + 认证 | 0.5 |
| 7 | 9 Block 前 4 | 0.7 |
| 8 | 9 Block 后 5 | 0.7 |
| 9 | share + profile + settings | 0.3 |
| **Part 2 总** | | **2.2 月** |

跟 Step 11 RFC §2.2 前端小计 (2.4-3.0 月) 接近, 略低 (部分 mock 让位 Part 3 补)。

---

**End Part 2**

— Stratum 经理人 Claude
2026-05-24
