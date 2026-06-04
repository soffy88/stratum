# PHASE_11C_IMPLEMENTATION_INSTRUCTIONS_v0.1.md

**任务**: Stratum Phase 11C — Obsidian 工作流 + QMD 检索增强 (9 项)
**执行者**: CC FULL AUTO
**工程量**: 3 周 (15-22 天)
**SPEC 依据**:
- Obsidian 工作流文章 (PARA / MOC / 周期 / 任务 / 灵感 / 模板)
- QMD 文章 (Reranker / Query expansion / 本地优先)
- Phase 11C #8 已 sign-off (本地 embedding fallback) — 本指令书剩 8 项
- 4O v0.3 PATCH §H (新加, Phase 11C 增强)

**前置完工**:
- ✅ Phase 1/1.5/10/2/4/11A/13/11B 完工 (37/38, TTS v1.1)
- ✅ STRATUM_API_v1.md Gate 通过
- ✅ Phase 11C #8 本地 embedding fallback 完工 (qwen3-embedding:0.6b)
- ✅ 3 API key 齐 (Wiki .env 已填 DASHSCOPE + DEEPSEEK + ANTHROPIC)

**预期产物**:
- oprim 2.8.1 → 2.9.0
- oskill 2.9.0 → 2.10.0
- omodul 1.8.0 → 1.9.0
- stratum-extension v0.1.0 → v0.2.0
- 新增 1 个独立项目 stratum-cli (一键装 CLI)
- 4 个新 builtin view (PARA)
- 2 个新 builtin scheduled job (周记 / 月记)
- 1 个新实体 task + parser + view + MCP tool
- 浏览器扩展全局快捷键
- note 模板系统 (~/.stratum/templates/)
- Reranker (qwen3-reranker via Ollama)
- Query expansion (小 LLM 多变体)

---

## §0 FULL AUTO 规则

### R-1: 失败不静默
任何 skill / Agent / Block 失败 → 明确 error_message, 不假装成功

### R-2: SPEC 是真理源
- Phase 11C 是 v1.0 → v1.1 过渡, 不破坏 v1.0 已有 API 契约
- Obsidian 整合不抄概念语义, 用 Stratum 原生模型 (substrate / derivative / note)
- QMD 增强复用 Phase 1.5 / 11C-1 已有 embedding 设施

### R-3: 真实示例强制
- 每个 Wave 完工要跑真实 demo
- 用 Phase 1-13 已有 substrate 数据
- 不脑补字段 / 不假数据

### R-4: 严格范围
✅ 允许:
- 9 个 task 实施 (见 §1)
- 新建 omodul.knowledge.tasks / omodul.knowledge.templates
- 新建 oprim.reranker / oprim.query (expansion)
- 修订 hybrid_search 集成 reranker + expansion (向后兼容, 默认关闭)
- 浏览器扩展加 keyboard shortcut + popup
- 新建独立项目 stratum-cli (init 脚本)

❌ 禁止:
- 改 Phase 1-13 + Phase 11B 完工代码 (除非加可选参数, 默认行为不变)
- 改 STRATUM_API_v1.md (Phase 11D 一次性更新到 v1.1)
- 改 4 OSS 包 ABI (oprim/oskill/omodul/obase) 接口签名
- 用户自定义 Agent (Phase 14+)
- 多用户 / 多租户

### R-5: namespace 隔离
- 不动: oprim/storage / changefeed / push / translate
- 不动: oskill/sync / oskill/knowledge/ingest_substrate (除非必要的可选参数)
- 不动: omodul/sync / omodul/knowledge/agents (除非新加 builtin job)

只动 + 新建:
- 新建 omodul/knowledge/tasks/* (#3)
- 新建 omodul/knowledge/templates/* (#5)
- 新建 oprim/reranker/* (#6)
- 新建 oprim/query/* (#7)
- 新建 stratum-extension popup.js + shortcut (#4)
- 新建 stratum-cli/* 独立项目 (#8)
- 修订 oskill/knowledge/hybrid_search 加 rerank + expand 可选参数 (#6, #7)
- 修订 omodul/knowledge/scheduler/builtin_jobs.py 加 2 个 builtin (#2)
- 修订 omodul/knowledge/views/presets/ 加 4 个 yaml (#1)
- migration: tasks 表 / templates 表

### R-6: 破坏性操作必须 Wiki sign-off
- 不删除任何 OS 文件 / DB / ollama model / docker container
- 不重命名既有 module / function
- 不破坏 SPEC v0.6 / API v1.0 契约

---

## §1 9 项 (8 剩, #8 已完工)

| # | 项 | 工程量 | 依赖 |
|---|---|---|---|
| 1 | PARA + MOC builtin view | 0.5 天 | Phase 13 view 系统 |
| 2 | 周期笔记 (weekly / monthly review job) | 1-2 天 | Phase 11A scheduler |
| 3 | 任务管理 (task 实体 + parser + view + MCP) | 2-3 天 | DuckDB + omodul |
| 4 | 灵感收集箱 (扩展全局快捷键 + popup) | 1-2 天 | Phase 4 浏览器扩展 |
| 5 | note 模板系统 | 2-3 天 | omodul + DuckDB |
| 6 | Reranker (qwen3-reranker via Ollama) | 2-3 天 | oprim + hybrid_search |
| 7 | Query expansion (小 LLM 多变体) | 2-3 天 | oprim + hybrid_search |
| ~~8~~ | ~~本地 embedding fallback~~ | ✅ 已完工 | - |
| 9 | stratum-init 一键装 CLI | 2-3 天 | 独立项目 |

---

## §2 Wave 0 — 准入 + 调研 (0.5 天)

### 2.1 baseline 验证

```bash
# oprim / oskill / omodul 版本
python3 -c "import oprim, oskill, omodul; print(oprim.__version__, oskill.__version__, omodul.__version__)"
# 期待: 2.8.1 / 2.9.0 / 1.8.0

# Phase 11C #8 embedding fallback OK?
EMBEDDING_PROVIDER=qwen3_local python3 -c "
from oprim.embedding import embed_text
v = embed_text(['测试'], provider='qwen3_local', dim=1024)
print(f'qwen3_local OK: {len(v[0])} dim')
"

# DashScope 3 keys 配置 OK?
cat ~/.config/keys/.env | grep -E "DASHSCOPE|DEEPSEEK|ANTHROPIC" | wc -l
# 期待: 3

# Ollama 可用模型
ollama list
# 期待至少: qwen3:14b / qwen3-embedding:0.6b
```

### 2.2 调研 (CC 自查)

1. **qwen3-reranker** ollama 上是否有? 维度 / 接口?
   ```bash
   ollama search qwen3-reranker
   ollama pull qwen3-reranker:latest (如有)
   ```
   如无 → fallback bge-reranker-v2-m3 (Hugging Face → transformers 本地)

2. **Query expansion 小模型**: 当前 qwen3:14b 太大, 用啥?
   - 候选 1: qwen3:7b (~4G, 适合 expansion)
   - 候选 2: qwen3:0.5b (~0.5G, 超快)
   选 0.5b (expansion 不需要长上下文 / 复杂推理, 速度优先)

3. **stratum-cli 框架**: 用 Python typer / click?
   - typer (推荐, 现代化 + FastAPI 风格)

### 2.3 Wave 0 完成报告
```
Wave 0 ✅
- baseline: oprim 2.8.1 / oskill 2.9.0 / omodul 1.8.0 / embedding fallback OK
- ollama models: <list>
- Reranker 选型: <qwen3-reranker / bge-reranker-v2-m3>
- Expansion 选型: <qwen3:0.5b / qwen3:7b>
- stratum-cli 框架: typer
```

---

## §3 Wave 1 — PARA View (0.5 天) [#1]

### 3.1 新增 4 个 builtin view yaml

`omodul/omodul/knowledge/views/presets/`:

**projects.yaml** (PARA Projects)
```yaml
name: "项目"
description: "正在推进、有终点的事 (PARA Projects)"
default_filter:
  medium: [note]
  tag: [project]
default_llm:
  provider: deepseek
  model: deepseek-chat
default_system_prompt: "你是项目管理助手, 关注进度和待办."
icon: "🎯"
is_default: false
```

**areas.yaml** (PARA Areas)
```yaml
name: "领域"
description: "长期负责、无终点 (PARA Areas)"
default_filter:
  medium: [note]
  tag: [area]
default_llm:
  provider: deepseek
  model: deepseek-chat
icon: "🌳"
is_default: false
```

**resources.yaml** (PARA Resources)
```yaml
name: "资源"
description: "兴趣素材库 (PARA Resources)"
default_filter:
  medium: [paper, article, book, web]
  tag: [resource]
icon: "📚"
is_default: false
```

**archives.yaml** (PARA Archives)
```yaml
name: "归档"
description: "已结束 / 不活跃 (PARA Archives)"
default_filter:
  tag: [archived]
icon: "📦"
is_default: false
```

### 3.2 install_builtin_views 自动加载

`omodul/knowledge/views/preset_loader.py` 既有逻辑自动覆盖新增 yaml.

### 3.3 Wave 1 完成报告
```
Wave 1 ✅ (#1 PARA view)
- 4 个 yaml 新增 (projects / areas / resources / archives)
- install_builtin_views 5 → 9 view
- 测试: omodul views 全量回归 0 regressions
- commit: <hash>
```

---

## §4 Wave 2 — 周期笔记 (1-2 天) [#2]

### 4.1 新增 2 个 builtin job

`omodul/knowledge/scheduler/builtin_jobs.py`:

```python
{
    "name": "weekly_review",
    "description": "每周日 9 点生成本周回顾",
    "cron_expression": "0 9 * * 0",
    "agent_name": "daily_digest",  # 复用 daily_digest, 改 params
    "agent_params": {
        "time_range": "last_7_days",
        "title_prefix": "周回顾",
        "include": ["new_substrates", "agent_runs", "completed_tasks"],
    },
    "enabled": False,  # 默认关 (Wiki 自己开)
    "is_builtin": True,
    "timezone": "Asia/Shanghai",
    "notify_on_completion": True,
    "notify_on_failure": True,
    "max_runtime_seconds": 1800,
},
{
    "name": "monthly_review",
    "description": "每月 1 号 9 点生成上月回顾",
    "cron_expression": "0 9 1 * *",
    "agent_name": "daily_digest",
    "agent_params": {
        "time_range": "last_30_days",
        "title_prefix": "月回顾",
        "include": ["new_substrates", "agent_runs", "completed_tasks", "new_concepts"],
    },
    "enabled": False,
    "is_builtin": True,
    "timezone": "Asia/Shanghai",
    "notify_on_completion": True,
    "notify_on_failure": True,
    "max_runtime_seconds": 3600,
},
```

### 4.2 daily_digest Agent 改造支持 time_range / title_prefix

`omodul/knowledge/agents/builtin/daily_digest.py`:
- params 加 `time_range: str = "last_24_hours"` (兼容旧默认)
- 改 list_substrates_since(...) 调用按 time_range 解析
- output 加 `time_range`, `title` 字段

### 4.3 Wave 2 完成报告
```
Wave 2 ✅ (#2 周期笔记)
- 2 个 builtin job 新增 (weekly_review / monthly_review)
- daily_digest Agent 支持 time_range params
- 测试: 13/13 (含 weekly + monthly path)
- commit: <hash>
```

---

## §5 Wave 3 — 任务管理 (2-3 天) [#3]

### 5.1 数据模型

migration: `migrations/010_v1_9_tasks.sql`

```sql
CREATE TABLE IF NOT EXISTS task (
    id          VARCHAR PRIMARY KEY,        -- ULID
    user_id     VARCHAR NOT NULL,
    note_id     VARCHAR,                    -- 来源 note (parsed from)
    text        VARCHAR NOT NULL,           -- 任务文本
    completed   BOOLEAN DEFAULT FALSE,
    due_date    TIMESTAMP,                  -- 📅 截止
    scheduled_date TIMESTAMP,                -- ⏳ 计划
    priority    INTEGER DEFAULT 0,           -- 0=none, 1=low, 2=med, 3=high
    tags        VARCHAR DEFAULT '[]',        -- JSON array
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    meta_json   VARCHAR DEFAULT '{}'
);

CREATE INDEX idx_task_user_completed ON task(user_id, completed);
CREATE INDEX idx_task_due ON task(user_id, due_date) WHERE completed = FALSE;
```

### 5.2 Task Parser

`omodul/knowledge/tasks/parser.py`:

```python
import re
from datetime import datetime

# 匹配 Markdown 任务行:
# - [ ] 写周报 📅 2026-05-22
# - [x] 完成
TASK_RE = re.compile(r'^[\s]*-\s+\[(\s|x|X)\]\s+(.+?)(?:\s+📅\s*(\d{4}-\d{2}-\d{2}))?(?:\s+⏳\s*(\d{4}-\d{2}-\d{2}))?(?:\s+🏷\s*\[(.+?)\])?\s*$', re.MULTILINE)

def parse_tasks_from_note(note_content: str) -> list[dict]:
    """从 note Markdown 提取 - [ ] 任务"""
    tasks = []
    for match in TASK_RE.finditer(note_content):
        completed_marker, text, due, scheduled, tags = match.groups()
        tasks.append({
            "text": text.strip(),
            "completed": completed_marker.lower() == "x",
            "due_date": due,           # ISO string 或 None
            "scheduled_date": scheduled,
            "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
        })
    return tasks
```

### 5.3 Task CRUD

`omodul/knowledge/tasks/crud.py`:
- create_task / get_task / list_tasks (with filters: completed / due_before / overdue / tag)
- update_task / mark_completed / delete_task
- sync_from_note(note_id) — 重新解析 note 并 upsert tasks

### 5.4 Hook: note 写入时自动 sync tasks

`omodul/knowledge/notes/create_note.py` (如存在) 或 ingest_substrate 加 note 路径:
- 检测 note content 含 `- [ ]` → 调 sync_from_note(note_id)

### 5.5 MCP tool 新增

`omodul/knowledge/start_mcp_server.py`:

```python
@mcp_tool(name="stratum.list_tasks")
async def list_tasks_tool(
    completed: bool = False,
    due_before: str | None = None,  # ISO date
    overdue: bool = False,
    tag: str | None = None,
    limit: int = 20,
) -> dict:
    user_id = get_current_user_id()
    tasks = await list_tasks(user_id, completed=completed, ...)
    return {"tasks": tasks, "count": len(tasks)}


@mcp_tool(name="stratum.mark_task_completed")
async def mark_task_tool(task_id: str) -> dict:
    await mark_completed(task_id)
    return {"success": True}
```

### 5.6 Wave 3 完成报告
```
Wave 3 ✅ (#3 任务管理)
- task 表 + migration 010
- parser: 解析 - [ ] / 📅 due / ⏳ scheduled / 🏷 tags
- CRUD: create / list (5 filter) / update / mark_completed
- note hook: 自动 sync tasks
- 2 MCP tool: list_tasks / mark_task_completed
- 端到端 demo: 创建 note → 提取 3 任务 → list_tasks → mark_completed → 状态更新
- 测试: 25+ tests
- commit: <hash>
```

---

## §6 Wave 4 — 灵感收集箱 (1-2 天) [#4]

### 6.1 浏览器扩展加 popup

`stratum-extension/popup.html` (新建):
- 简洁 input box (1 行文本)
- Enter 提交 → POST `/api/v1/browser-extension/ingest`
- 默认 tags=["inbox"], create_note=False (直接作 substrate)
- 提交后自动关闭 popup

### 6.2 manifest v3 加 commands

`stratum-extension/manifest.json`:

```json
"commands": {
  "_execute_action": {
    "suggested_key": {
      "default": "Ctrl+Shift+I",
      "mac": "Command+Shift+I"
    },
    "description": "Stratum 快速捕捉"
  }
}
```

### 6.3 popup.js (新建)

```javascript
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('capture-input');
  input.focus();
  
  input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      const text = input.value.trim();
      if (!text) return;
      
      const token = await chrome.storage.local.get('stratum_token');
      
      const response = await fetch('http://localhost:14567/api/v1/browser-extension/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Stratum-Token': token.stratum_token,
        },
        body: JSON.stringify({
          url: 'stratum://inbox',
          title: text.substring(0, 80),
          selection_text: text,
          tags: ['inbox', 'capture'],
          create_note: false,
        }),
      });
      
      if (response.ok) {
        window.close();
      } else {
        alert('保存失败: ' + response.status);
      }
    }
  });
});
```

### 6.4 Wave 4 完成报告
```
Wave 4 ✅ (#4 灵感收集箱)
- stratum-extension v0.1.0 → v0.2.0
- 全局快捷键 Ctrl+Shift+I 触发 popup
- popup input box → POST ingest with tag=[inbox, capture]
- 端到端 demo: 按快捷键 → 输入 "今天的想法" → 回车 → substrate 落库 → MCP search 命中
- commit: <hash>
```

---

## §7 Wave 5 — note 模板系统 (2-3 天) [#5]

### 7.1 数据模型

migration: `migrations/011_v1_9_templates.sql`

```sql
CREATE TABLE IF NOT EXISTS note_template (
    id          VARCHAR PRIMARY KEY,
    user_id     VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,
    description VARCHAR,
    content     VARCHAR NOT NULL,           -- Markdown 模板 (含变量)
    variables   VARCHAR DEFAULT '{}',       -- JSON: {date: 'auto', custom: 'prompt'}
    icon        VARCHAR,
    is_builtin  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7.2 4 个 builtin 模板

`omodul/knowledge/templates/presets/`:

**daily_note.yaml**
```yaml
name: "日记"
description: "每日笔记模板"
icon: "📅"
content: |
  # {{date}} 日记
  
  > 今天是 {{weekday}}
  
  ## 今天发生了什么
  
  ## 今天学到了什么
  
  ## 明天要做什么
  - [ ] 
variables:
  date: auto
  weekday: auto
```

**book_note.yaml**
```yaml
name: "读书笔记"
description: "读书笔记模板"
icon: "📖"
content: |
  ---
  tags: [book]
  book_title: {{book_title}}
  author: {{author}}
  rating: 
  finished_date: {{date}}
  ---
  
  # {{book_title}}
  
  ## 一句话总结
  
  ## 核心观点
  
  ## 启发与行动
  
  ## 金句摘录
variables:
  date: auto
  book_title: prompt
  author: prompt
```

**meeting_note.yaml** / **project_note.yaml**: 类似结构.

### 7.3 模板渲染

`omodul/knowledge/templates/renderer.py`:

```python
from datetime import datetime
import re

def render_template(template: dict, user_inputs: dict) -> str:
    """渲染模板, auto 变量自动填, prompt 变量取 user_inputs"""
    content = template["content"]
    vars = template.get("variables", {})
    
    auto_values = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()],
        "datetime": datetime.now().isoformat(),
    }
    
    for var, source in vars.items():
        placeholder = f"{{{{{var}}}}}"
        if source == "auto":
            value = auto_values.get(var, "")
        elif source == "prompt":
            value = user_inputs.get(var, "")
        else:
            value = source  # 固定值
        content = content.replace(placeholder, value)
    
    return content
```

### 7.4 CRUD + MCP tool

```python
@mcp_tool(name="stratum.list_templates")
async def list_templates_tool() -> dict: ...

@mcp_tool(name="stratum.create_note_from_template")
async def create_note_from_template_tool(
    template_id: str,
    user_inputs: dict = None,  # {book_title: "深度工作", author: "..."}
) -> dict:
    """渲染模板 + 创建 note"""
    ...
```

### 7.5 Wave 5 完成报告
```
Wave 5 ✅ (#5 note 模板系统)
- note_template 表 + migration 011
- 4 个 builtin 模板 (daily / book / meeting / project)
- renderer 支持 auto + prompt 变量
- 2 MCP tool: list_templates / create_note_from_template
- 端到端 demo: 选 "读书笔记" → 输入 book_title="深度工作" → 渲染 → 创建 note
- 测试: 18+ tests
- commit: <hash>
```

---

## §8 Wave 6 — Reranker (2-3 天) [#6]

### 8.1 实施

`oprim/reranker/qwen3_reranker.py`:

```python
import httpx
from typing import Protocol

class Reranker(Protocol):
    async def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[tuple[int, float]]: ...

class Qwen3Reranker:
    """Qwen3-Reranker via Ollama (本地) 或 DashScope (云)"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3-reranker:latest"):
        ...
    
    async def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        """返回 (original_index, score) 排序后"""
        # 调 Ollama /api/embeddings + cosine sim
        # 或调 dashscope reranker
        ...
```

### 8.2 hybrid_search 集成

`oskill/knowledge/hybrid_search.py`:

```python
async def hybrid_search(
    query: str,
    user_id: str,
    top_k: int = 10,
    rerank: bool = False,          # 新增, 默认关 (向后兼容)
    rerank_top_k: int | None = None,  # 重排前先取多少
    ...
) -> list[SearchResult]:
    # 既有 RRF 逻辑
    results = ...
    
    # 新增: rerank
    if rerank and len(results) > 0:
        from oprim.reranker import get_default_reranker
        reranker = get_default_reranker()
        documents = [r.highlight or r.title for r in results]
        reranked = await reranker.rerank(query, documents, top_k=top_k)
        results = [results[i] for i, _ in reranked]
    
    return results[:top_k]
```

### 8.3 Wave 6 完成报告
```
Wave 6 ✅ (#6 Reranker)
- oprim/reranker/qwen3_reranker.py 实施
- Reranker Protocol + factory
- hybrid_search 加 rerank 可选参数 (默认关)
- 端到端 demo: 同 query 开/关 rerank 对比, 准确性提升 (manual check)
- 测试: 12+ tests
- commit: <hash>
```

---

## §9 Wave 7 — Query Expansion (2-3 天) [#7]

### 9.1 实施

`oprim/query/expansion.py`:

```python
from typing import Protocol

class QueryExpander(Protocol):
    async def expand(self, query: str, num_variants: int = 3) -> list[str]: ...


class LlmQueryExpander:
    """用小 LLM 生成 query 变体"""
    
    PROMPT = """给定用户检索 query, 生成 {num_variants} 个语义相近但表述不同的变体. 
每行一个, 不要编号, 不要解释.

原 query: {query}

变体:"""
    
    def __init__(self, llm_provider: str = "qwen3_local", model: str = "qwen3:0.5b"):
        ...
    
    async def expand(self, query: str, num_variants: int = 3) -> list[str]:
        # 调 Ollama qwen3:0.5b
        # 返回 [原 query, *变体]
        ...
```

### 9.2 hybrid_search 集成

```python
async def hybrid_search(
    ...,
    expand: bool = False,        # 新增, 默认关
    expand_num_variants: int = 3,
) -> list[SearchResult]:
    # 既有 query embedding 路径
    
    # 新增: query expansion
    queries = [query]
    if expand:
        from oprim.query import get_default_expander
        expander = get_default_expander()
        queries = await expander.expand(query, num_variants=expand_num_variants)
    
    # 多 query 并行检索 + RRF 合并
    all_results = []
    for q in queries:
        results_q = await _search_single_query(q, ...)
        all_results.append(results_q)
    
    # RRF 合并 multi-query 结果
    merged = _rrf_merge(all_results)
    
    return merged[:top_k]
```

### 9.3 Wave 7 完成报告
```
Wave 7 ✅ (#7 Query Expansion)
- oprim/query/expansion.py 实施
- QueryExpander Protocol + LlmQueryExpander
- hybrid_search 加 expand 可选参数 + multi-query RRF
- 端到端 demo: query "夏普比率" → 生成 ["风险调整收益", "投资组合评估"] → 召回率提升
- 测试: 10+ tests
- commit: <hash>
```

---

## §10 Wave 8 — stratum-cli 一键装 (2-3 天) [#9]

### 10.1 新建独立项目

`~/projects/stratum-cli/`:

```
stratum-cli/
├── pyproject.toml
├── README.md
├── src/
│   └── stratum_cli/
│       ├── __init__.py
│       ├── main.py          # typer entry
│       ├── commands/
│       │   ├── init.py      # stratum init
│       │   ├── doctor.py    # stratum doctor (健康检查)
│       │   ├── ingest.py    # stratum ingest <file>
│       │   ├── search.py    # stratum search <query>
│       │   └── view.py      # stratum view list / set-default
│       └── utils/
│           ├── docker.py
│           ├── ollama.py
│           └── config.py
└── tests/
```

### 10.2 主命令 `stratum init`

```python
@app.command()
def init():
    """初始化 Stratum (一键装)"""
    typer.echo("=== Stratum 一键装 ===")
    
    # 1. 检查前置
    check_python_version()  # 3.10+
    check_docker_available()
    check_wsl2()
    
    # 2. 创建目录
    create_stratum_home()  # ~/.stratum
    create_config()        # ~/.stratum/config.yaml
    
    # 3. API key 配置
    ask_for_api_keys()     # 交互式问 DashScope / DeepSeek / Anthropic
    
    # 4. 起 docker
    docker_compose_up()
    
    # 5. ollama 拉模型
    ollama_pull_models()   # qwen3:14b / qwen3-embedding:0.6b
    
    # 6. 初始化 DB
    run_migrations()
    
    # 7. 安装 builtin (view / job / template)
    install_builtin_views()
    install_builtin_jobs()
    install_builtin_templates()
    
    # 8. 验证
    run_health_check()
    
    typer.echo("✅ Stratum 安装完成! 试试 `stratum search 'hello'`")
```

### 10.3 doctor 命令

```python
@app.command()
def doctor():
    """健康检查"""
    checks = [
        ("Python 3.10+", check_python),
        ("Docker", check_docker),
        ("Ollama", check_ollama),
        ("DashScope key", check_dashscope_key),
        ("Stratum DB", check_db),
        ("Stratum containers", check_containers),
    ]
    for name, fn in checks:
        try:
            fn()
            typer.echo(f"✅ {name}")
        except Exception as e:
            typer.echo(f"❌ {name}: {e}")
```

### 10.4 Wave 8 完成报告
```
Wave 8 ✅ (#9 stratum-cli)
- 独立项目 ~/projects/stratum-cli/ (typer 框架)
- 5 命令: init / doctor / ingest / search / view
- pip install -e . 安装到 ~/.local/bin/stratum
- 端到端 demo: 全新机器 stratum init → 全自动装完 → stratum search 跑通
- 测试: 20+ tests
- commit: <hash>
```

---

## §11 Wave 9 — Gate (0.5 天)

### 11.1 全量回归

```bash
cd ~/projects/platform
make test  # 或 pytest oprim/tests oskill/tests omodul/tests

# 期待: 4900+ tests, 0 regressions
```

### 11.2 STRATUM_API_v1.md 更新 (附 Phase 11C 增量)

主体不动 (v1.0 锁定), 附录加 Phase 11C 增量章节:

```markdown
## 附录 E: Phase 11C 增强 (v1.1 一部分)

- §E.1 PARA View (4 新 builtin view)
- §E.2 周期笔记 (2 新 builtin job)
- §E.3 任务管理 (task 表 + parser + 2 MCP tool)
- §E.4 灵感收集箱 (扩展全局快捷键)
- §E.5 note 模板系统 (4 builtin template + 2 MCP tool)
- §E.6 Reranker (hybrid_search.rerank 参数)
- §E.7 Query Expansion (hybrid_search.expand 参数)
- §E.8 stratum-cli (5 命令)
```

### 11.3 版本 bump

- oprim 2.8.1 → 2.9.0
- oskill 2.9.0 → 2.10.0
- omodul 1.8.0 → 1.9.0
- stratum-extension 0.1.0 → 0.2.0
- stratum-cli 0.1.0 (新)
- tags: oprim-2.9.0 / oskill-2.10.0 / omodul-1.9.0 / stratum-cli-0.1.0 / stratum-extension-0.2.0

### 11.4 Gate 完成报告
```
Phase 11C Gate ✅

全 9 项完工 (含 #8 本地 embedding fallback 之前已完工):
1. PARA + MOC view (9 builtin view, 4 new)
2. 周期笔记 (6 builtin job, 2 new)
3. 任务管理 (task 实体 + 2 MCP tool)
4. 灵感收集箱 (扩展快捷键)
5. note 模板系统 (4 template + 2 MCP tool)
6. Reranker (hybrid_search.rerank)
7. Query expansion (hybrid_search.expand)
8. ✅ 本地 embedding fallback (Phase 11C 单项已完工)
9. stratum-cli 一键装

测试: oprim X / oskill Y / omodul Z = N total, 0 regressions
版本: oprim 2.9.0 / oskill 2.10.0 / omodul 1.9.0 / stratum-cli 0.1.0 / stratum-extension 0.2.0

STRATUM_API_v1.md 附录 E 更新 (Phase 11C 增量).

Stratum v1.0 + Phase 11C 完工.
```

---

## §12 异常处理

立即停止 + 报告 advisor:
- Reranker / Expansion 选型 (Ollama 模型不存在或维度不一致)
- task parser 跟既有 note 格式冲突
- 浏览器扩展 manifest v3 quirks
- stratum-cli 依赖跨平台问题 (Windows / macOS)

非阻塞:
- 个别测试需要 mock 复杂场景, 给 reasonable mock
- 模板渲染 edge case (变量名含特殊字符) 给默认行为

---

## §13 时间线

| Wave | 项 | 工时 |
|---|---|---|
| Wave 0 | 准入 + 调研 | 0.5 天 |
| Wave 1 | #1 PARA view | 0.5 天 |
| Wave 2 | #2 周期笔记 | 1-2 天 |
| Wave 3 | #3 任务管理 | 2-3 天 |
| Wave 4 | #4 灵感扩展 | 1-2 天 |
| Wave 5 | #5 模板系统 | 2-3 天 |
| Wave 6 | #6 Reranker | 2-3 天 |
| Wave 7 | #7 Query Expansion | 2-3 天 |
| Wave 8 | #9 stratum-cli | 2-3 天 |
| Wave 9 | Gate | 0.5 天 |
| **总计** | | **14-22 天 (~3 周)** |

---

**End**
