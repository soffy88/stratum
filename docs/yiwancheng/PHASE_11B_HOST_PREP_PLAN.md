# Phase 11B 主机准备路线图

生成时间: 2026-05-21  
基于 ADR-021 §Phase 11 启动前置条件

---

## Step 1 侦测结果

### A. Tailscale 状态

```
节点                  IP               OS       状态
wsl-main-1           100.69.31.109    linux    在线 (当前 WSL2，CC 运行处)
desktop-volbggk      100.114.154.113  windows  在线 (同一台物理机 Win11 侧)
singapore-vps        100.73.220.5     linux    active, direct (Layer C)
iphone-15-plus       100.92.24.106    iOS      offline 26d
soffy-1              100.94.76.122    windows  offline 274d
sonkimi12i7          100.84.127.67    windows  offline 240d
```

**关键发现**: CC 运行在 WSL2 (Ubuntu 24.04) **内部**，宿主机即为 DESKTOP-VOLBGGK (RTX 3080 10G，32GB RAM)。
"笔记本 → 主机" 路径 = WSL2 直接本地访问，无需 Tailscale hop，无需 SSH。

### B. SSH 可达性

CC 已在主机 WSL2 内部，无需远程 SSH 即可执行部署操作。  
SSH server (sshd): inactive (已 enabled，但 systemd 未完全拉起)。  
→ **CC 可直接本地操作，标"CC 可本机操作"**。

### C. 主机环境侦测结果

```
OS/硬件:
  主机名:          DESKTOP-VOLBGGK
  GPU:             NVIDIA GeForce RTX 3080
  VRAM:            10240 MiB (10G)
  NVIDIA Driver:   591.86 (Windows) / SMI 590.57
  CUDA 版本:       13.1
  RAM:             31.8 GB (≈ 32G)

WSL2:
  Distro:          Ubuntu-24.04 (Running, Version 2)
  Kernel:          6.6.114.1-microsoft-standard-WSL2
  systemd:         enabled (wsl.conf [boot] systemd=true)
  /dev/dxg:        present (WSL2 GPU 透传正常)
  GPU from WSL2:   nvidia-smi 可用 ✅

Docker:
  版本:            29.4.3
  NVIDIA runtime:  ❌ 未配置 (仅 runc)
  nvidia-container-toolkit: ❌ 未安装

Ollama:            ❌ 未安装

GPU 驱动模式:      WDDM (Windows Display Driver Model) — 主机正常
```

---

## ADR-021 §Phase 11 启动前置条件 — 当前状态

| # | 条件 | 当前状态 | 执行者 |
|---|------|----------|--------|
| 1 | Tailscale mesh 已配置 (三台设备入 tailnet) | ✅ WSL2 + Win11 + VPS 均在 | — |
| 2 | 笔记本能 ping/curl 主机 Tailscale IP，延迟 < 20ms | ✅ CC 本机即主机 (无跨机 hop) | — |
| 3 | 主机 Ollama 服务跑通 (qwen3:14b-q4 加载，/api/generate 返回正确) | ❌ **阻塞** | Wiki + CC |
| 4 | 外挂镜像最终选型确定 (F5-TTS / SD / whisper.cpp) | ⏳ Phase 11 启动时 CC 出方案 | CC |
| 5 | docker-compose.layer-b.yml 模板 ready (ollama + whisper 验证) | ⏳ Phase 11 启动时 CC 写 | CC |
| 6 | 笔记本 .env 中配置 STRATUM_*_HOST 环境变量 | ⏳ Phase 11 启动时 | Wiki + CC |

---

## 路线表 — 三栏

| 项 | CC 能做 (WSL2 本机) | Wiki 手动 | 状态 |
|----|---------------------|-----------|------|
| **nvidia-container-toolkit 安装** | `curl \| sudo apt install nvidia-container-toolkit` + `sudo systemctl restart docker` | 无需手动 | ❌ 待做 |
| **Docker NVIDIA runtime 配置** | `nvidia-ctk runtime configure --runtime=docker` | 无需手动 | ❌ 待做 |
| **验证 `docker run --gpus all` 可用** | `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi` | 无需手动 | ❌ 待做 |
| **Ollama 安装** | `curl -fsSL https://ollama.com/install.sh \| sh` (WSL2 内) 或 Windows 安装器 | 若选 Windows 安装: 下载 OllamaSetup.exe | ❌ 待做 |
| **Ollama 模型拉取** | `ollama pull qwen3:14b-q4_k_m` | 无需手动 (约 8.3G，需等待) | ❌ 待做 |
| **Ollama /api/generate 验证** | `curl http://localhost:11434/api/generate -d '{"model":"qwen3:14b-q4_k_m","prompt":"hi","stream":false}'` | 无需手动 | ❌ 待做 |
| **docker-compose.layer-b.yml 写** | CC 根据 ADR-021 §Layer B 模板写 | 无需手动 | ⏳ Phase 11 启动时 |
| **Windows Hyper-V / Containers 功能验证** | ❌ 需管理员 PS | `Get-WindowsOptionalFeature -Online \| Where {$_.FeatureName -match 'Hyper\|Container'}` (管理员 PS) | ⏳ Wiki 配合 Step 1C |
| **wsl --status / wsl -l -v (Windows 侧)** | 已从 WSL2 内获取 (Ubuntu-24.04 v2 Running) | 已确认 | ✅ |
| **.env STRATUM_*_HOST 配置** | CC 写 .env 模板，填入 `127.0.0.1` (本机) | Wiki 确认端口 | ⏳ Phase 11 启动时 |
| **STRATUM_HOST 端口规划** | CC 出端口表 (ollama:11434, whisper:8178, tts:8880, sd:7860) | 确认无冲突 | ⏳ Phase 11 启动时 |
| **GPU 内存实测 (并发约束)** | 拉起各服务后 `nvidia-smi` 记录占用 | 无需手动 | ⏳ Phase 11 GPU 测试时 |

---

## 关键路径 (到 Phase 11B Gate)

```
[现在]
  ↓
Step 1C: Wiki 跑 PowerShell admin 命令 (Hyper-V/Containers 功能确认)
  ↓
CC: 安装 nvidia-container-toolkit + 配置 Docker NVIDIA runtime (5 min)
  ↓
CC: 安装 Ollama (WSL2 内) (2 min)
  ↓
CC/Wiki: 拉取 qwen3:14b-q4_k_m 模型 (~8.3G，网速决定时间)
  ↓
CC: 验证 /api/generate 端到端 (前置条件 #3 ✅)
  ↓
Phase 11B 准入门 OPEN → CC 启动 Phase 11B 实施
```

---

## Step 1C — Wiki 需在 Windows 跑的命令

请在 **Windows PowerShell (管理员)** 跑以下命令，将输出粘贴给 CC：

```powershell
# 1. Hyper-V 和 Containers 功能
Get-WindowsOptionalFeature -Online | Where-Object {$_.FeatureName -match 'Hyper|Container|WSL'} | Select-Object FeatureName, State | Format-Table -AutoSize

# 2. Docker Desktop 版本 (若已装)
docker version 2>$null | Select-String "Version|Engine"

# 3. NVIDIA GPU (Windows 侧)
(Get-WmiObject Win32_VideoController | Where-Object {$_.Name -match 'NVIDIA'}).Name

# 4. Tailscale IP (Windows 侧确认)
tailscale ip
```

---

*文档路径: `/home/soffy/projects/stratum/PHASE_11B_HOST_PREP_PLAN.md`*
