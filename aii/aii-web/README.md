# aii-web

AII 认识论知识图谱 Web 前端。

由 Helios 前端架构组按 AII-FRONTEND-REQ-002 交付的 **starter 脚手架**。业务逻辑(调引擎、数据映射、措辞红线)由 AII 经理人 / CC 自己填。

## 你拿到的

- ✅ Next.js 16 App Router + React 19 + Tailwind 4 项目
- ✅ `@helios/blocks@1.9.0` + `@helios/oui@0.1.1` 已配好(tarball 在 `vendor/`)
- ✅ `OAppProviders` (theme=professional) + `LangProvider` (zh-en) + `OAppShell` 装配
- ✅ 6 个 Page 骨架(query / ingest / health / diagnose / evolution / governance),路由 + 默认导航全连通
- ✅ `apiClient`(fetch 封装),含统一响应包络处理 + `degraded_no_provider` 检测
- ✅ `useApi` / `useApiNoArg` hook,Page 一行调 API
- ✅ `<DegradedBanner />` 组件实现红线 #6(LLM 降级时醒目提示,不静默)
- ✅ Mock 数据(`src/lib/mock-data.ts`)— 后端没起也能跑 dev,看 UI
- ✅ Mobile-first(375px 可用,桌面自适应)
- ✅ TypeScript 严格模式

## 升级提醒(请注意)

REQ-002 写的是 `@helios/blocks@1.8.0`,我交付时**已升到 v1.9.0**。理由:

- v1.9.0(Wiki 拍板)新增 `<LangProvider>`,**中英并列默认**,跟 AII 经理人审视项目调性一致
- 你 6 Page 直用 12 个 Block(`OEpistemicBadge` / `OEpistemicCard` / `OEpistemicDistribution` / `ORadarChart` / `OConfirmDialog` / `OAlertBadge` / `OKPICard` / `OHighDensityTable` / `OEventTimeline` / `OSearchBar` / `OJsonViewer` / `OPlanConsistencyChart`)在 1.9.0 全 i18n 化
- 完全向后兼容,**你的代码不需要任何改动**就能升

如果你坚持要 1.8.0:把 `vendor/helios-blocks-1.9.0.tgz` 换成 1.8.0 那个 + `package.json` 改路径。但 LangProvider 那一行也得去掉(1.8.0 没有这个 API)。

## 怎么跑

### 1. 装依赖

```bash
cd aii-web
pnpm install        # 或 npm install / yarn install
```

`vendor/` 里有两个 tarball,`package.json` 已经把它们引用为 `file:./vendor/xxx.tgz`,装一次就好。

### 2. 配 env

```bash
cp .env.local.example .env.local
# 编辑 .env.local:
#   NEXT_PUBLIC_USE_MOCK=true    # 后端没起时先用 mock
#   NEXT_PUBLIC_AII_API_BASE=http://localhost:8000
```

### 3. 跑 dev server

```bash
pnpm dev
# 打开 http://localhost:3000
# 自动 redirect 到 /query
```

### 4. 切真后端

```bash
# .env.local
NEXT_PUBLIC_USE_MOCK=false
NEXT_PUBLIC_AII_API_BASE=http://localhost:8000   # 改成你后端的实际地址
```

TopBar 角标会显示当前是 `MOCK` 还是 `localhost:8000`。

## 项目结构

```
aii-web/
├── package.json                  # 依赖
├── next.config.ts                # transpilePackages
├── tsconfig.json
├── postcss.config.mjs            # Tailwind v4
├── .env.local.example
├── vendor/
│   ├── helios-blocks-1.9.0.tgz   # Helios Block 元素库(file: 依赖)
│   └── helios-oui-0.1.1.tgz      # Helios OUI 框架(file: 依赖)
└── src/
    ├── app/
    │   ├── layout.tsx            # Providers + Shell 装配
    │   ├── page.tsx              # / → 重定向到 /chat
    │   ├── globals.css           # Tailwind + helios themes
    │   ├── chat/page.tsx         # REQ-003:对话(认识论暴露)
    │   ├── query/page.tsx        # P0:查询
    │   ├── ingest/page.tsx       # P0:摄入
    │   ├── health/page.tsx       # P1:图健康
    │   ├── diagnose/page.tsx     # P2:诊断
    │   ├── evolution/page.tsx    # P3:进化
    │   └── governance/page.tsx   # P3:治理
    ├── components/
    │   ├── AppShell.tsx          # 7 项侧边导航装配
    │   ├── DegradedBanner.tsx    # 红线 #6:降级提示
    │   └── chat/                 # REQ-003 对话区组件
    │       ├── ChatPage.tsx          # 主容器
    │       ├── ChatInput.tsx
    │       ├── ChatMessage.tsx
    │       ├── AIIResponse.tsx       # mode + meter + answer + citations + disclaimer
    │       ├── ConfidenceMeter.tsx   # 可信度可视化(硬编码 confidence→color)
    │       ├── CitationsList.tsx     # 依据列表 + OEpistemicBadge
    │       └── ModeTag.tsx           # mode 视觉标签
    ├── hooks/
    │   └── useApi.ts             # 调 API 的通用 hook
    ├── lib/
    │   ├── env.ts                # NEXT_PUBLIC_* 集中
    │   ├── api-client.ts         # 6 endpoints + envelope
    │   └── mock-data.ts          # mock 实现(后端没起时)
    └── types/
        └── api.ts                # 响应类型
```

## 业务逻辑填到哪儿(每页都有 `TODO: AII business logic` 标注)

### `/query`
- 把 mock query 改成 AII 真实业务 query 流
- 实现 filters UI(date / source / grade 过滤)
- 点击 Card 跳详情 / 高亮 fragment

### `/ingest`
- 加文件上传(用 `<OFileUpload>`,已在 `@helios/blocks` 暴露)
- 加 metadata 表单(date / tags / language)

### `/health`
- 接 `<OKPICard>` 显示总节点 / 总边 / 反证 / 健康分(starter 给的是 KPIBlock 简陋占位)
- OEpistemicDistribution 点 segment 跳 `/query?grade=X` 过滤
- 加趋势图(7d health_score 折线)

### `/diagnose`
- 加 `<OSearchableSelect>` 选 fragment
- 多 series 对比(当前片段 vs 同 grade 中位数)
- **不要**给 ORadarChart 加 reference line/target zone — 库层硬护栏(红线 #3),你想加也加不了

### `/evolution`
- pending 项的接受 / 拒绝按钮调 `/governance/action`
- 加 `<OConfirmDialog>` 二次确认
- 加 filter(仅看回滚 / 仅看接受)

### `/governance`
- 联动 Health / Evolution 跳过来时自动填 target_id
- audit_log 列表预留(可能后端再加一个 `/governance/audit-log GET`)
- rollback 之前显示影响范围

## 红线如何在前端体现

| 红线 | 实现位置 | 说明 |
|---|---|---|
| #1 视觉硬规范 | `<OEpistemicBadge>` 内部 | proven 永远安全色,unverified 永远警示色,**不允许覆盖** |
| #2 反证强制显示 | `<OEpistemicCard>` 内部 | defeaters 非空时**必显示**,不可隐藏 |
| #3 不开处方 | `<ORadarChart>` API 层 | **API 不接受 referenceLine / targetZone / thresholdBand** prop — 各项目想加也加不了 |
| #4 措辞护栏 | 后端 LLM prompt 层 | 前端不管,AII 经理人在后端做 |
| #5 审计日志 | `/governance` Page UI 强制 reason 必填 + OConfirmDialog 二次确认 | |
| #6 降级不静默 | `<DegradedBanner />` + `useApi` 自动 detect `warning === "degraded_no_provider"` | 你只要 `{state.degraded && <DegradedBanner />}`,starter 6 Page 全部都做了 |

## 主题:professional

`<OAppProviders theme="professional">` 已经装好。如果想试别的(`academic` / `terminal-dark` / `cyberpunk` 等共 11 套),改这一行的字符串即可。professional 跟 AII 调性(诚实、克制)最匹配,Helios 也建议保留。

## i18n:中英并列默认

`<LangProvider lang="zh-en">`(v1.9.0 默认)— 所有 Helios Block 文字会显示成 "中文 (English)" 形式。

如果你要纯中文:`lang="zh"`;纯英文:`lang="en"`。

你**自己写**的文字(`<h1>查询 / Query</h1>` 这种),如果想自动切,用 `useUiLang()` hook:

```tsx
import { useUiLang } from '@helios/blocks';

function MyComponent() {
  const { tr } = useUiLang();
  return <h1>{tr('查询', 'Query')}</h1>;
}
```

## 移动端

- Body min-width 375px
- AppShell 在 `<lg` 自动折叠 SideBar(可点 hamburger 切换)
- Page content 用 `p-4 md:p-6 lg:p-8` 自适应留白
- 表单 / 输入 / 按钮都用 Tailwind 默认 sm/md/lg 断点,375px 默认可用

## TypeScript

```bash
pnpm typecheck    # tsc --noEmit
```

应该 0 错。

## Lint

```bash
pnpm lint
```

## Build

```bash
pnpm build
pnpm start
```

## 反馈渠道

任何 starter 装配 / Block 使用问题 → 找 Helios 前端架构组。
业务逻辑 / 引擎对接 / 后端契约调整 → AII 经理人 / CC 自管。

---

— Helios 前端架构组,2026-06-05
