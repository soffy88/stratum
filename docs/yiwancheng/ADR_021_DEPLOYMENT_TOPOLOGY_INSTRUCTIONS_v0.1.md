# ADR_021_DEPLOYMENT_TOPOLOGY_INSTRUCTIONS_v0.1.md

**任务**: 撰写 ADR-021 — Stratum 跨机部署拓扑 (Phase 11 准入关键决策)
**执行者**: 任一空闲 CC (推荐刚完工 ADR-020 重构的 CC, 上下文连贯)
**执行模式**: Claude Code FULL AUTO (设计决策类, 不实施代码)
**触发**: 
- Wiki 拍板 Stratum 部署到笔记本 (24G/4G GPU)
- 主机 10G GPU 资源闲置 → Phase 11 外挂候选机
- ADR-019 "同 Docker network 解耦集成" 在跨机场景需要修订
- Phase 11 启动前需要锁定外挂部署位置

**输出**: 单一文档 `ADR-021.md`, 写入 `~/projects/stratum/docs/decisions/`
**性质**: 设计决策类任务, **不实施代码**, 只产出 ADR + 修订其他相关 ADR
**工程量**: 1-2 天

---

## §0 工作模式

### 0.1 范围 (R-4 严格)

✅ 允许:
- 写 ADR-021 完整文档
- 引用 ADR-016 / ADR-019 (修订相关条款)
- 调研 Tailscale 跨机 Docker network 方案 (web_search if needed)
- 引用 Phase 11 4O 元素 (oprim.external.*)
- 提供 docker-compose 拓扑示例

❌ 禁止:
- 实施任何代码 (这是设计任务)
- 修改 Phase 1-10 已完工的代码
- 启动外挂部署 (Phase 11 启动后再做)
- 评估 Phase 14+ 商业化拓扑 (太远)

### 0.2 R-1 / R-2 应用

- R-1 失败不静默: 拿不准的方案 (e.g. Tailscale + Docker network 实际兼容性) 不要假装确定, 标 "待 Phase 11 启动时实证验证"
- R-2 SPEC 是真理源: ADR-019 部分条款 (同 network) 修订时, 必须显式说明哪些保留 / 哪些变更

### 0.3 输出格式

跟现有 ADR (001-020) 风格一致:
- 背景 / 决定 / 理由 / 含义 / 关联
- 工程化语言, 不阐述
- 含 docker-compose / tailscale config 示例
- 含部署决策表 (外挂 → 设备 映射)

---

## §1 ADR-021 必含章节

### 1.1 背景

- Wiki 设备拓扑校准 (2026-05-18): 笔记本 24G/4G GPU 主开发, 主机 32G/10G GPU 闲置
- Stratum Phase 11 外挂能力 (whisper / TTS / SD / searxng / hevi) 跟 GPU 需求强相关
- ADR-019 "同 Docker network" 在跨机场景需要修订
- Phase 11 启动前必须锁定外挂部署位置 + 通信方案

### 1.2 决定 (核心)

**Stratum 部署拓扑分层**:

| Layer | 设备 | 角色 | 组件 |
|---|---|---|---|
| Layer A | 笔记本 | Stratum 主体 + 轻外挂 | stratum-main, postgres, redis, rabbitmq, lancedb |
| Layer B | 主机 | 重外挂 (GPU) | whisper-large, F5-TTS, SD-webui, ollama |
| Layer C | Singapore VPS | 代理 + 备份 | sing-box, 公网 backup |

**跨机通信**: Tailscale mesh + Magic DNS

**故障域**: 各 Layer 独立, Stratum 主体永远在线 (Layer A 单点), 外挂可降级

### 1.3 外挂分配 (基于主机 10G GPU 实测能力)

具体决策表 (CC 写):
- whisper.cpp small/medium (~2G) → 主机 (Layer B), 笔记本作 fallback
- whisper.cpp large-v3 (~10G) → 仅主机
- F5-TTS (4-6G) → 主机
- fish-speech (~8-12G) → 主机紧贴极限, **不推荐**, 用 F5 替代
- stable-diffusion 1.5/2.1 (4-6G) → 主机
- SDXL (~12G) → 不部署, 用云 API 或 SD 1.5 替代
- searxng (CPU only) → 笔记本 (Layer A) 或 VPS (Layer C), 偏笔记本
- ollama qwen3-14B Q4 (~9G) → 主机, 跨机调用
- hevi → 独立, 看 hevi 经理人决定 (不归 Stratum advisor 管)

### 1.4 ADR-019 修订条款

明确指出 ADR-019 哪些保留 / 哪些变更:

**保留**:
- 解耦原则 (各外挂独立 container, 独立故障域)
- 各经理人独立 (Stratum advisor 只规范接入接口)
- 本地优先 (不依赖云 API)
- MCP 协议优先通信

**变更**:
- ❌ "同 Docker network" → ✅ "Tailscale mesh + Magic DNS"
- ❌ "同机 docker network 内网延迟 < 5ms" → ✅ "Tailscale 内网延迟 5-15ms (LAN 实测)"
- 新增: 跨 Layer 故障降级策略

### 1.5 数据流向 + 隐私

- substrate 数据始终在 Layer A + GDrive (用户网盘), 不进入 Layer B
- 外挂调用只传输**任务数据** (e.g. transcribe input audio, TTS input text), 不传 substrate 完整数据
- 外挂内不持久化任务数据, 任务完成后清理
- 跟 SPEC §13.4 一致

### 1.6 Tailscale 配置示例

```yaml
# 主机 (Layer B) Tailscale tag
tags: [tag:stratum-host]

# 笔记本 (Layer A) Tailscale tag  
tags: [tag:stratum-main]

# VPS (Layer C) Tailscale tag
tags: [tag:stratum-vps]

# ACL (Tailscale admin console)
{
  "acls": [
    { "action": "accept", "src": ["tag:stratum-main"], "dst": ["tag:stratum-host:*"] },
    { "action": "accept", "src": ["tag:stratum-main"], "dst": ["tag:stratum-vps:443"] }
  ]
}
```

Stratum 主体调用外挂时, 用 Tailscale Magic DNS:
```python
# oprim/external/whisper_client.py
WHISPER_HOST = os.environ.get("STRATUM_WHISPER_HOST", "http://stratum-host.tail-net.ts.net:9000")
```

### 1.7 docker-compose 示例 (两份)

**笔记本 (Layer A)**:
```yaml
# ~/projects/stratum/docker-compose.layer-a.yml
services:
  stratum-main:
    image: stratum/stratum-main:v2.5.0
    network_mode: host  # 简化, 直接共享 Tailscale 网络
    environment:
      STRATUM_WHISPER_HOST: "http://stratum-host.ts.net:9000"
      STRATUM_TTS_HOST: "http://stratum-host.ts.net:9001"
      STRATUM_SD_HOST: "http://stratum-host.ts.net:9002"
  postgres:
    ...
  redis:
    ...
```

**主机 (Layer B)**:
```yaml
# 主机 ~/projects/stratum-host/docker-compose.layer-b.yml
services:
  whisper:
    image: ghcr.io/ggml-org/whisper.cpp:latest
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: 1
    ports:
      - "9000:9000"
  f5-tts:
    image: <community-image>
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    ports:
      - "9001:9001"
  sd-webui:
    image: ...
    ports:
      - "9002:9002"
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
```

### 1.8 故障降级策略

| 故障场景 | Stratum 行为 |
|---|---|
| Layer B 离线 (主机关机) | Stratum 主体正常运行, TTS/SD/whisper 不可用, Agent 路由跳过外挂任务, 排队等恢复 |
| Layer C 离线 (VPS) | 仅代理不可用, 国内 API 调用受影响 |
| Layer A 离线 (笔记本) | Stratum 全停, 数据安全在 GDrive (恢复时 pull 即可) |
| Tailscale mesh 局部断 | 走降级路由, 重试 |

每个 external_client 实施 circuit_breaker (4O v0.3 §E.1 已规范), 故障 N 次后 fail-fast。

### 1.9 Phase 11 启动条件

ADR-021 决定后, Phase 11 启动条件:

1. ✅ Tailscale mesh 已配 (Wiki 已有)
2. ⏳ 笔记本能 ping 主机 Tailscale IP (实证)
3. ⏳ 主机 Ollama 服务跑通 (qwen3-14B Q4 加载成功)
4. ⏳ 外挂选型最终决定 (TTS: F5 / SD: 1.5)
5. ⏳ 主机 docker-compose 模板 ready
6. ⏳ 笔记本 STRATUM_*_HOST 环境变量配置

### 1.10 含义 (对其他文档的影响)

- **STRATUM_SPEC v0.6 PATCH §11.4**: 修订外挂能力 Docker 拓扑示意图, 加 Tailscale mesh
- **4O 清单 v0.3 §E.1**: oprim.external.* 实施时配置 base_url 通过 env var, 不硬编码 docker network
- **ADR-019**: 加 "已被 ADR-021 部分修订" 状态标注
- **SPEC v0.6 PATCH §13.4 隐私**: 加 "跨 Tailscale mesh 不出 Wiki 个人网络" 条款

### 1.11 未决问题 (Phase 11 启动前需补)

- **Q14**: hevi 部署位置 (主机 / 独立 VPS / 笔记本?) → hevi 经理人决定
- **Q15**: 主机 GPU 任务调度 — Ollama + F5-TTS + SD 共享 10G, 并发时怎么排队?
- **Q16**: 主机离线时, Scheduled Jobs (e.g. 每夜批翻译) 跑还是不跑?
- **Q17**: Tailscale 跨大陆延迟实测 (Wiki 笔记本 ↔ Singapore VPS) — 国内访问场景

### 1.12 关联

- 修订 ADR-019 (外挂能力架构, 同 network → Tailscale mesh)
- 修订 ADR-016 (本地部署, 现扩展到 "笔记本 + 主机 + VPS" 三机本地)
- 触发 SPEC v0.6 PATCH §11.4 修订
- 触发 4O v0.3 §E.1 oprim.external.* 配置规范
- Phase 11 启动前置

---

## §2 Wave 工作流程

### Wave 0: 准入检查 (10 分钟)

```bash
cd ~/projects/stratum/docs/decisions/
ls -la   # 应该已有 ADR-001 ~ ADR-020
git status
git pull
```

### Wave 1: 写 ADR-021 主体 (4-6 小时)

按 §1 章节 (1.1 ~ 1.12) 撰写, 每章节扎实, 不灌水。

Wave 1 完成报告:
```
=== Wave 1 完成 ===
- ADR-021 主文档已写 (<行数>)
- 关键决策表已含 (外挂分配 / 故障降级 / Tailscale 配置)
- docker-compose 示例 (笔记本 + 主机)
- ADR-019 修订条款明确
- commit: <hash>
```

### Wave 2: 调研验证 + 校准 (2-4 小时)

CC 在 web 上 (用 web_search) 验证以下技术点:
- Tailscale + Docker network 是否兼容 (2026 最新状态)
- F5-TTS 实际 GPU 内存占用 (跟 ADR-021 假设的 4-6G 是否一致)
- fish-speech 真实 GPU 需求 (确认是否真的 8-12G)
- whisper.cpp large-v3 在 10G GPU 上运行可行性
- Ollama qwen3:14b-q4 实际内存 (确认是否 ~9G)

如果调研结果跟 ADR-021 假设不符, 修订 ADR-021。

Wave 2 完成报告:
```
=== Wave 2 完成 ===
- 调研结果:
  - Tailscale + Docker: <发现>
  - F5-TTS GPU: <实测 / 调研数字>
  - fish-speech GPU: <数字>
  - whisper large-v3 in 10G: <可行 / 不可行>
  - ollama qwen3-14b: <数字>
- ADR-021 修订项 (如有): <list>
- commit: <hash>
```

### Wave 3: 修订相关 ADR (1 小时)

如果 ADR-021 决定需要修订 ADR-019 / ADR-016:
- 在 ADR-019 末尾加 "状态变更: 2026-05-19 被 ADR-021 部分修订" 标注 (不删原内容)
- 在 ADR-016 末尾加 "拓扑扩展: 见 ADR-021" 标注
- 不大改原 ADR (保留历史决策记录)

### Wave 4: 完工报告

```
=== ADR-021 完工报告 ===

ADR-021: Stratum 跨机部署拓扑

完工内容:
- 主文档 ADR-021.md (<行数>)
- 设备角色 + 外挂分配决策表
- ADR-019 修订条款
- docker-compose 示例 (2 份)
- 故障降级策略
- Phase 11 启动条件清单
- 4 个未决问题 (Q14-Q17)

调研结果摘要:
- <主要发现>

修订其他 ADR:
- ADR-019: 加修订标注 (不动主体)
- ADR-016: 加扩展标注

commit:
- ADR-021: <hash>
- ADR-019/016 修订: <hash>

Phase 11 启动前置条件清单:
- ⏳ Tailscale mesh ping 测试 (Wiki 跑)
- ⏳ 主机 Ollama 部署 (Wiki 跑)
- ⏳ 外挂镜像调研 (Phase 11 启动时 CC 跑)
```

---

## §3 异常处理

立即停止 + 报告:
- 调研发现 Tailscale + Docker 完全不兼容 (推翻 ADR-021 核心假设)
- 主机 GPU 实际容量跟 Wiki 校准的 10G 不符 (e.g. 实际只有 8G 或 12G)
- 笔记本拓扑跟 Wiki 之前说的不一致

非阻塞:
- 个别外挂 GPU 需求数字略有偏差 (在 ADR 里记 "估算", 不必精确)

---

**预估工程量**: 1-2 天 FULL AUTO

Wave 0: 10 分钟
Wave 1: 4-6 小时 (主文档撰写)
Wave 2: 2-4 小时 (web 调研)
Wave 3: 1 小时 (修订相关 ADR)
Wave 4: 完工报告

---

**End of ADR_021_DEPLOYMENT_TOPOLOGY_INSTRUCTIONS_v0.1.md**
