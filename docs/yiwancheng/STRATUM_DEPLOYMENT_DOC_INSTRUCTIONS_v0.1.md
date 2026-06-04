# STRATUM_DEPLOYMENT_DOC_INSTRUCTIONS_v0.1.md

**任务**: 撰写 Stratum 部署文档 (DEPLOYMENT.md)
**执行者**: 任一空闲 CC (推荐刚完工治理修复的 CC, ADR-021 上下文连贯)
**执行模式**: Claude Code FULL AUTO (文档类, 不实施代码)
**触发**: ADR-021 跨机部署拓扑已锁定, 需要落地为可执行部署文档
**输出**: `docs/DEPLOYMENT.md` 写入 stratum repo
**工程量**: 1 天

---

## §0 工作模式

### 范围 (R-4 严格)

✅ 允许:
- 撰写 docs/DEPLOYMENT.md (Stratum 部署主文档)
- 引用 ADR-016 / ADR-019 / ADR-021 (已有决策, 不重新讨论)
- 引用 Phase 1 完工状态 (oprim/oskill/omodul 已实施清单)
- 引用 Phase 10 完工状态 (translate 已可用)
- 引用 Phase 1.5 完工状态 (pin/unpin + citation)
- 写 bash / docker-compose / YAML 配置示例
- 写故障恢复脚本

❌ 禁止:
- 实施任何 production 代码 (这是文档任务)
- 写未来 Phase 的部署细节 (Phase 11+ 部分留占位符)
- 修改 stratum 代码本体
- 启动任何服务测试 (这是参考文档, 不是执行任务)

### 真理源

- ADR-021: 跨机拓扑 (Layer A / B / C)
- ADR-016: 本地部署原则
- ADR-019: 外挂解耦原则
- SPEC v0.5 + v0.6 PATCH: 数据架构 / 同步策略
- Phase 1 + Phase 10 + Phase 1.5 完工状态: 当前实际可用功能

### 输出位置

```
~/projects/stratum/docs/DEPLOYMENT.md
```

如果 docs/ 已有 README 或其他文档, 不动它们, 只加 DEPLOYMENT.md。

---

## §1 DEPLOYMENT.md 必含章节

### §1.1 概览 + 谁该读这个文档

- Stratum 是单用户 (Wiki) 本地 + 用户网盘部署
- 跨 3 层 (笔记本 + 主机 + Singapore VPS)
- 读者: Wiki 自己 (主要), 未来商业化时 onboarding 新用户参考
- 不适合: 服务端集群 / 多用户云部署 (那是 Phase 14+ 才考虑)

### §1.2 部署拓扑总图

引用 ADR-021 三层拓扑表, 加上 Phase 维度:

| Layer | 设备 | Phase 1-10 已部署 | Phase 11+ 计划 |
|---|---|---|---|
| Layer A | 笔记本 (24G/4G GPU) | ✅ stratum-main, postgres, redis, rabbitmq, lancedb | + searxng (轻外挂) |
| Layer B | 主机 (32G/10G GPU) | (闲置) | whisper-Q4, F5-TTS, SD 1.5, ollama qwen3-q4 |
| Layer C | Singapore VPS | ✅ sing-box 代理 (已有) | (无变化) |

ASCII 拓扑图 (含 Tailscale mesh)。

### §1.3 当前可部署 Layer A (Phase 1-10 已完工)

这是**重点章节**, 因为 Wiki 现在马上就要在笔记本上部署。

#### 1.3.1 前置硬件 / OS 检查

```bash
# 笔记本 OS 要求
# - WSL2 (Win11 host) + Ubuntu 22.04+ 或 24.04
# - Docker Desktop 或 nerdctl (containerd)
# - Python 3.11+
# - Disk: 至少 50 GB 给 ~/.stratum (substrate + index + cache)
# - RAM: 16 GB 最低, 24 GB 推荐

# 验证脚本
cat > /tmp/preflight.sh <<'EOF'
#!/bin/bash
echo "=== Stratum Layer A 前置检查 ==="

# Python
python3 --version || { echo "❌ Python 3 missing"; exit 1; }
# 期待 3.11+

# Docker
docker --version || { echo "❌ Docker missing"; exit 1; }
docker compose version || { echo "❌ Docker Compose missing"; exit 1; }

# Disk
df -h ~/ | tail -1

# RAM
free -h

# WSL detection
grep -qi microsoft /proc/version && echo "✓ WSL2 detected"

echo "=== Preflight OK ==="
EOF
chmod +x /tmp/preflight.sh
bash /tmp/preflight.sh
```

#### 1.3.2 目录结构

```
~/.stratum/
├── inbox/           # 用户投递的 substrate 文件 (process_inbox 处理)
├── data/            # 用户元数据 (SQLite meta.db)
├── index/           # 向量索引 (LanceDB)
├── _archive/        # 处理完的文件归档
├── secrets/         # OAuth 凭证 (.gitignore'd)
│   ├── gdrive_oauth.json   # Google Drive (Phase 2 需要)
│   └── gdrive_token.json   # OAuth refresh token (自动生成)
└── credentials/     # 其他凭证
```

`stratum init` 命令自动创建。

#### 1.3.3 配置文件 ~/.stratum/config.yaml

```yaml
# Stratum Layer A 配置 (笔记本)
device:
  id: "laptop_wiki"   # 跨设备同步用
  name: "Wiki Laptop"

user:
  id: "wiki"          # 单用户 (Phase 14+ 多用户时换)

llm:
  providers:
    # 远程 API (Phase 10 已实施)
    deepseek:
      api_key_env: DEEPSEEK_API_KEY
      model: deepseek-chat
    claude:
      api_key_env: ANTHROPIC_API_KEY
      model: claude-sonnet-4-5
    qwen3:
      api_key_env: DASHSCOPE_API_KEY
      model: qwen-max
    
    # Phase 11+ 跨机调 ollama (placeholder, 未启用)
    # local_ollama:
    #   base_url: http://stratum-host.ts.net:11434
    #   model: qwen3:14b-q4

embedding:
  provider: dashscope
  model: text-embedding-v4
  api_key_env: DASHSCOPE_API_KEY

storage:
  # Phase 2 启动后启用 GDrive
  primary: local        # 当前阶段 (Phase 2 前)
  # primary: gdrive     # Phase 2 启动后切换
  local:
    root: ~/.stratum/storage_local
  # gdrive:
  #   oauth_config: ~/.stratum/secrets/gdrive_oauth.json

search:
  default_mode: augmented   # strict / augmented (Phase 1.5 已实施)
  pinned_boost: 1.5
  return_citations: true
```

#### 1.3.4 docker-compose.layer-a.yml

```yaml
# ~/projects/stratum/docker-compose.layer-a.yml
version: '3.9'

services:
  stratum-postgres:
    image: timescale/timescaledb:latest-pg18
    container_name: stratum-postgres
    environment:
      POSTGRES_DB: stratum
      POSTGRES_USER: stratum
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?must set in .env}
    volumes:
      - ~/.stratum/data/postgres:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"   # 仅本地
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stratum"]
      interval: 10s

  stratum-redis:
    image: redis:7-alpine
    container_name: stratum-redis
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - ~/.stratum/data/redis:/data

  stratum-rabbitmq:
    image: rabbitmq:3-management
    container_name: stratum-rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: stratum
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:?must set in .env}
    ports:
      - "127.0.0.1:5672:5672"
      - "127.0.0.1:15672:15672"   # management UI
    volumes:
      - ~/.stratum/data/rabbitmq:/var/lib/rabbitmq

  # stratum-main 不容器化, 直接跑 Python (开发期方便 debug)
  # production 期可以容器化

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
```

#### 1.3.5 启动顺序

```bash
# 1. 准备 .env (敏感配置)
cat > ~/projects/stratum/.env <<'EOF'
POSTGRES_PASSWORD=<生成强密码>
RABBITMQ_PASSWORD=<生成强密码>
DEEPSEEK_API_KEY=<your_key>
ANTHROPIC_API_KEY=<your_key>
DASHSCOPE_API_KEY=<your_key>
EOF
chmod 600 ~/projects/stratum/.env

# 2. 启动基础服务
cd ~/projects/stratum
docker compose -f docker-compose.layer-a.yml up -d

# 3. 等服务 ready
sleep 10
docker compose -f docker-compose.layer-a.yml ps
# 期待: postgres / redis / rabbitmq 全 healthy / running

# 4. 初始化 Stratum
stratum init

# 5. 验证 (Phase 1 端到端 demo)
echo "测试笔记" > ~/.stratum/inbox/test.md
python -m omodul.knowledge.process_inbox
python -m oskill.knowledge.hybrid_search "测试"

# 6. 启动 MCP server (供 Claude Desktop / Hermes 调用)
python -m omodul.knowledge.start_mcp_server
```

#### 1.3.6 日常运维

```bash
# 重启
docker compose -f docker-compose.layer-a.yml restart

# 看日志
docker compose -f docker-compose.layer-a.yml logs -f stratum-postgres

# 备份 (Phase 2 前手动)
tar czf ~/stratum-backup-$(date +%Y%m%d).tar.gz \
  ~/.stratum/data/ ~/.stratum/index/ ~/.stratum/_archive/

# 升级 oprim/oskill/omodul (Phase X 完工时)
cd ~/projects/platform/oprim && git pull && pip install -e .
cd ~/projects/platform/oskill && git pull && pip install -e .
cd ~/projects/platform/omodul && git pull && pip install -e .
```

### §1.4 Phase 2 启动: GDrive 同步集成

简述 (详细等 Phase 2 完工再补):

#### 1.4.1 GDrive OAuth 凭证准备

(引用 advisor 给 Wiki 的 OAuth 申请文档, 不重复)

```bash
# OAuth JSON 放置
~/.stratum/secrets/gdrive_oauth.json
chmod 600 ~/.stratum/secrets/gdrive_oauth.json
```

#### 1.4.2 首次授权 (一次性)

```bash
# Phase 2 完工后跑
python -m omodul.sync.bg_sync --user-id=wiki --device-id=laptop_wiki --auth-only
# 浏览器自动开 OAuth 同意页, 授权后 token 自动保存
```

#### 1.4.3 切换 config 主存储

```yaml
# ~/.stratum/config.yaml
storage:
  primary: gdrive   # 从 local 切到 gdrive
  gdrive:
    oauth_config: ~/.stratum/secrets/gdrive_oauth.json
    root_folder: /Stratum
```

#### 1.4.4 启动后台同步

```bash
python -m omodul.sync.bg_sync --user-id=wiki --device-id=laptop_wiki &
```

(详细等 Phase 2 完工)

### §1.5 Phase 11+ 启动: Layer B 主机 GPU 外挂 (前置准备)

引用 ADR-021 §1.9 启动条件 6 项, 落地为可执行清单。

#### 1.5.1 Wiki 行动清单

| # | 任务 | 估时 | 状态 |
|---|---|---|---|
| 1 | Tailscale mesh 已配 | (已完成) | ✅ |
| 2 | 笔记本 ping 主机 Tailscale IP | 5 min | ⏳ |
| 3 | 主机 Ollama 安装 + qwen3:14b-q4 拉取 | 30 min | ⏳ |
| 4 | 主机 Docker GPU runtime 配置 (nvidia-container-runtime) | 30 min | ⏳ |
| 5 | 笔记本 STRATUM_*_HOST 环境变量 (示例见下) | 5 min | ⏳ |

#### 1.5.2 主机 Ollama 安装 (Wiki 跑)

```bash
# 主力机 Windows + WSL2
# 在 WSL2 内安装 Ollama (能用 GPU)
curl -fsSL https://ollama.com/install.sh | sh

# 拉模型 (~5 GB Q4)
ollama pull qwen3:14b-q4

# 配置 0.0.0.0 listen (默认只 localhost)
# 编辑 /etc/systemd/system/ollama.service.d/override.conf
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama

# 验证
curl http://localhost:11434/api/tags
# 期待返回 qwen3:14b-q4 在列
```

#### 1.5.3 笔记本验证跨机调用

```bash
# 从笔记本 (Layer A) 调主机 Ollama
TAILSCALE_HOST=stratum-host.ts.net   # 替换实际 magic DNS
curl http://$TAILSCALE_HOST:11434/api/generate -d '{
  "model": "qwen3:14b-q4",
  "prompt": "hello",
  "stream": false
}'

# 期待返回 JSON 含 response 字段
```

如果超时, 检查:
1. Tailscale 状态: `tailscale status`
2. 主机防火墙: 允许 11434 端口
3. Ollama listen 0.0.0.0: `ss -tlnp | grep 11434`

#### 1.5.4 笔记本环境变量

```bash
# ~/.bashrc 或 ~/.zshrc
# Phase 11 启动前才需要
export STRATUM_OLLAMA_HOST=http://stratum-host.ts.net:11434
export STRATUM_WHISPER_HOST=http://stratum-host.ts.net:9000   # Phase 11 启动后
export STRATUM_TTS_HOST=http://stratum-host.ts.net:9001
export STRATUM_SD_HOST=http://stratum-host.ts.net:9002
```

### §1.6 故障恢复

#### 1.6.1 stratum-main 崩溃

```bash
# 重启
docker compose -f docker-compose.layer-a.yml restart

# 检查日志
docker compose logs --tail=100 stratum-postgres
```

#### 1.6.2 LanceDB 索引损坏

```bash
# 备份现有索引
mv ~/.stratum/index ~/.stratum/index.bad-$(date +%s)

# 重建索引 (Phase 1 omodul 已实施)
python -m omodul.knowledge.rebuild_index
```

#### 1.6.3 GDrive token 过期 (Phase 2 后)

```bash
# 删除过期 token, 触发重新授权
rm ~/.stratum/secrets/gdrive_token.json
python -m omodul.sync.bg_sync --user-id=wiki --device-id=laptop_wiki --auth-only
```

#### 1.6.4 笔记本完全损坏 — 从 GDrive 恢复 (Phase 2 后)

```bash
# 新设备
stratum init --device-id=laptop_wiki_new
# 配 gdrive_oauth.json
python -m oskill.sync.restore_from_snapshot --user-id=wiki
# 等下载完成 (取决于网盘速度 + 数据量)
```

#### 1.6.5 Tailscale mesh 断 (Phase 11 后影响外挂)

```bash
# 笔记本端
tailscale status      # 看 host 节点状态
tailscale up          # 重新连
```

Stratum 主体跑 degraded mode: 翻译 / TTS / SD 任务排队等恢复 (circuit breaker 触发)。

### §1.7 安全 + 隐私清单

引用 SPEC §13:

- [ ] OAuth secrets 文件权限 600 (`chmod 600 ~/.stratum/secrets/*.json`)
- [ ] .env 文件权限 600
- [ ] Postgres / Redis / RabbitMQ 端口仅 127.0.0.1 bind, 不暴露 LAN
- [ ] Tailscale ACL 限定 Stratum 节点之间 (不开公网)
- [ ] substrate 内容仅在 Layer A + GDrive, 不进 Layer B
- [ ] 外挂调用临时数据不持久化 (转录中间结果 / TTS 输入 / SD prompt)
- [ ] 外挂日志只记元数据 (任务 ID / 耗时), 不记内容
- [ ] backup 文件加密 (Phase 5 商业化时考虑, v1.0 单用户暂不强制)

### §1.8 监控 + 告警 (v1.0 minimal)

```bash
# 容器健康检查
docker compose -f docker-compose.layer-a.yml ps

# 磁盘空间监控 (cron)
0 6 * * * df -h ~/.stratum | awk '$5 > 80 {print "Disk warning"}' | \
  mail -s "Stratum disk" wiki@example.com

# Postgres 慢查询日志 (默认开)
```

完整可观测栈 (Prometheus + Grafana + Loki) 在 helios-platform 已有, 接入是 Phase 11+ 工作。

### §1.9 已知问题 + 限制

引用 ADR / Phase 完工偏差:

- async provider 已实施 (ADR-020 偿还), 但 sync wrapper 仍可用 1 版本 (Phase 11 后正式删)
- Phase 1.5 hybrid_search mode=augmented 当前不调 LLM 兜底 (Phase 11+ 实施)
- Phase 11+ 外挂 GPU 调度未实施 (Q15 未决)
- WSL2 6.8+ kernel + Tailscale 需 TS_USERSPACE=true (ADR-021 调研发现)

### §1.10 版本对应表

| Stratum 整体版本 | oprim | oskill | omodul | 完工时间 | 主要功能 |
|---|---|---|---|---|---|
| Phase 1 (v0.1) | 2.2.0 | 2.3.0 | 1.2.0 | 2026-05-18 | 4O 基础 + MCP server |
| Phase 1.5 (v0.2) | 2.3.1 | 2.4.0 | 1.2.2 | 2026-05-18 | pin/unpin + citation + mode |
| Phase 10 (v0.3) | 2.5.0 | 2.5.0 | 1.2.2 | 2026-05-19 | Translation (async) |
| Phase 2 (v0.4) | TBD | TBD | TBD | TBD | GDrive + 同步 |
| Phase 11 (v1.0) | TBD | TBD | TBD | TBD | Agent + Scheduled + 外挂 |

---

## §2 Wave 工作流程

### Wave 0: 准入检查 (10 分钟)

```bash
cd ~/projects/stratum/docs/
ls -la
# 如已有 README.md / SPEC.md 等, 不动它们
# DEPLOYMENT.md 应不存在 (本次新建)
```

### Wave 1: 撰写 DEPLOYMENT.md (6-8 小时)

按 §1.1 ~ §1.10 章节顺序撰写。

工程化语言, 不灌水。重点章节:
- §1.3 (Layer A 当前部署) — 最重要, Wiki 马上要用
- §1.4 (Phase 2 GDrive 集成) — 占位 + 框架, 详细等 Phase 2 完工
- §1.5 (Phase 11 准备) — Wiki 行动清单 + 实证脚本
- §1.6 (故障恢复) — 实战脚本

### Wave 2: 验证脚本可执行性

不实际跑 (因为环境可能不够), 但**确保脚本语法正确**:

```bash
# 用 bash -n 检查所有 bash 脚本语法
grep -oP '```bash\n\K[^`]+(?=\n```)' docs/DEPLOYMENT.md | \
while IFS= read -r script; do
  echo "$script" | bash -n && echo "OK" || echo "SYNTAX ERROR"
done

# 用 yaml-lint 检查所有 yaml 块语法
grep -oP '```yaml\n\K[^`]+(?=\n```)' docs/DEPLOYMENT.md | \
while IFS= read -r yaml; do
  echo "$yaml" | python -c "import yaml, sys; yaml.safe_load(sys.stdin)" && echo "OK" || echo "YAML ERROR"
done
```

### Wave 3: commit + 完工报告

```bash
git add docs/DEPLOYMENT.md
git commit -m "docs: Stratum deployment guide (Layer A current + Phase 2/11 prep)

Covers:
- Preflight checks
- docker-compose.layer-a.yml + .env template
- ~/.stratum/config.yaml template
- Phase 2 GDrive integration (placeholder)
- Phase 11 主机 Ollama / 外挂前置 (Wiki action list)
- Failure recovery scripts
- Security + privacy checklist
- Version compatibility matrix

References ADR-016/019/021 (tri-machine topology decisions)."
git push
```

---

## §3 完工报告格式

```
=== Stratum DEPLOYMENT.md 完工报告 ===

文件: docs/DEPLOYMENT.md
行数: <数>
章节: §1.1 ~ §1.10 全部完成

核心可执行内容:
- preflight.sh 检查脚本
- docker-compose.layer-a.yml 模板
- ~/.stratum/config.yaml 完整模板
- Phase 11 Wiki 行动清单 (5 项)
- 主机 Ollama 安装步骤
- 故障恢复脚本 (5 场景)
- 安全清单 (8 项)
- 版本对应表 (5 个 Phase)

脚本语法验证:
- bash 块: <N>/通过
- yaml 块: <N>/通过

commit: <hash>

后续 Wiki 可直接按 §1.3 部署 Layer A.
Phase 11 启动前按 §1.5 跑 Wiki 行动清单.
```

---

## §4 异常处理

立即停止 + 报告:
- ADR-016 / ADR-019 / ADR-021 内容跟 docs/decisions/ 实际不符 (说明 advisor 文档跟 repo 不一致)
- Phase 1 / 10 / 1.5 完工事实跟 DEPLOYMENT 描述无法对齐
- docker-compose 模板有真实结构性错误 (yaml 语法 / Docker spec 不存在的字段)

非阻塞:
- 个别脚本可能在 Wiki 真跑时需要微调 (e.g. WSL2 路径), 留备注
- 主机 Ollama 实际版本号可能跟示例不一致

---

**预估工程量**: 1 天 FULL AUTO

Wave 0: 10 分钟
Wave 1: 6-8 小时 (主文档)
Wave 2: 30 分钟 (语法验证)
Wave 3: 完工

---

**End of STRATUM_DEPLOYMENT_DOC_INSTRUCTIONS_v0.1.md**
