# Stratum 部署文档

**版本**: v0.3 (Phase 10 完工状态)
**最后更新**: 2026-05-20
**适用部署**: Wiki 个人单用户 — 笔记本 + 主机 + Singapore VPS

---

## 目录

1. [概览](#1-概览)
2. [部署拓扑总图](#2-部署拓扑总图)
3. [Layer A — 当前可部署 (Phase 1-10)](#3-layer-a--当前可部署-phase-1-10)
4. [Phase 2 — GDrive 同步集成](#4-phase-2--gdrive-同步集成)
5. [Phase 11+ — Layer B 主机 GPU 外挂 (前置准备)](#5-phase-11--layer-b-主机-gpu-外挂-前置准备)
6. [故障恢复](#6-故障恢复)
7. [安全 + 隐私清单](#7-安全--隐私清单)
8. [监控 (v1.0 minimal)](#8-监控-v10-minimal)
9. [已知问题 + 限制](#9-已知问题--限制)
10. [版本对应表](#10-版本对应表)

---

## 1. 概览

### 读者

本文档面向 **Wiki**，记录 Stratum 在 Wiki 个人设备上的部署流程。

**不适合**：
- 多用户云部署（Phase 14+ 商业化范围，超出当前 SPEC）
- 他人仿部署（参考价值有限，依赖 Wiki 账号/设备/API Key 体系）

### Stratum 是什么

Stratum 是 Wiki 的个人知识库系统，采用 4O 范式实现：

```
oprim (v2.5.0)  →  oskill (v2.5.0)  →  omodul (v1.2.2)
原子操作             技能层              模块/守护进程
```

当前状态（Phase 10 完工）：
- 文件入库（inbox → substrate）
- 混合检索（向量 + 全文，支持 pin/citation）
- 翻译 derivative（async, DeepSeek/Claude/Qwen3）
- MCP server（供 Claude Desktop / Hermes 调用）

---

## 2. 部署拓扑总图

决策依据：[ADR-021](decisions/ADR-021.md) + [ADR-016](decisions/ADR-016.md)

### 设备分层

| Layer | 设备 | GPU/RAM | Phase 1-10 状态 | Phase 11+ 计划 |
|---|---|---|---|---|
| **Layer A** | 笔记本 (Win11/WSL2) | 4G VRAM / 24G RAM | ✅ Stratum 主体 | + searxng |
| **Layer B** | 主机 (Win11/WSL2) | 10G VRAM / 32G RAM | (闲置) | whisper-Q4/Q5, F5-TTS, SD 1.5 (vision → Claude API, Ollama 留给 Aegis) |
| **Layer C** | Singapore VPS | CPU only | ✅ sing-box 代理 (已有) | 无变化 |

### 跨机通信

```
┌──────────────────────────────────────────────┐
│              Tailscale mesh (个人 tailnet)    │
│                                              │
│  Layer A (笔记本)        Layer B (主机)       │
│  ┌─────────────────┐    ┌──────────────────┐ │
│  │ stratum-main    │    │ whisper (9303)   │ │
│  │ postgres (5432) │◄───│ F5-TTS  (9301)   │ │
│  │ redis   (6379)  │    │ SD-webui (9302)  │ │
│  │ rabbitmq (5672) │    │ ollama  (11434)  │ │  ← Aegis only (v1.0 vision → Claude API)
│  │ lancedb  (file) │    └──────────────────┘ │
│  └─────────────────┘                         │
│          │                   Layer C (VPS)   │
│          │                ┌──────────────┐   │
│          └───────────────►│ sing-box     │   │
│                           │ (443/代理)   │   │
│                           └──────────────┘   │
└──────────────────────────────────────────────┘

笔记本 ←→ 主机: Tailscale Magic DNS (stratum-host.ts.net, 5-15ms LAN)
笔记本 ←→ VPS:  Tailscale (stratum-vps.ts.net, 代理出口)

Layer A 数据 → GDrive (Phase 2 后): substrate + index snapshot
Layer B 无数据持久化: 外挂任务数据任务完成即清理
```

### Tailscale ACL (已配置)

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:stratum-main"],
      "dst": ["tag:stratum-host:9301-9304", "tag:stratum-host:11434", "tag:stratum-host:22"]
    },
    {
      "action": "accept",
      "src": ["tag:stratum-main"],
      "dst": ["tag:stratum-vps:443"]
    }
  ]
}
```

---

## 3. Layer A — 当前可部署 (Phase 1-10)

> **这是重点章节**。Phase 1-10 功能已完工，按此部署即可启动完整知识库。

### 3.1 前置硬件/OS 要求

| 项目 | 最低 | 推荐 | 备注 |
|---|---|---|---|
| OS | WSL2 Ubuntu 22.04 | WSL2 Ubuntu 24.04 | Windows 11 宿主 |
| RAM | 16 GB | 24 GB | 模型推理 + 索引 |
| 磁盘 | 50 GB (for ~/.stratum) | 100 GB | 含 substrate + index + model cache |
| Python | 3.11 | 3.12 | 3.14+ 有已知 Pillow 兼容性限制 |
| Docker | Docker Desktop 4.x | 同 | 或 nerdctl (containerd) |

**前置检查脚本**:

```bash
cat > /tmp/stratum_preflight.sh <<'PREFLIGHT'
#!/bin/bash
set -e
echo "=== Stratum Layer A 前置检查 ==="

PASS=0
FAIL=0

check() {
  if eval "$2" &>/dev/null; then
    echo "  ✓ $1"
    ((PASS++))
  else
    echo "  ✗ $1 — $3"
    ((FAIL++))
  fi
}

# Python
check "Python 3.11+" \
  "python3 -c 'import sys; assert sys.version_info >= (3,11)'" \
  "Install Python 3.11+"

# pip / uv
check "pip 可用" "python3 -m pip --version" "python3 -m ensurepip"

# Docker
check "Docker daemon" "docker info" "Start Docker Desktop"
check "Docker Compose" "docker compose version" "Update Docker Desktop"

# WSL2
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "  ✓ WSL2 detected"
  ((PASS++))
else
  echo "  ℹ 非 WSL2 环境 (bare Linux 也可用)"
fi

# Disk (require >50GB free on home)
FREE_GB=$(df -BG "$HOME" | awk 'NR==2 {print $4}' | tr -d G)
if [ "$FREE_GB" -ge 50 ]; then
  echo "  ✓ 磁盘空间 ${FREE_GB}GB 可用"
  ((PASS++))
else
  echo "  ✗ 磁盘空间不足: ${FREE_GB}GB (需要 50GB+)"
  ((FAIL++))
fi

# RAM
TOTAL_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
if [ "$TOTAL_GB" -ge 16 ]; then
  echo "  ✓ RAM ${TOTAL_GB}GB"
  ((PASS++))
else
  echo "  ✗ RAM 不足: ${TOTAL_GB}GB (推荐 16GB+)"
  ((FAIL++))
fi

# API Keys check
for KEY in DEEPSEEK_API_KEY ANTHROPIC_API_KEY DASHSCOPE_API_KEY; do
  if [ -n "${!KEY}" ]; then
    echo "  ✓ $KEY 已设"
    ((PASS++))
  else
    echo "  ✗ $KEY 未设 (翻译/embedding 功能需要)"
    ((FAIL++))
  fi
done

echo ""
echo "=== 结果: ${PASS} 通过 / ${FAIL} 失败 ==="
[ "$FAIL" -eq 0 ] && echo "✅ 可以继续部署" || echo "⚠ 请修复上述问题再继续"
PREFLIGHT
chmod +x /tmp/stratum_preflight.sh
bash /tmp/stratum_preflight.sh
```

### 3.2 目录结构

`oprim.bootstrap` 自动创建 `~/.stratum/` 结构:

```
~/.stratum/
├── inbox/                  # 投递入口 — 待处理文件放这里
│   └── (你的 PDF / EPUB / MD / 视频字幕...)
├── data/
│   ├── meta.db             # DuckDB 元数据库 (substrate + derivative 记录)
│   ├── postgres/           # Phase 2 后: PostgreSQL 持久化数据
│   ├── redis/              # Phase 2 后: Redis 缓存
│   └── rabbitmq/           # Phase 2 后: RabbitMQ 队列
├── index/
│   ├── vectors/            # LanceDB 向量索引
│   └── fulltext/           # Tantivy 全文索引
├── _archive/               # inbox 处理完毕后归档 (不删，留溯源)
├── cache/
│   └── embeddings/         # embedding 缓存 (避免重复计费)
└── secrets/                # OAuth 凭证 (chmod 600，不入 git)
    ├── gdrive_oauth.json   # Phase 2 后: Google Drive OAuth client config
    └── gdrive_token.json   # Phase 2 后: OAuth refresh token (自动生成)
```

### 3.3 Python 环境 + 安装

```bash
# 推荐: 用 uv (快) 或 pip (标准)

# 方式 A: uv (推荐)
pip install uv   # 或: curl -LsSf https://astral.sh/uv/install.sh | sh

cd ~/projects/platform/oprim && uv pip install -e .
cd ~/projects/platform/oskill && uv pip install -e .
cd ~/projects/platform/omodul && uv pip install -e .

# 方式 B: pip (传统)
cd ~/projects/platform/oprim && pip install -e .
cd ~/projects/platform/oskill && pip install -e .
cd ~/projects/platform/omodul && pip install -e .

# 验证安装
python3 -c "import oprim; print('oprim', oprim.__version__)"
python3 -c "import oskill; print('oskill', oskill.__version__)"
python3 -c "import omodul; print('omodul', omodul.__version__)"
# 期待: oprim 2.5.0 / oskill 2.5.0 / omodul 1.2.2
```

### 3.4 配置文件 `~/.stratum/config.yaml`

```yaml
# ~/.stratum/config.yaml
# Stratum Layer A 配置 — 笔记本 (Wiki 主设备)

device:
  id: "laptop_wiki"         # 跨设备同步用，唯一标识
  name: "Wiki Laptop"

user:
  id: "wiki"                # 单用户 (Phase 14+ 多用户时改)

# ── LLM 配置 ────────────────────────────────────────────────
llm:
  providers:
    deepseek:
      api_key_env: DEEPSEEK_API_KEY
      model: deepseek-chat
      # Phase 10 translation: 主力翻译 provider
    claude:
      api_key_env: ANTHROPIC_API_KEY
      model: claude-sonnet-4-6
      # 注: Claude quota 恢复后 (2026-06-01+) 补跑集成测试
    qwen3:
      api_key_env: DASHSCOPE_API_KEY
      model: qwen-max
    
    # Phase 11+ 跨机本地模型 (未启用，等 Layer B 就绪)
    # local_ollama:
    #   base_url: "${STRATUM_OLLAMA_HOST}"   # http://stratum-host.ts.net:11434
    #   model: qwen3:14b-q4

# ── Embedding ───────────────────────────────────────────────
embedding:
  provider: dashscope
  model: text-embedding-v4   # Qwen3-Embedding (ADR-005: 中文 SOTA)
  api_key_env: DASHSCOPE_API_KEY
  dimension: 1024            # 精度 98.1% + 存储 4GB/1M docs

# ── 存储 ────────────────────────────────────────────────────
storage:
  primary: local             # Phase 2 前: 纯本地
  # primary: gdrive          # Phase 2 后切换
  local:
    root: ~/.stratum/data
  # gdrive:
  #   oauth_config: ~/.stratum/secrets/gdrive_oauth.json
  #   root_folder: /Stratum

# ── 搜索 ────────────────────────────────────────────────────
search:
  default_mode: augmented    # strict (纯向量+全文) / augmented (Phase 1.5 LLM 兜底, 当前 stub)
  pinned_boost: 1.5          # pinned substrate 结果得分加权
  return_citations: true     # 返回 Citation 对象 (来源段落定位)

# ── Phase 11+ 外挂 ──────────────────────────────────────────
external_providers:
  vision: claude      # v1.0 默认: Claude API (ANTHROPIC_API_KEY). local=Ollama (Aegis only)
  tts: local          # F5-TTS (localhost:9301)
  stt: local          # whisper.cpp (localhost:9303)
  image_gen: local    # SD 1.5/ComfyUI (localhost:9302)
  search: local       # SearXNG (localhost:9304)

# external:           # 跨机地址 (Tailscale)
#   whisper:
#     base_url: "${STRATUM_WHISPER_HOST}"   # http://stratum-host.ts.net:9303
#   tts:
#     base_url: "${STRATUM_TTS_HOST}"       # http://stratum-host.ts.net:9301
#   sd:
#     base_url: "${STRATUM_SD_HOST}"        # http://stratum-host.ts.net:9302
```

### 3.5 环境变量 `.env`

```bash
# ~/projects/stratum/.env
# 权限必须 600，不入 git

cat > ~/projects/stratum/.env <<'ENV_EOF'
# ── 数据库密码 ──
POSTGRES_PASSWORD=<生成强密码，至少 24 字符>
RABBITMQ_PASSWORD=<生成强密码，至少 24 字符>

# ── API Keys ──
DEEPSEEK_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DASHSCOPE_API_KEY=sk-...

# ── Phase 11+ 外挂 (等 Layer B 就绪再填) ──
# STRATUM_OLLAMA_HOST=http://stratum-host.ts.net:11434
# STRATUM_WHISPER_HOST=http://stratum-host.ts.net:9303
# STRATUM_TTS_HOST=http://stratum-host.ts.net:9301
# STRATUM_SD_HOST=http://stratum-host.ts.net:9302
ENV_EOF
chmod 600 ~/projects/stratum/.env
echo ".env created with 600 permissions"
```

生成强密码的方式:

```bash
# 生成 32 字符随机密码 (openssl)
openssl rand -base64 32

# 或用 python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.5.1 AI API Keys (`~/.stratum/secrets/.env`)

> **与 §3.5 的区别**: §3.5 的 `~/projects/stratum/.env` 存 Docker 密码（Postgres/RabbitMQ）。
> 本节的 `~/.stratum/secrets/.env` 存 AI API Key，由 oprim 在启动时自动加载。两个文件独立。

```bash
# 1. 复制模板
cp ~/.stratum/secrets/.env.example ~/.stratum/secrets/.env

# 2. 填入实际 key（用编辑器打开）
#    DASHSCOPE_API_KEY=sk-...
#    DEEPSEEK_API_KEY=sk-...
#    ANTHROPIC_API_KEY=sk-ant-...

# 3. 锁权限
chmod 600 ~/.stratum/secrets/.env
```

**加载机制**（`oprim/_config.py`）：
- import oprim 时自动执行 `load_dotenv(~/.stratum/secrets/.env, override=False)`
- `override=False`：shell `export DASHSCOPE_API_KEY=xxx` 优先于 `.env` 文件
- 缺少必需 key 时，`load_config()` 打印 WARNING（不 raise）：

```
WARNING oprim.config: DASHSCOPE_API_KEY 未设置 — hybrid_search / embedding 不可用
WARNING oprim.config: DEEPSEEK_API_KEY 未设置 — 翻译不可用
WARNING oprim.config: ANTHROPIC_API_KEY 未设置 — Claude Vision 不可用
```

**`.gitignore` 验证**（已含，无需手动添加）：
```
stratum/.gitignore  → .env, .env.local
platform/.gitignore → .env, .env.*, !.env.example
```

---

### 3.6 Docker 基础服务 (`docker-compose.layer-a.yml`)

> **注**: Phase 1-10 运行时不需要 Docker（DuckDB/LanceDB/Tantivy 均为嵌入式）。
> Docker 服务是为 **Phase 2（网盘 + 同步）提前准备**，现在启动不影响 Phase 1-10 功能。

```yaml
# ~/projects/stratum/docker-compose.layer-a.yml

services:
  stratum-postgres:
    image: postgres:17-alpine
    container_name: stratum-postgres
    environment:
      POSTGRES_DB: stratum
      POSTGRES_USER: stratum
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?must set POSTGRES_PASSWORD in .env}
    volumes:
      - ~/.stratum/data/postgres:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"    # 仅 localhost，不暴露 LAN
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stratum"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  stratum-redis:
    image: redis:7-alpine
    container_name: stratum-redis
    command: redis-server --appendonly yes
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - ~/.stratum/data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
    restart: unless-stopped

  stratum-rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: stratum-rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: stratum
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:?must set RABBITMQ_PASSWORD in .env}
    ports:
      - "127.0.0.1:5672:5672"      # AMQP
      - "127.0.0.1:15672:15672"    # Management UI (http://localhost:15672)
    volumes:
      - ~/.stratum/data/rabbitmq:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 15s
    restart: unless-stopped

  # stratum-main: 不容器化 (开发期直接跑 Python，方便 debug)
  # Phase 11+ production 期可容器化
```

### 3.7 完整启动流程 (首次)

```bash
#!/bin/bash
# 首次部署 Layer A — 完整步骤
# 预计时间: ~15 分钟

set -e
cd ~/projects/stratum

echo "Step 1: 检查 .env"
[ -f .env ] || { echo "请先创建 .env (见 §3.5)"; exit 1; }
source .env
[ -n "$POSTGRES_PASSWORD" ] || { echo ".env 缺少 POSTGRES_PASSWORD"; exit 1; }

echo "Step 2: 安装 Python 库"
cd ~/projects/platform/oprim && uv pip install -e . -q
cd ~/projects/platform/oskill && uv pip install -e . -q
cd ~/projects/platform/omodul && uv pip install -e . -q
cd ~/projects/stratum

echo "Step 3: 初始化 ~/.stratum 目录结构"
python3 -m oprim.bootstrap
# 创建: inbox/ data/ index/ _archive/ cache/ secrets/

echo "Step 4: 写 config.yaml (如未存在)"
[ -f ~/.stratum/config.yaml ] && echo "  config.yaml 已存在，跳过" || \
  cp ~/projects/stratum/docs/config.yaml.example ~/.stratum/config.yaml

echo "Step 5: 启动 Docker 基础服务"
cd ~/projects/stratum
docker compose -f docker-compose.layer-a.yml --env-file .env up -d

echo "Step 6: 等服务 healthy"
sleep 15
docker compose -f docker-compose.layer-a.yml ps

echo "Step 7: 端到端 smoke test"
echo "# 测试文件" > ~/.stratum/inbox/smoke_test.md
python3 -m omodul.knowledge.process_inbox
python3 -c "
from oskill.knowledge.hybrid_search import hybrid_search
from oprim.meta_db.duckdb import MetaDB
import os
db = MetaDB(os.path.expanduser('~/.stratum/data/meta.db'))
results = hybrid_search(db, '测试')
print(f'hybrid_search: {len(results)} 结果')
print('✅ Smoke test 通过')
"

echo ""
echo "🎉 Layer A 部署完成"
echo "   下一步: python3 -m omodul.knowledge.start_mcp_server"
echo "   在 Claude Desktop 配置 MCP server 地址"
```

### 3.8 MCP Server (Claude Desktop 集成)

```bash
# 启动 MCP server (前台，开发用)
python3 -m omodul.knowledge.start_mcp_server

# 或后台 (生产用)
nohup python3 -m omodul.knowledge.start_mcp_server \
  > ~/.stratum/logs/mcp.log 2>&1 &
echo $! > ~/.stratum/mcp.pid
```

Claude Desktop `claude_desktop_config.json` 示例:

```json
{
  "mcpServers": {
    "stratum": {
      "command": "python3",
      "args": ["-m", "omodul.knowledge.start_mcp_server"],
      "env": {
        "DASHSCOPE_API_KEY": "<your_key>",
        "DEEPSEEK_API_KEY": "<your_key>",
        "ANTHROPIC_API_KEY": "<your_key>"
      }
    }
  }
}
```

当前暴露 4 个 MCP 工具:
- `stratum.hybrid_search` — 混合检索（向量 + 全文）
- `stratum.ingest_file` — 投递文件入库
- `stratum.pin_substrate` — 固定知识节点
- `stratum.unpin_substrate` — 解除固定

### 3.9 日常运维

```bash
# 启动基础服务 (每次开机或重启后)
cd ~/projects/stratum
docker compose -f docker-compose.layer-a.yml --env-file .env up -d

# 状态检查
docker compose -f docker-compose.layer-a.yml ps
docker compose -f docker-compose.layer-a.yml logs --tail=50 stratum-postgres

# 重启单个服务
docker compose -f docker-compose.layer-a.yml restart stratum-redis

# 停止全部
docker compose -f docker-compose.layer-a.yml down

# ── 知识库操作 ──────────────────────────────────────
# 处理 inbox (有新文件时跑)
python3 -m omodul.knowledge.process_inbox

# 翻译一个文件 (Phase 10 功能)
python3 -c "
from oskill.knowledge.translate_substrate import translate_substrate
from oprim.meta_db.duckdb import MetaDB
import os
db = MetaDB(os.path.expanduser('~/.stratum/data/meta.db'))
# translate_substrate(db, substrate_id='xxx', target_lang='zh', provider='deepseek')
"

# ── 手动备份 (Phase 2 前) ───────────────────────────
BACKUP_DATE=$(date +%Y%m%d_%H%M)
tar czf ~/stratum-backup-${BACKUP_DATE}.tar.gz \
  ~/.stratum/data/ \
  ~/.stratum/index/ \
  ~/.stratum/_archive/ \
  ~/.stratum/config.yaml
echo "备份: ~/stratum-backup-${BACKUP_DATE}.tar.gz"

# ── 升级 4O 库 (Phase X 完工时 CC 通知) ────────────
cd ~/projects/platform/oprim && git pull && uv pip install -e . -q
cd ~/projects/platform/oskill && git pull && uv pip install -e . -q
cd ~/projects/platform/omodul && git pull && uv pip install -e . -q
python3 -c "import oprim, oskill, omodul; print(oprim.__version__, oskill.__version__, omodul.__version__)"
```

---

## 4. Phase 2 — GDrive 同步集成

> **占位章节**。Phase 2 完工后 CC 补写详细步骤，当前提供框架。

决策依据：[ADR-006](decisions/ADR-006.md)、[ADR-008](decisions/ADR-008.md)

### 4.1 GDrive OAuth 凭证准备 (提前操作)

```bash
# OAuth JSON 从 Google Cloud Console 下载后放置
mkdir -p ~/.stratum/secrets
cp ~/Downloads/gdrive_oauth.json ~/.stratum/secrets/
chmod 600 ~/.stratum/secrets/gdrive_oauth.json
```

### 4.2 首次授权 (一次性, Phase 2 完工后)

```bash
# Phase 2 完工后跑 (模块路径以实际实现为准)
python3 -m omodul.sync.bg_sync \
  --user-id=wiki \
  --device-id=laptop_wiki \
  --auth-only
# 浏览器自动开 OAuth 同意页，授权后 token 自动保存到
# ~/.stratum/secrets/gdrive_token.json
```

### 4.3 切换主存储到 GDrive

```yaml
# ~/.stratum/config.yaml — Phase 2 启动后修改
storage:
  primary: gdrive           # 从 local 切换
  gdrive:
    oauth_config: ~/.stratum/secrets/gdrive_oauth.json
    root_folder: /Stratum   # GDrive 根目录
```

### 4.4 启动后台同步

```bash
# Phase 2 完工后
python3 -m omodul.sync.bg_sync \
  --user-id=wiki \
  --device-id=laptop_wiki &
echo $! > ~/.stratum/sync.pid
```

同步策略（设计目标）：
- substrate 原始文件 → GDrive `/Stratum/substrate/`
- 索引 snapshot（每日）→ GDrive `/Stratum/_hub_backup/`
- changefeed → 服务端（多端同步协调）
- 新设备恢复时间：5-15 分钟（取决于 GDrive 速度 + 数据量）

---

## 5. Phase 11+ — Layer B 主机 GPU 外挂 (前置准备)

决策依据：[ADR-021](decisions/ADR-021.md)、[ADR-019](decisions/ADR-019.md)

### 5.1 Wiki 行动清单（Phase 11 启动前）

| # | 任务 | 执行者 | 估时 | 状态 |
|---|---|---|---|---|
| 1 | Tailscale mesh 已配置（三台设备入 tailnet） | — | — | ✅ |
| 2 | 笔记本 ping/curl 主机 Tailscale IP | Wiki | 5 min | ⏳ |
| 3 | 主机 Ollama 安装 + qwen3:14b-q4 拉取验证 | Wiki | 30 min | ⏸ N/A (v1.0 vision→Claude API; Ollama 留 Aegis) |
| 4 | 主机 Docker + NVIDIA Container Runtime 配置 | Wiki | 30 min | ⏳ |
| 5 | 笔记本 `.env` 填写 `STRATUM_*_HOST` 变量 | Wiki + CC | 5 min | ⏳ |
| 6 | CC 部署主机 `docker-compose.layer-b.yml` | CC | 2h | ⏳ |

### 5.2 Tailscale 连通性验证 (Wiki 跑)

```bash
# 从笔记本
tailscale status
# 确认主机 (stratum-host) 在列且 online

# ping 测试
tailscale ping stratum-host
# 期待: pong from stratum-host ... via ... 延迟 5-15ms

# curl 测试 (Ollama 安装后)
TAILSCALE_HOST=stratum-host   # 替换为实际 Magic DNS 名
curl http://${TAILSCALE_HOST}.ts.net:11434/api/tags
# 期待: JSON 含 qwen3:14b-q4
```

如果连接失败，排查：

```bash
# 1. 检查 Tailscale 状态
tailscale status --peers

# 2. 检查 ACL 是否允许
tailscale ping --peerapi stratum-host

# 3. 主机端检查 Tailscale
# (在主机 WSL2 内)
tailscale status
sudo tailscale up --reset
```

### 5.3 主机 Ollama 安装 (Wiki 跑，主机 WSL2 内)

```bash
# 主机 WSL2 内执行
curl -fsSL https://ollama.com/install.sh | sh

# 配置监听 0.0.0.0 (默认只 localhost，Tailscale 无法穿透)
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama

# 拉取模型 (约 8.3GB，视网速而定)
ollama pull qwen3:14b-q4_k_m
# GPU 内存: ~8.3-10G (10G 卡可运行，4K token context 限制)

# 验证
curl http://localhost:11434/api/tags | python3 -m json.tool
# 期待: models 列表中含 qwen3:14b-q4_k_m
```

### 5.4 主机 NVIDIA Container Runtime (Docker GPU 支持)

```bash
# 主机 WSL2 内
# 1. 安装 nvidia-container-toolkit
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit

# 2. 配置 Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 3. 验证 GPU 透传
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
# 期待: 显示 GPU 信息，10G VRAM
```

### 5.5 主机 docker-compose.layer-b.yml (CC 执行，Phase 11 时)

> **占位**：Phase 11 启动时 CC 根据外挂最终选型补写完整配置。以下是框架。

```yaml
# 主机: ~/projects/stratum-host/docker-compose.layer-b.yml
# GPU 重外挂。不与 Layer A 共享 docker network。
# 访问方式: 笔记本通过 Tailscale Magic DNS 调用。

services:
  whisper:
    # whisper.cpp large-v3 Q4/Q5 量化版 (~4-5G VRAM)
    # image: Phase 11 启动时确定镜像 tag
    image: ghcr.io/ggml-org/whisper.cpp:latest-cuda
    ports:
      - "0.0.0.0:9303:8080"    # 0.0.0.0: Tailscale 可访问
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
              count: 1

  f5-tts:
    # F5-TTS (~6-8G VRAM，实测约 6.4G)
    # image: Phase 11 启动时确定镜像 tag
    image: placeholder/f5-tts:latest
    ports:
      - "0.0.0.0:9301:9001"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
              count: 1

  sd-webui:
    # Stable Diffusion 1.5/2.1 (~4-6G VRAM)
    # image: Phase 11 启动时确定镜像 tag
    image: placeholder/sd-webui:latest
    ports:
      - "0.0.0.0:9302:7860"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
              count: 1

  # ollama: 直接跑 systemd (§5.3 已配置)，不用 Docker

# GPU 并发约束 (ADR-021 §GPU 并发约束):
# whisper large-v3 量化版 ~4-5G + F5-TTS ~6-8G = 10-13G → 不可并发
# SD ~4-6G 可与 whisper 量化版共存，需实测
# ollama (systemd) ~8.3-10G — 跑 ollama 时不启动 F5/SD
# Q15 未决: 完整 GPU 任务调度策略待 Phase 11 设计
```

### 5.6 笔记本环境变量 (Phase 11 启动后填写)

```bash
# 追加到 ~/projects/stratum/.env
cat >> ~/projects/stratum/.env <<'EOF'

# Phase 11: Layer B 外挂服务地址 (替换 ts.net 为实际 tailnet 域名)
STRATUM_OLLAMA_HOST=http://stratum-host.ts.net:11434
STRATUM_WHISPER_HOST=http://stratum-host.ts.net:9303
STRATUM_TTS_HOST=http://stratum-host.ts.net:9301
STRATUM_SD_HOST=http://stratum-host.ts.net:9302
EOF
```

---

## 6. 故障恢复

### 6.1 Docker 服务崩溃 (postgres / redis / rabbitmq)

```bash
cd ~/projects/stratum

# 查看崩溃原因
docker compose -f docker-compose.layer-a.yml logs --tail=100 stratum-postgres

# 重启单服务
docker compose -f docker-compose.layer-a.yml restart stratum-postgres

# 重启全部
docker compose -f docker-compose.layer-a.yml down && \
  docker compose -f docker-compose.layer-a.yml up -d

# 验证 healthy
docker compose -f docker-compose.layer-a.yml ps
```

### 6.2 LanceDB 向量索引损坏

```bash
# 备份损坏的索引 (保留，可能能修复)
TIMESTAMP=$(date +%s)
mv ~/.stratum/index/vectors ~/.stratum/index/vectors.bad-${TIMESTAMP}

# 重建: 把 _archive/ 里的文件重新投入 inbox 再处理
# (重建时间取决于 substrate 数量 + embedding 速度)
cp ~/.stratum/_archive/*.* ~/.stratum/inbox/
python3 -m omodul.knowledge.process_inbox

# 验证重建结果
python3 -c "
from oprim.vector_db.lancedb import LanceDBVectorDB
import os
db = LanceDBVectorDB(os.path.expanduser('~/.stratum/index/vectors'))
count = db.count()
print(f'向量索引: {count} 条记录')
"
```

### 6.3 Tantivy 全文索引损坏

```bash
# 同 §6.2，全文索引与向量索引分开存储
mv ~/.stratum/index/fulltext ~/.stratum/index/fulltext.bad-$(date +%s)

# 重建: 重新跑 process_inbox (会同时重建向量 + 全文)
cp ~/.stratum/_archive/*.* ~/.stratum/inbox/
python3 -m omodul.knowledge.process_inbox
```

### 6.4 DuckDB meta.db 损坏

```bash
# 验证损坏
python3 -c "
import duckdb
conn = duckdb.connect(os.path.expanduser('~/.stratum/data/meta.db'))
conn.execute('SELECT count(*) FROM substrate').fetchall()
"

# 从备份恢复
ls ~/stratum-backup-*.tar.gz   # 找最近的备份
tar xzf ~/stratum-backup-20260520_XXXX.tar.gz ~/.stratum/data/meta.db

# 如无备份: meta.db 只存元数据 (文件路径/标题/pin状态)
# substrate 内容在 GDrive (Phase 2 后) 或 _archive/ 中，索引可重建
# 极端情况: 从头 process_inbox 重建 (元数据会重新生成)
```

### 6.5 GDrive token 过期 (Phase 2 后)

```bash
# token 过期症状: sync.log 出现 "invalid_grant" / "Token has been expired"
rm ~/.stratum/secrets/gdrive_token.json

# 触发重新授权 (浏览器打开 OAuth 页)
python3 -m omodul.sync.bg_sync \
  --user-id=wiki \
  --device-id=laptop_wiki \
  --auth-only
```

### 6.6 从 GDrive 完全恢复 (笔记本损坏，Phase 2 后)

```bash
# 新设备上:
# 1. 安装环境 (见 §3.3)
# 2. 放置 gdrive_oauth.json
# 3. 初始化新设备
python3 -m oprim.bootstrap

# 4. 从最新 GDrive snapshot 恢复 (模块路径以 Phase 2 实现为准)
python3 -m oskill.sync.restore_from_snapshot \
  --user-id=wiki \
  --device-id=laptop_wiki_new
# 下载时间: 取决于 GDrive 速度 + 数据量 (估计 10-60 分钟)
```

### 6.7 Tailscale 断连 (Phase 11 后影响外挂)

```bash
# 笔记本端
tailscale status
tailscale up --accept-routes

# 检查控制面可达性
curl https://controlplane.tailscale.com/ping

# Tailscale 控制面不可达时: LAN 直连仍通 (点对点加密，控制面只做密钥协商)
# 极端情况: 手动配 /etc/hosts 映射主机 LAN IP 作 fallback
# echo "192.168.x.x stratum-host.ts.net" >> /etc/hosts  # 替换实际 LAN IP
```

Stratum 主体在外挂断联时的行为（circuit breaker，4O v0.3 §E.1）：
- 翻译/TTS/SD/Whisper 任务进入等待队列
- 基础入库 + 检索功能正常（不依赖 Layer B）
- 连接恢复后任务自动重试

### 6.8 WSL2 Tailscale 内核问题 (kernel 6.8+)

```bash
# 症状: Tailscale 无法连接，日志出现 kernel networking errors
# 原因: ADR-021 调研发现，Linux kernel 6.8+ 部分版本 Tailscale kernel-mode 有问题

# 临时修复: 切换 userspace 模式
sudo tailscale down
sudo tailscale up --netfilter-mode=off

# 或配置环境变量 (永久)
echo 'TS_USERSPACE=true' | sudo tee -a /etc/default/tailscaled
sudo systemctl restart tailscaled

# 当前 WSL2 kernel 6.6.114 未受影响，升级 kernel 时注意
```

---

## 7. 安全 + 隐私清单

依据：[SPEC §13](decisions/ADR-017.md) + ADR-021 隐私条款

### 部署前必做

- [ ] `.env` 文件权限 600: `chmod 600 ~/projects/stratum/.env`
- [ ] `~/.stratum/secrets/` 目录权限 700: `chmod 700 ~/.stratum/secrets/`
- [ ] OAuth JSON 文件权限 600: `chmod 600 ~/.stratum/secrets/*.json`
- [ ] `.env` 已加入 `.gitignore` (验证: `git status` 不显示 .env)

### 网络隔离

- [ ] Postgres/Redis/RabbitMQ 端口仅绑定 127.0.0.1（不暴露 LAN）
  - 验证: `ss -tlnp | grep -E '5432|6379|5672'` → 应只显示 127.0.0.1
- [ ] Tailscale ACL 限定 Stratum 节点之间（不对全 tailnet 开放）
  - 验证: Tailscale Admin Console → ACL 规则已配置

### 数据隐私 (ADR-021 §数据流向)

- [ ] substrate 原始内容仅在 Layer A + GDrive（不进入 Layer B 主机）
- [ ] 外挂调用只传**任务数据**（whisper 只传 audio，TTS 只传 text）
- [ ] 外挂日志只记元数据（任务 ID / 耗时），不记内容
- [ ] Layer B 外挂无持久化：任务完成后清理临时文件

### API Key 安全

- [ ] API Key 只在 `.env` + `~/.stratum/config.yaml`，不硬编码进代码
- [ ] 定期 rotate API Key（DashScope / DeepSeek 控制台）
- [ ] Anthropic Key 定期检查配额（当前 2026-06-01 配额恢复）

### 备份加密 (v1.0 单用户暂不强制，商业化时加)

- 当前：`tar.gz` 明文备份，放在本地磁盘
- Phase 5+：考虑 `gpg --symmetric` 加密备份文件

---

## 8. 监控 (v1.0 minimal)

### 基础健康检查

```bash
# 一键状态检查脚本
cat > ~/bin/stratum-status <<'EOF'
#!/bin/bash
echo "=== Stratum 状态检查 $(date) ==="

# Docker 服务
echo "── Docker 服务 ──"
docker compose -f ~/projects/stratum/docker-compose.layer-a.yml ps 2>/dev/null || \
  echo "  Docker 服务未运行"

# 磁盘
echo "── 磁盘 ──"
df -h ~/.stratum | tail -1

# meta.db substrate 数量
echo "── 知识库 ──"
python3 -c "
import duckdb, os
try:
    conn = duckdb.connect(os.path.expanduser('~/.stratum/data/meta.db'), read_only=True)
    n = conn.execute('SELECT count(*) FROM substrate').fetchone()[0]
    print(f'  substrate: {n} 条')
except Exception as e:
    print(f'  meta.db 检查失败: {e}')
" 2>/dev/null

# Phase 11+: Tailscale / 外挂状态
# tailscale status --peers 2>/dev/null | grep -E 'stratum-host|stratum-vps'
EOF
chmod +x ~/bin/stratum-status
```

### 磁盘告警 (cron)

```bash
# 每天 6:00 检查磁盘空间
crontab -e
# 加入:
# 0 6 * * * df -BG ~/.stratum | awk 'NR==2 && int($5)>80 {print "Stratum 磁盘告警: " $5 " 已用"}' >> ~/.stratum/logs/disk.log
```

### 完整可观测栈 (Phase 11+ 规划)

helios-platform 已有 Prometheus + Grafana + Loki 栈，Phase 11+ 接入时：
- oprim 层：暴露 `/metrics` (请求数/延迟/错误率)
- omodul 层：进程日志 → Loki
- Docker 服务：cadvisor → Prometheus

---

## 9. 已知问题 + 限制

| # | 问题 | 影响 | 状态/计划 |
|---|---|---|---|
| 1 | `translate_document()` sync wrapper 仍可用 | 从 async context 调用会 `RuntimeError` | Phase 11 后正式删，现在用 `translate_document_async()` |
| 2 | `hybrid_search` mode=augmented 的 LLM 兜底是 stub | augmented 模式当前等同 strict | Phase 11 实施真正 LLM augmented path |
| 3 | Phase 11 外挂 GPU 调度未设计 | whisper-large + F5-TTS 不可并发 | Q15 未决，Phase 11 设计 |
| 4 | WSL2 kernel 6.8+ Tailscale 问题 | 升级内核后 Tailscale 可能断 | 见 §6.8 临时修复；Tailscale 上游跟进 |
| 5 | Claude API quota 2026-06-01 前受限 | Claude 作翻译 provider 暂时不可用 | 用 DeepSeek / Qwen3 替代；6 月后补集成测试 |
| 6 | Docker Magic DNS in bridge container 不解析 | Layer A 主体用 network_mode: host 规避 | ADR-021 §Tailscale 配置注意事项 |
| 7 | marker-pdf INFRA_FAIL (BATCH2 实证) | marker 作为 PDF parser 未实证 | pymupdf4llm 作默认 parser；marker 等环境修复 |
| 8 | hevi 部署位置未决 | Phase 11 hevi 集成阻塞 | Q14 — hevi 经理人决定 |

---

## 10. 版本对应表

| Stratum 阶段 | oprim | oskill | omodul | 完工日期 | 主要功能 |
|---|---|---|---|---|---|
| Phase 1 (v0.1) | 2.2.0 | 2.3.0 | 1.2.0 | 2026-05-18 | 4O 基础: 入库/检索/MCP server |
| Phase 1.5 (v0.2) | 2.3.1 | 2.4.0 | 1.2.2 | 2026-05-18 | pin/unpin + citation + hybrid_search mode |
| Phase 10 (v0.3) | 2.5.0 | 2.5.0 | 1.2.2 | 2026-05-19 | Translation async (DeepSeek/Claude/Qwen3) |
| ADR-020 (v0.3.1) | 2.5.0 | 2.5.0 | 1.2.2 | 2026-05-19 | async provider 重构 (sync wrapper deprecated) |
| Phase 2 (v0.4) | TBD | TBD | TBD | TBD | GDrive 同步 + changefeed + 多端 |
| Phase 11 (v1.0) | TBD | TBD | TBD | TBD | Agent + Scheduled Jobs + Layer B 外挂全部就绪 |

### 当前实际安装版本确认

```bash
python3 -c "
import oprim, oskill, omodul
print(f'oprim  {oprim.__version__}')
print(f'oskill {oskill.__version__}')
print(f'omodul {omodul.__version__}')
"
# 期待输出:
# oprim  2.5.0
# oskill 2.5.0
# omodul 1.2.2
```

---

## 附录: 关键路径速查

```bash
# ── 代码 ──
~/projects/platform/oprim/     # oprim 源码
~/projects/platform/oskill/    # oskill 源码
~/projects/platform/omodul/    # omodul 源码
~/projects/stratum/             # stratum repo (配置 + ADR + 文档)

# ── 运行时数据 ──
~/.stratum/inbox/              # 投递入口
~/.stratum/data/meta.db        # DuckDB 元数据
~/.stratum/index/vectors/      # LanceDB 向量索引
~/.stratum/index/fulltext/     # Tantivy 全文索引
~/.stratum/_archive/           # 已处理文件归档
~/.stratum/secrets/            # OAuth 凭证 (chmod 600)
~/.stratum/config.yaml         # Stratum 配置

# ── 部署配置 ──
~/projects/stratum/.env                         # API Keys + 密码 (chmod 600)
~/projects/stratum/docker-compose.layer-a.yml   # Layer A Docker 服务

# ── 决策文档 ──
~/projects/stratum/docs/decisions/INDEX.md      # ADR 全览
~/projects/stratum/docs/decisions/ADR-021.md    # 跨机拓扑决策
~/projects/stratum/docs/decisions/ADR-019.md    # 外挂架构决策
```

---

## §8 浏览器扩展安装 (Phase 4)

### 8.1 启动 Stratum 后端 API

```bash
cd ~/projects/platform/omodul
# 首次运行：安装依赖
uv pip install -e ".[browser-extension]" --python .venv/bin/python

# 启动 (仅绑定 localhost:14567)
python -m omodul.knowledge.browser_extension

# 验证
curl http://localhost:14567/api/v1/browser-extension/health
# → {"status":"ok","version":"0.1.0"}
```

### 8.2 初始化 Token (一次性)

```bash
python -m omodul.knowledge.browser_extension init
# 输出 token，保存备用
# token 存储于: ~/.stratum/secrets/browser_ext_token.txt (chmod 600)
```

### 8.3 Chrome / Edge 扩展安装

```
1. 打开 chrome://extensions/
2. 右上角启用 "Developer mode"
3. 点 "Load unpacked" → 选 ~/projects/stratum-extension/
4. 工具栏出现 Stratum 图标 ✓
```

### 8.4 Firefox 扩展安装

```
1. 打开 about:debugging#/runtime/this-firefox
2. "Load Temporary Add-on" → 选 ~/projects/stratum-extension/manifest.json
注意: Firefox 不支持 sidePanel (chrome.sidePanel API)，Sidebar 功能不可用。
Popup 保存 / 右键菜单 正常工作。
```

### 8.5 配置 Token

```
1. 点工具栏 Stratum 图标 → 弹出 popup
2. 点 "Settings"（或右键扩展图标 → Options）
3. 粘贴 §8.2 生成的 token → 点 "Save & Verify"
4. 显示 "✓ Token saved and server reachable" 即配置完成
```

### 8.6 日常使用

| 操作 | 方式 |
|---|---|
| 保存当前完整网页 | 点扩展图标 → "Save full page" |
| 保存选中文字 | 选中文字 → 点扩展图标 → "Save selection" |
| 右键快速保存 | 选中文字 → 右键 → "Save selection to Stratum" |
| 右键保存整页 | 页面空白处右键 → "Save page to Stratum" |
| 查看相关内容 | 点扩展图标 → "Sidebar" (Chrome/Edge only) |

**URL 去重**: 同一 URL（含 utm_* 等追踪参数）重复保存时自动返回已有 substrate，不产生重复。

### 8.7 故障排查

```bash
# 服务未响应
curl http://localhost:14567/api/v1/browser-extension/health
# → 若 Connection refused: 重新执行 §8.1

# Token 无效 (401)
cat ~/.stratum/secrets/browser_ext_token.txt
# 重新在扩展 Options 页面填入

# 查看服务日志
python -m omodul.knowledge.browser_extension 2>&1 | head -50
```

---

*本文档由 CC (Claude Code) 依据 ADR-016/019/021 + Phase 1/1.5/10/Phase2/Phase4 完工状态撰写。*
