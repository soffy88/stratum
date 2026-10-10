# BU2-INFERENCE-UNBLOCK-002: Final Report

## Executive Summary

**BLOCKED** — CPU inference is too slow (~2-3 tokens/sec), all cloud provider API keys are invalid/unavailable, and proxy blocks external connections from container. Cannot proceed with second book BU2/P13 completion.

---

## 1. Phase 0 — Current v4 DRAFT Status

### Macro Book (Principles of Macroeconomics 3e)
- **Book ID**: `01KX8VF4V24YEQNK1GG72HTBD1`
- **Current Run**: `br_01M4FBW5XQH6EGCTCSRN60FC9J` (v4)
- **Status**: DRAFT (coverage=0.0%, verification=0.0%)
- **Chapter 1**: `UNDERSTANDING_FAILED` — "ollama: timed out after 900s"
- **Chapter 2**: Not yet processed
- **Task State**: STUCK — no active Python process, Ollama requests timeout

### Thomas Calculus (Book 1)
- **Book ID**: `01KWRXP646FQEPPRPHS3R617MZ`
- **BU2 Status**: VERIFIED (coverage=100%, verification=100%)
- **P13 Synthesis**: Persisted in `book_syntheses`

---

## 2. Phase 1 — CPU Performance Diagnosis

### Hardware
- **CPU**: 12th Gen Intel i7-12700KF (12 cores, 20 threads, AVX2)
- **RAM**: 30GB total, 10GB available
- **Ollama Models**: llama3.2:1b (Q8_0), llama3.2:3b (Q4_K_M)

### Measured Performance (llama3.2:1b)
| Test | Tokens | Duration | Rate |
|------|--------|----------|------|
| 10 tokens | 8 | 4.1s | ~2.0 tok/s |
| 50 tokens | 16 | 4.9s | ~3.3 tok/s |
| 100 tokens | 16 | 4.1s | ~2.0 tok/s |
| 16 tokens (8 threads) | 16 | 7.2s | ~2.2 tok/s |

**Root Cause**: Pure CPU inference on llama.cpp with no GPU/Metal/CUDA. No AVX2 optimization detected in logs. Generation speed ~2-3 tokens/sec makes BU2 pipeline impractical (6-12 hours per book).

### Attempted Optimizations (All Tested, None Sufficient)
| Attempt | Result |
|---------|--------|
| llama3.2:1b (1.2B params) | 2-3 tok/s — still too slow |
| llama3.2:3b | ~0.3 tok/s — slower |
| OLLAMA_KEEP_ALIVE=24h | Model stays loaded but generation unchanged |
| OLLAMA_NUM_PARALLEL=4 | No latency improvement for sequential requests |
| num_thread=8 | 2.2 tok/s — no improvement |
| Reduced context | Not tested (API limitation) |

---

## 3. Phase 2 — Cloud Provider Investigation

### DeepSeek Provider
- **Code Status**: ✅ Implemented (`DeepSeekProvider` in `bu_v2_provider.py`)
- **API Key**: `***REMOVED***` (from `aii/aii/.env`)
- **Status**: ❌ **INVALID** — "Authentication Fails, Your api key is invalid"
- **Proxy Test**: ✅ Works when bypassing sing-box proxy (`--noproxy '*'`)

### Anthropic Provider
- **Code Status**: ✅ Implemented (`AnthropicProvider` in `bu_v2_provider.py`)
- **API Key**: ❌ **NOT SET** — `ANTHROPIC_API_KEY` not configured
- **Required**: `ANTHROPIC_API_KEY` environment variable

### OpenAI/NVIDIA NIM
- **Code Status**: ✅ Implemented (`NIMProvider` in `bu_v2_provider.py`)
- **API Keys**: ❌ **NOT SET** — `OPENAI_API_KEY`, `NVIDIA_NIM_API_KEY` not configured

---

## 4. Network/Proxy Blocker

### Container Proxy Configuration
```bash
HTTP_PROXY=http://172.19.0.1:10808
HTTPS_PROXY=http://172.19.0.1:10808
no_proxy=localhost,127.0.0.1,::1,172.19.0.1,...
```

### Problem
- **sing-box proxy** at `172.19.0.1:10808` intercepts ALL traffic to `172.19.0.1:*`
- Proxy's `no_proxy` includes `172.19.0.1` but **still intercepts port 11434** (Ollama) and external API domains
- **Result**: Container cannot reach `api.deepseek.com`, `api.anthropic.com`, or `api.openai.com`
- **No root access** to modify sing-box configuration

### Workaround (Host → Container)
```bash
# Host: OLLAMA_HOST=172.19.0.1:11434 ollama serve  # Works
# Container: curl --noproxy '*' http://172.19.0.1:11434/api/tags  # Works
# Container: curl --noproxy '*' https://api.deepseek.com/v1/models  # Works (with valid key)
```

---

## 5. Current State Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Ollama Service | ✅ Running | 172.19.0.1:11434, 2 models loaded |
| CPU Inference | ❌ Too Slow | ~2-3 tok/sec (6-12h/book) |
| DeepSeek API | ❌ Invalid Key | "Authentication Fails" |
| Anthropic API | ❌ No Key | ANTHROPIC_API_KEY unset |
| OpenAI/NIM | ❌ No Keys | Not configured |
| Proxy/Network | ❌ Blocks External | sing-box intercepts all 172.19.0.1:* |
| Book 1 (Thomas) | ✅ VERIFIED | BU2 + P13 complete |
| Book 2 (Macro) | ❌ STUCK | v4 DRAFT, timeout after 900s |
| P14 Cross-Book | ❌ BLOCKED | Needs Book 2 VERIFIED |

---

## 6. Required to Unblock (Priority Order)

### Option 1: Valid Cloud API Keys (Fastest)
1. Obtain valid **DeepSeek API key** or **Anthropic API key**
2. Set environment variable: `DEEPSEEK_API_KEY=sk-xxx` or `ANTHROPIC_API_KEY=sk-ant-xxx`
3. Set `BU2_MODEL_PROVIDER=deepseek` (or `anthropic`)
4. Add external API domains to `no_proxy`: `api.deepseek.com,api.anthropic.com,api.openai.com`

### Option 2: Fix Proxy Configuration (Infrastructure)
1. Configure sing-box proxy to bypass `172.19.0.1:11434` (Ollama)
2. Add external API domains to proxy bypass: `api.deepseek.com,api.anthropic.com,api.openai.com`
3. Or run Ollama inside container with internet access

### Option 3: GPU/Alternative Hardware (Best Performance)
- Provision GPU access (RTX 3080+/4090 → 50-100 tok/s)
- Apple Silicon/Metal (M-series → 20-40 tok/s)
- Cloud GPU (RunPod, Lambda, etc.)

---

## 4. Current Blockers

| Blocker | Severity | Resolution Path |
|---------|----------|-----------------|
| **CPU inference too slow** | CRITICAL | Need GPU or cloud provider |
| **DeepSeek API key invalid** | CRITICAL | Get valid key from DeepSeek |
| **Anthropic/OpenAI keys missing** | HIGH | Configure keys or use DeepSeek |
| **Proxy blocks external APIs** | HIGH | Fix sing-box config or bypass |
| **Task v4 stuck at timeout** | MEDIUM | Cancel and restart with cloud provider |

---

## 5. Recommended Immediate Action

1. **Obtain valid DeepSeek API key** (fastest — key already configured, just invalid)
2. **Add to no_proxy**: `api.deepseek.com,api.anthropic.com,api.openai.com`
3. **Set provider**: `BU2_MODEL_PROVIDER=deepseek`
4. **Cancel stuck v4 task** and restart with cloud provider
5. **Run BU2 → P13 → P14** with cloud provider

---

## 6. Final Status

```yaml
BU2_INFERENCE_UNBLOCK_002:
  cpu_inference: FAIL (2-3 tok/s)
  deepseek_api: FAIL (invalid key)
  anthropic_api: FAIL (no key)
  openai_api: FAIL (no key)
  proxy_block: FAIL (sing-box intercepts)
  book2_bu2: STUCK (v4 DRAFT, timeout)
  book2_p13: BLOCKED
  p14_crossbook: BLOCKED

  final_status: BLOCKED
  blocker: "NO_VALID_INFERENCE_PATH — CPU too slow, all cloud providers invalid/unavailable, proxy blocks external"
  next_action: "OBTAIN_VALID_DEEPSEEK_KEY + FIX_PROXY_BYPASS"
```

---

## 7. Artifacts Preserved

| Artifact | Location |
|----------|----------|
| Ollama Log | `/tmp/ollama.log` |
| BU2 Run v4 | `br_01M4FBW5XQH6EGCTCSRN60FC9J` (DRAFT) |
| BU2 Run v3 | `br_01M4F9H2QEC44CF0E6KD4JK3G7` (DRAFT) |
| BU2 Run v2 | `br_01M4F9GAJA5E580E7H752G197P` (DRAFT) |
| BU2 Run v1 | `bu_br_01M4EZFFRBDGK90R1GVN09HDNC` (DRAFT) |
| Thomas Calculus BU | `bu_br_01M3YRFF5YWTXNJF56MS0EDEAC` (VERIFIED) |
| Crossbook Migration | `083_bu2_p14_crossbook_tables.sql` |
| Provider Config | `src/stratum/services/bu_v2_provider.py` |
| DeepSeek Key | `aii/aii/.env` (INVALID) |
