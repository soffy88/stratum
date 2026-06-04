# PHASE 17.5 - 17.10 完整推进指令书 (alpha 引流前最后冲刺)

**项目**: Stratum SaaS alpha v0.8 → v1.0 引流准备
**前置**: SPEC v0.7 Wiki 通过 + 18 元素 ship + omodul PR #1 merge
**执行**: CC FULL AUTO 6 Phase 顺序推进
**预算**: ~ 6-9 周到真引流
**目标**: alpha 真用户视角完整 + 引流前 P0 全清

---

## §0 范围声明 (R-4)

✅ 允许:
- Stratum SaaS 端 backend / frontend / 部署改动
- 调 oprim / oskill / omodul / obase 已 ship 元素
- 容器 rebuild stratum-sl / stratum-api / stratum-web
- 新建文档 (README / USER_GUIDE / landing 修订)
- 新建 e2e 测试

❌ 禁止 (R-4 跨经理人协调):
- 修主库 (obase / oprim / oskill / omodul) — 走 PR 流程
- 修 dns_pinned_transport (等 obase / oprim 经理人 v0.10.1 / v2.29.1)
- 修底层 ws.py 鉴权 (走后端 R-4, advisor 在 17.6 给明确范围)

---

## §1 R-1 / R-3 / R-4 / R-5 / R-6 强制要求

- **R-1 失败立即停**: 任何 test fail / build error / 公网真返错 立即停报告, 不静默
- **R-3 真用户视角**: 每 Phase 完工 Wiki 浏览器真测试 (advisor 不接受 "build pass + curl 200")
- **R-4 范围严守**: 见 §0
- **R-5 namespace**: 每 Phase 改动清单见对应章节
- **R-6 破坏性**: 不删 Phase 14-17 已 ship 功能, 兼容性兜底

---

## §2 Phase 17.5 — URL 抓取 UX 升级 (1 周)

### 2.1 背景

Wiki 浏览器测试 Phase 17-A 反馈"功能简陋, 给地址抓什么内容不知道". 跟 Phase 16 AI 助手 D1-D4 同模式: dialog 现一个 URL 框 + 按钮, 用户没控制 / 没反馈 / 没预览.

### 2.2 改动文件清单

```
src/components/UrlIngestDialog.tsx          # 大改: 增强字段 + 反馈 + 预览
src/app/(app)/documents/page.tsx            # 调用方加 onSuccess callback 刷文档列表
tests/unit/components/url-ingest-dialog.test.tsx  # 新增单元测试
tests/e2e/phase17_5_url_ux.spec.ts          # 新增 e2e
```

### 2.3 任务 D1: dialog 增强字段

```tsx
// UrlIngestDialog.tsx
interface UrlIngestFormState {
  url: string;
  title: string;          // 可选, 默认从网页 title 抽
  tags: string[];         // 可选, 逗号分隔
  fetchMode: "full" | "summary";  // alpha 默认 full
  note: string;           // 可选, 用户备注
}

const initial: UrlIngestFormState = {
  url: "",
  title: "",
  tags: [],
  fetchMode: "full",
  note: "",
};
```

dialog 字段:
- URL (必填, autofocus, placeholder "https://example.com/article")
- 标题 (可选, placeholder "留空自动从网页抽取")
- 标签 (可选, 逗号分隔, e.g. "kelly criterion, quant, btc")
- 内容模式 (radio: "全文" / "摘要 (LLM 提炼)")
- 备注 (可选, multiline textarea, 用户为什么收藏)

### 2.4 任务 D2: 抓取过程真反馈

```tsx
const [phase, setPhase] = useState<"input" | "fetching" | "success" | "error">("input");
const [result, setResult] = useState<WebClipResult | null>(null);
```

抓取流程:
1. 用户点 "抓取" → phase = "fetching"
2. dialog **不关**, 显示 loading spinner + 提示文字 ("正在抓取 example.com..." 真显示 hostname)
3. fetch 完 → phase = "success" / "error"
4. 用户主动点 "关闭" 或 "继续抓另一个"

### 2.5 任务 D3: 抓取后 inline 预览

success 状态显示:
```tsx
<div className="mt-4 p-4 bg-green-50 rounded">
  <h3 className="font-semibold">✓ 抓取成功</h3>
  <dl className="mt-3 text-sm">
    <dt>真标题</dt><dd>{result.title}</dd>
    <dt>真摘要</dt><dd className="line-clamp-3">{result.snippet}</dd>
    <dt>字数</dt><dd>{result.word_count}</dd>
    <dt>medium</dt><dd>{result.medium}</dd>
  </dl>
  <div className="flex gap-2 mt-3">
    <Link href={`/documents/${result.substrate_id}`} className="btn-primary">查看完整 →</Link>
    <button onClick={resetForm} className="btn-secondary">继续抓另一个</button>
    <button onClick={onClose} className="btn-ghost">关闭</button>
  </div>
</div>
```

### 2.6 任务 D4: 错误处理细化

```tsx
const errorMessages: Record<string, string> = {
  "ssrf_blocked": "URL 是内网地址, 已拒绝以保护服务器安全",
  "fetch_timeout": "抓取超时 (>30s), 该网页可能需要登录或 JS 渲染. 试试用浏览器扩展.",
  "parse_failed": "网页内容无法解析 (可能是图片/视频/PDF). 试试直接上传文件.",
  "too_large": "网页内容超过 10MB 限制",
  "not_found": "网页 404 不存在",
  "auth_required": "网页需登录访问, 试试用浏览器扩展 (扩展能用你的登录态)",
  "rate_limited": "网页限制访问频率, 稍后重试",
};

// 友好错误提示 + 给用户建议
```

### 2.7 任务 D5: 后端 inbox.py 支持新字段

后端 `POST /api/v1/inbox/web-clip` 当前接受 url, 加 optional:
- title_override (用户填的标题)
- tags (List[str])
- fetch_mode ("full" / "summary")
- note (用户备注)

返 schema 扩展:
```python
{
  "substrate_id": "01KT...",
  "title": "网页标题",
  "snippet": "前 500 字符...",
  "word_count": 3500,
  "medium": "webpage",
  "url": "https://...",
}
```

### 2.8 Gate

```bash
# 后端
pytest tests/ -k "web_clip or inbox" -v

# 前端
cd stratum-web
pnpm type-check && pnpm lint && pnpm build && pnpm test --run

# e2e
pnpm test:e2e --grep "phase17_5"

# 容器 rebuild
cd ../deploy
docker compose build stratum-sl stratum-api stratum-web
docker compose up -d
sleep 10

# 真公网测试 (Wiki 浏览器):
# 1. /documents 点 "输入 URL"
# 2. 输 https://en.wikipedia.org/wiki/Kelly_criterion
# 3. 加标题 "凯利公式 wiki" + 标签 "凯利公式, quant"
# 4. 点抓取 → loading → 真预览返
# 5. 点 "查看完整 →" → 进 /documents/[id] 真渲染网页内容

git commit -m "Phase 17.5: URL UX 升级 (D1-D5, 字段+反馈+预览+错误处理+后端扩展)"
git push
```

---

## §3 Phase 17.6 — JWT WS 安全升级 + UX 工程债清 (0.5-1 周)

### 3.1 任务 P0-1: JWT WebSocket 安全升级

#### 真根因 (advisor 前面记的)

WebSocket 鉴权当前用 `wss://stratum.uex.hk/ws?token=<JWT>` URL query 模式. token 被 nginx access log / Cloudflare log / 浏览器 history 真持久化记录, 引流后 100+ 用户 = 100+ token 在日志里泄露.

#### 修复方案 (选 1)

**方案 A**: Sec-WebSocket-Protocol header
**方案 B**: 短期 ticket

advisor 推荐方案 A (符合 WebSocket 标准, 工程量小):

**后端改 (stratum/api/routers/ws.py 真修):**
```python
from fastapi import WebSocket, status
from stratum.auth import verify_jwt

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    # 从 Sec-WebSocket-Protocol header 取 token
    protocols = ws.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in protocols.split(",")]
    
    if len(parts) != 2 or parts[0] != "bearer":
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    token = parts[1]
    
    try:
        user_id = verify_jwt(token)
    except Exception:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # accept 时指定 subprotocol 真返
    await ws.accept(subprotocol="bearer")
    
    # ... 原 ws 业务逻辑
```

**前端改 (src/lib/ws-client.ts 真修):**
```typescript
connect(token: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    
    // 不再 URL 带 token, 走 Sec-WebSocket-Protocol
    const wsUrl = `wss://${window.location.host}/ws`;
    this.ws = new WebSocket(wsUrl, ["bearer", token]);
    
    // ... 原 onopen / onmessage / onclose 不变
}
```

#### 验证

- 浏览器 dev tools Network → WS 连接 → 看 request header 真 Sec-WebSocket-Protocol: bearer, <token>
- URL 真无 token (nginx 日志 / Cloudflare 不再记 token)
- 连接 真 accept + 业务 event 真触发 (toast 真出现)

### 3.2 任务 P0-2: 上传文件进度反馈

```
~/projects/stratum/stratum-web/src/components/UploadButton.tsx (或对应组件)

加:
- 上传中 loading + 进度条 (XHR.upload.onprogress)
- 上传成功 toast "已入库, 1 个 substrate 真添加"
- 上传失败 toast "失败: [真错误]"
```

### 3.3 任务 P0-3: User onboarding 引导

```
src/components/OnboardingTour.tsx 新建:
- 首次登录用户显示引导 tour (4-5 步)
  1. "欢迎! Stratum 帮你把英文资料消化成自己的知识"
  2. "点这里上传文件" (指向 /documents 上传按钮)
  3. "点这里抓取网页 URL" (指向 /documents 输入URL按钮)
  4. "点这里跑 AI Agent (翻译/摘要/问答)" (指向 /ai)
  5. "你的笔记 / 高亮 / 视图 见 sidebar" 
- localStorage 存 onboarding_completed flag
- /settings 加 "重看引导" 按钮
```

### 3.4 Gate

```bash
# 后端 WS
pytest tests/ -k "ws_auth" -v

# 前端
pnpm type-check && pnpm lint && pnpm build && pnpm test --run

# 真测试 WS:
# - Wiki 浏览器 / dev tools Network → WS → 看 header 真改
# - 创建 note 真 toast 出现 (changefeed event 真广播)

# 真测试 onboarding:
# - 用 incognito 注册新账号 → 真看到 tour
# - localStorage 删 onboarding_completed → 重新 tour

git commit -m "Phase 17.6: JWT WS Sec-WebSocket-Protocol 安全 + 上传进度 + onboarding 引导"
git push
```

TECHNICAL_DEBT.md 移除:
- ✅ "JWT WS URL 泄露" (已修)
保留:
- 🔴 "DNS rebinding TOCTOU" (等 obase v0.10.1 + oprim v2.29.1)

---

## §4 Phase 17.7 — RSS + ResearcherAgent ship (2-3 周)

### 4.1 任务 R-1: searxng Docker 部署

```yaml
# ~/projects/stratum/deploy/docker-compose.yml
services:
  searxng:
    image: searxng/searxng:latest
    container_name: stratum-searxng
    restart: unless-stopped
    ports:
      - "127.0.0.1:8888:8080"
    volumes:
      - ./searxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:8888/
    networks:
      - stratum-net
```

```yaml
# searxng/settings.yml (最小配置)
use_default_settings: true
general:
  instance_name: "Stratum SearxNG"
search:
  formats:
    - html
    - json
server:
  secret_key: "<生成 32 字节 random>"
  limiter: false  # alpha 期不限速
engines:
  - name: google
    disabled: false
  - name: duckduckgo
    disabled: false
  - name: bing
    disabled: true  # 国内不可用
```

启动验证:
```bash
docker compose up -d searxng
curl "http://localhost:8888/search?q=test&format=json" | jq
# 期待真返结果
```

### 4.2 任务 R-2: oprim.external.searxng_client 真激活

主库已 ship 18 元素含 searxng_client? 核查:
```python
docker exec stratum-sl python3 -c "
from oprim import external
print(dir(external))
"
# 看是否真有 searxng_client
```

如果有 → 走 Stratum 端 wire
如果没 → R-1 报告 oprim 经理人补 (跟 dns_pinned_transport 同模式)

### 4.3 任务 R-3: FeedTrackerAgent (Stratum 端 omodul 引用 + 服务层 wire)

#### 前置: omodul 经理人新增 FeedTrackerAgent

advisor 假设主库已 ship (按 Wiki 之前 "18 元素入主库 + Owner review 通过" 含). CC 核查:
```python
docker exec stratum-sl python3 -c "
from omodul.knowledge.agents.builtin.feed_tracker import FeedTrackerAgent
print('OK')
"
```

如果 omodul 端 FeedTrackerAgent 还没真新增 → R-1 报告, advisor 出 omodul 经理人对接信. CC **不擅自在 Stratum 端实施 Agent** (Agent 归 omodul).

#### Stratum 端 wire (假设 omodul ship 后)

```python
# src/stratum/api/routers/agents.py
from omodul.knowledge.agents.builtin.feed_tracker import FeedTrackerAgent

AGENT_REGISTRY["feed_tracker"] = (FeedTrackerAgent, FeedTrackerConfig, FeedTrackerInput)
```

```python
# src/stratum/api/routers/feeds.py 新建
from fastapi import APIRouter, Depends
from sqlalchemy import ... # 或 duckdb 直查

router = APIRouter(prefix="/api/v1/feeds")

@router.post("")
async def subscribe_feed(req: FeedSubscribeRequest, user=Depends(get_current_user)):
    """订阅新 RSS feed"""
    # 1. oprim.detect_feed_url_from_homepage 真发现 feed URL (如果用户输的是首页)
    # 2. oprim.fetch_rss_feed 真拉一次 (验证可用)
    # 3. 写 feed_subscriptions 表
    # 4. emit changefeed event
    
@router.get("")
async def list_feeds(user=Depends(get_current_user)):
    """列用户订阅"""
    
@router.delete("/{feed_id}")
async def unsubscribe(feed_id: str, user=Depends(get_current_user)):
    """取消订阅"""

@router.put("/{feed_id}")
async def update_feed(feed_id: str, req: FeedUpdateRequest, user=Depends(get_current_user)):
    """改频率 / 暂停"""

@router.post("/{feed_id}/check_now")
async def check_now(feed_id: str, user=Depends(get_current_user)):
    """立即拉一次"""
```

DB migration:
```sql
-- migrations/021_feed_subscriptions.sql
CREATE TABLE feed_subscriptions (
  id UUID PRIMARY KEY DEFAULT uuidv7(),
  user_id TEXT NOT NULL,
  feed_url TEXT NOT NULL,
  feed_title TEXT,
  feed_description TEXT,
  frequency_hours INTEGER DEFAULT 6,
  last_check_at TIMESTAMP,
  last_etag TEXT,
  last_modified TEXT,
  last_entries_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',  -- active / paused / error
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, feed_url)
);
CREATE INDEX idx_feed_subs_user ON feed_subscriptions(user_id);
CREATE INDEX idx_feed_subs_status ON feed_subscriptions(status) WHERE status = 'active';
```

scheduler 加 builtin job:
```python
# omodul.knowledge.scheduler.builtin_jobs (跟 omodul 经理人协调加)
JOB_FEED_TRACKER = {
    "name": "feed_tracker_hourly",
    "agent": "feed_tracker",
    "cron": "0 * * * *",  # 每小时
    "enabled": True,
    "params": {},
}
```

### 4.4 任务 R-4: ResearcherAgent (Stratum 端 omodul 引用 + 服务层 wire)

同 R-3, omodul 端 ResearcherAgent 主库 ship 后 Stratum 端 wire.

```python
# src/stratum/api/routers/agents.py
from omodul.knowledge.agents.builtin.researcher import ResearcherAgent
AGENT_REGISTRY["researcher"] = (ResearcherAgent, ResearcherConfig, ResearcherInput)
```

Stratum 端不新增 endpoint, 走通用 `/api/v1/agents/researcher/run`.

### 4.5 任务 R-5: 前端 wire

#### 4.5.1 /documents 加 "订阅 RSS" 按钮

```tsx
<FeedSubscribeDialog />  // 新建
```

UI:
- 输入 URL (placeholder "网站首页或 RSS feed URL")
- 自动 detect_feed_url (调后端 /api/v1/feeds/discover?url=...)
- 列出 detected feed 选择
- 频率: 每小时 / 每 6 小时 / 每天
- 订阅 → toast 真提示

#### 4.5.2 /feeds 新页 (sidebar 入口 "订阅源")

```tsx
// src/app/(app)/feeds/page.tsx
- 列用户订阅
- 每行: feed title + frequency + last_check + status
- 操作: 暂停 / 删除 / 立即拉一次
- 顶部 "添加新订阅" 按钮 (跟 /documents 同 dialog)
```

#### 4.5.3 /ai ResearcherAgent 加入 8 Agent 卡片网格

```tsx
// src/lib/agent-options.ts
AGENT_OPTIONS.push({
  value: "researcher",
  label: "Researcher (主动研究)",
  description: "输入研究主题, 自动找资料 + 总结",
  requiresParam: "query",
});
```

AgentParamsForm 加 researcher case:
```tsx
{selectedAgent === "researcher" && (
  <>
    <input placeholder="研究主题, e.g. 凯利公式 BTC 实战" />
    <input type="number" placeholder="抓取文章数 (10-50)" defaultValue={10} />
  </>
)}
```

#### 4.5.4 ResearcherAgent 真用户体验 (~ 1-3 分钟)

- 跑 ResearcherAgent 弹 progress modal (不是简单 spinner)
- WS event 真显示进度 ("正在搜索..." / "找到 15 篇" / "入库第 3 篇..." / "LLM 总结中...")
- 完成后 inline 显示总结 + 所有源 substrate links

### 4.6 Gate

```bash
# 后端测试
pytest tests/ -k "feeds or researcher" -v

# 前端
pnpm build && pnpm test:e2e --grep "phase17_7"

# 真公网验证 (Wiki):
# RSS:
# - /feeds → 添加订阅 → 输 https://feeds.feedburner.com/aalbc → 自动 detect → 真订阅
# - 等下次 cron 拉 (或点 "立即拉一次") → /documents 真出现新 substrate
# - WS event 触发 toast "已抓取 5 篇新文章"
# 
# Researcher:
# - /ai 选 Researcher 卡片 → 输 "凯利公式 BTC 实战" → 跑
# - WS progress 真显示 → 1-3 分钟完成
# - inline 真显示总结 + 10 个 substrate links

git commit -m "Phase 17.7: RSS 订阅 + ResearcherAgent ship (searxng + FeedTrackerAgent + 前端 wire)"
git push
tag phase17.7-v0.85-alpha
git push --tags
```

---

## §5 Phase 17.8 — 概念图谱 + 反向链接 + 时间线前端 (1 周)

### 5.1 任务 G-1: 概念图谱前端 (`/concepts/[id]/graph`)

```bash
pnpm add reactflow
# 或: pnpm add cytoscape
```

```tsx
// src/app/(app)/concepts/[id]/graph/page.tsx
import ReactFlow from "reactflow";

// 调后端 GET /api/v1/concepts/graph/:id
// 返: { nodes: [...], edges: [...] }
// 渲染交互式图谱 (拖拽 / 缩放 / 点节点跳转)
```

### 5.2 任务 G-2: 反向链接前端 (/notes/[id])

```tsx
// 现有 /notes/[id] page 加 sidebar 区:
<BacklinksPanel noteId={id} />

// BacklinksPanel 调 GET /api/v1/notes/:id/backlinks
// 列出 哪些 note 链接到本 note
```

### 5.3 任务 G-3: 时间线视图 (/timeline)

后端: 新 endpoint `GET /api/v1/timeline?from=&to=&medium=`
```python
# src/stratum/api/routers/timeline.py
@router.get("/api/v1/timeline")
async def get_timeline(
    from_date: datetime = Query(...),
    to_date: datetime = Query(...),
    medium: Optional[str] = None,
    user=Depends(get_current_user)
):
    """按月/周分桶, 返 substrate + note + Agent run + highlight"""
```

前端: `/timeline` 新页, sidebar 加 "时光机" 入口
- 月度日历视图 (按月分桶 substrate count)
- 点某月 → 列出当月所有 substrate / note / highlight
- 筛选 medium (全部 / PDF / webpage / note)

### 5.4 Gate

```bash
pnpm build && pnpm test:e2e --grep "phase17_8"

# 真测试:
# - /concepts/[id]/graph: 真显示节点 + 边, 可拖拽
# - /notes/[id]: sidebar 显示 backlinks
# - /timeline: 按月真渲染

git commit -m "Phase 17.8: 概念图谱前端 + 反向链接 + 时间线视图"
git push
```

---

## §6 Phase 17.9 — Web Responsive 移动端优化 (0.5 周)

### 6.1 真问题

当前 stratum-web mobile (< 768px) 体验差:
- sidebar 不收, 占屏 70% 真挤
- 卡片网格 desktop 2 列, mobile 仍 2 列, 真窄
- button / input 触屏 < 44px

### 6.2 任务 M-1: sidebar 改汉堡菜单 (mobile)

```tsx
// src/components/layout/Sidebar.tsx
import { useMediaQuery } from "@/hooks/use-media-query";

const isMobile = useMediaQuery("(max-width: 768px)");

if (isMobile) {
  return <MobileHamburgerSidebar />;  // 真汉堡 + drawer
}

return <DesktopSidebar />;  // 现有
```

### 6.3 任务 M-2: 卡片网格响应式

```tsx
// /ai page (AgentInfoCards)
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
// 真按屏宽: mobile 1 列 / tablet 2 列 / desktop 3 列
```

类似 /documents / /feeds / /timeline 全部响应式核查.

### 6.4 任务 M-3: 触屏友好

- button: `min-h-[44px]` (touch target ≥ 44px Apple HIG)
- input: 同样 `min-h-[44px]`
- font-size: ≥ 16px (mobile 避免 zoom in)

### 6.5 Gate

```bash
# Wiki 真用手机浏览器测 (或 Chrome dev tools mobile mode):
# - sidebar 真汉堡, 点开 drawer 真展开
# - /ai 卡片真 1 列
# - 按钮 真大可点
# - input 真不缩放

git commit -m "Phase 17.9: Web responsive mobile 优化 (汉堡 sidebar + 响应式网格 + 触屏)"
git push
```

---

## §7 Phase 17.10 — 引流准备 (1-2 周)

### 7.1 任务 L-1: README.md 真更新

```markdown
# Stratum — 你的 AI 知识管家

把英文资料消化成自己的知识. PDF / 网页 / RSS / 研究主题 → AI 翻译 / 摘要 / 朗读 / 插图 / 概念图谱.

## 真功能 (alpha v1.0)

### 主动获取
- 📄 上传文件 (PDF / EPUB / markdown / 图片)
- 🌐 输入 URL 抓取网页
- 🔌 浏览器扩展一键保存
- 📡 RSS / Atom 订阅跟踪
- 🔬 AI 研究员 (输入主题, 自动找 + 总结)

### AI 加工
- 🌏 英文翻译中文
- 📝 每日 / 每周 摘要
- 🎧 音频朗读 (edge-tts)
- 🖼️ 插图生成 (DashScope wanxiang)
- 💬 阅读伙伴 (针对你的资料库问答)

### 知识体系
- 🔍 三层融合检索 (你的资料 + hevi 专业内容 + 你的笔记)
- 🧠 概念图谱可视化
- 🔗 反向链接 / wikilink
- ⏰ 时光机时间线

### 隐私
- alpha 期: 数据存我们服务器 (你删 = 真删)
- 引流后 Pro tier 可选: 用户网盘 (Google Drive / OneDrive) 同步

## 立即试用

https://stratum.uex.hk (免费 + Plus ¥29/月)

## 跟 obsidian / notion 真区别

| 功能 | obsidian | notion | Stratum |
|---|---|---|---|
| AI 翻译 | ❌ | ❌ | ✅ |
| AI 摘要 / 总结 | 🟡 插件 | 🟡 AI 加 | ✅ |
| AI 主动研究 | ❌ | ❌ | ✅ |
| 音频朗读 | ❌ | ❌ | ✅ |
| 三层融合检索 | ❌ | ❌ | ✅ (含 hevi 专业内容) |
| 双链 + 图谱 | ✅ | 🟡 | ✅ |
| 数据所有权 | ✅ 本地 | ❌ 云 | 🟡 短期云, 长期 Pro 网盘 |

## 技术栈

Next.js 16 + FastAPI + DuckDB + LanceDB + Tantivy + obase/oprim/oskill/omodul (3O paradigm)

## 反馈

[FeedbackWidget 内嵌] 或 wiki@helios-plat.com
```

### 7.2 任务 L-2: docs/USER_GUIDE.md

```markdown
# Stratum 用户指南 (alpha v1.0)

## 5 分钟上手

### Step 1: 注册
...

### Step 2: 上传第一份资料
...

### Step 3: 跑第一个 AI Agent
...

### Step 4: 真感受三层融合检索
...

### Step 5: 进阶 — RSS 订阅 / Researcher
...
```

3-5 KB markdown, 含真截图 (优先), 真演示 5 分钟用户从注册到看到 AI 结果完整流程.

### 7.3 任务 L-3: Landing page review

`/` 首页 (Phase 14 时实施过) 真升级:
- Hero: "把英文资料消化成自己的知识"
- 3 段真用户场景 + GIF/截图
- "立即试用" → 注册
- 真 reviews / 真截图 / 真 demo
- 不要"AI-powered" 这种空话, 真说 Stratum 干什么

### 7.4 任务 L-4: FeedbackWidget 真测试

`src/components/FeedbackWidget.tsx` (Phase 14 已实施) 真用户视角测试:
- 真点 → 真弹反馈 form
- 真发送 → 真 admin 收到
- admin 后台 `/admin/feedback` 真看到

### 7.5 任务 L-5: 引流渠道决策 (Wiki 决策)

advisor 推荐:
1. **Twitter (@wiki_builds)**: Build in Public alpha launch tweet, 真讲 Stratum 解决什么问题. ~ 1 推 + DM 引流
2. **YouTube**: "Builder-Skeptic" 系列首发视频 (你之前规划), 15-20 min 讲 Stratum 真功能 + 跟 obsidian/notion 真对比
3. **少 数 V (3-5 个)**: 量化 / 投资 / 阅读 / 知识管理领域真用户, 1-on-1 推送, 邀请试用 + 反馈
4. **暂不**: 微信公众号 / 小红书 (备案未完成, ADR-025 推后)

每渠道 advisor 出真草案 (Wiki review):
- Twitter tweet (140 字内 + 配图/视频)
- YouTube 脚本 (Wiki 自己拍)
- DM 模板 (1 对 1 推送, 个性化)

### 7.6 Gate

```bash
# 文档真存档:
git add README.md docs/USER_GUIDE.md
git commit -m "Phase 17.10: README + USER_GUIDE + Landing review + FeedbackWidget 真测试"
git push

# 真最后一次全功能 e2e (引流前)
pnpm test:e2e --grep "alpha_v1_release"

# Wiki 真用户视角 最终验证:
# - 注册 → 上传 → AI Agent → 搜索 → URL 抓取 → 浏览器扩展 → RSS 订阅 → Researcher → 真都跑通
# - 没 bug 阻塞用户流程

tag alpha-v1.0
git push --tags
```

---

## §8 真引流执行 (Phase 17.10 完工后)

### 8.1 真 ship 前最后 checklist

- [ ] 全 Phase 17.5-17.9 完工
- [ ] 主库 obase v0.10.1 + oprim v2.29.1 修 dns_pinned HTTPS bug ship (跨经理人)
- [ ] Stratum 端 url_fetch_ssrf_safe 真切换 + TECHNICAL_DEBT DNS rebinding 移除
- [ ] PR #2 真 merge 到 main (phase14/backend-saas 一直没并主线)
- [ ] R6-6 PG volume 真删 (2026-06-08 后)
- [ ] alpha v1.0 tag 推 GitHub
- [ ] README + USER_GUIDE + Landing 真上 prod
- [ ] FeedbackWidget 真测试通过
- [ ] Twitter / YouTube 草案 Wiki review 通过

### 8.2 引流真执行 (Wiki 主导)

advisor 不能代 Wiki 发 Twitter / 拍 YouTube. advisor 出草案 + 跟踪用户反馈.

### 8.3 引流后真做

按 SPEC v0.7 §16 路线图:
- Phase 18 hevi 内容流水线 (3-4 周)
- Phase 19 Stripe 付费 (2-3 周)
- Phase 20 PWA 移动端 (1-2 周)
- Phase 22-24 (3-6 月内)

---

## §9 时间表 (真预算)

| Phase | 内容 | 工程量 | 完工 deadline (从 2026-06-04 起) |
|---|---|---|---|
| 17.5 | URL UX 升级 | 1 周 | 2026-06-11 |
| 17.6 | JWT WS + UX 工程债 | 0.5-1 周 | 2026-06-18 |
| 17.7 | RSS + Researcher | 2-3 周 | 2026-07-09 (假设跨经理人 omodul 协调 1 周) |
| 17.8 | 概念图谱 + 反向链接 + 时间线 | 1 周 | 2026-07-16 |
| 17.9 | Web responsive | 0.5 周 | 2026-07-19 |
| 17.10 | 引流准备 | 1-2 周 | 2026-08-02 |
| **真引流** | Twitter / YouTube / DM | — | **2026-08-05 ± 1 周** |

跨经理人 obase/oprim dns_pinned 修复 2 周内完工, 不阻塞引流 (引流前最后 checklist 时切换).

---

## §10 异常处理 (R-1)

立即停 + 报告 advisor:
- 任何 test fail / build fail
- 任何 omodul / oskill / oprim / obase 端元素 真不存在 (跨经理人 R-1)
- 任何前端 prod build pass 但浏览器真坏 (P0-5 教训)
- 任何 Wiki 浏览器真测试反馈卡点

非阻塞:
- alpha 期某 Agent 慢 / UI 简陋 (引流后看用户反馈)
- mobile 边角 UX (Phase 17.9 兜底)

---

## §11 跨经理人协调清单 (本指令书涉及)

| Phase | 跨经理人项 | 已开始? | 状态 |
|---|---|---|---|
| 17.6 | (无) | — | Stratum 端自己改 |
| 17.7 | omodul FeedTrackerAgent / ResearcherAgent 新增 | 待 advisor 出对接信 | advisor 等 Wiki 同意启动 |
| 17.7 | searxng Docker 配置 | Stratum 端 | 自己做 |
| 17.7 | oprim.external.searxng_client 主库验证 | CC 核查 | 看 18 元素是否含 |
| (跨) | obase v0.10.1 + oprim v2.29.1 dns_pinned HTTPS 修 | advisor 对接信已发 (上轮) | 等 ~ 2 周 |

---

## §12 完工标志 (alpha v1.0 ship)

```
✅ Phase 17.5-17.10 全完工
✅ omodul FeedTrackerAgent + ResearcherAgent ship + Stratum wire
✅ obase v0.10.1 + oprim v2.29.1 ship + Stratum 端 url_fetch_ssrf_safe 切换
✅ 7 Track 4 文档 + landing + FeedbackWidget 真测试通过
✅ tag alpha-v1.0
✅ Wiki 真用户视角全功能跑通
✅ TECHNICAL_DEBT 引流前清单全清 (JWT WS + DNS rebinding)
✅ Twitter / YouTube / DM 草案 Wiki review 通过

→ 真引流执行 (Wiki 主导)
```

---

**End of Phase 17.5-17.10 完整指令书**

— Stratum advisor Claude
2026-06-04

预算: ~ 6-9 周到引流 (2026-08-05 ± 1 周 真 ship)
