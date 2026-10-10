# BU2-CLOUD-INFERENCE-UNBLOCK-003: Final Report

## Executive Summary

**BLOCKED** — All cloud inference paths are either unavailable or too slow for production use. The NVIDIA NIM provider works but is extremely slow (>2 min/request), causing BU2 pipeline timeouts. DeepSeek API key is invalid, Anthropic/OpenAI keys not configured.

---

## 1. Current State

### Infrastructure
| Component | Status | Details |
|-----------|--------|---------|
| Ollama (CPU) | ✅ Running | 172.19.0.1:11434, llama3.2:1b & 3b |
| NVIDIA NIM | ⚠️ **WORKING BUT SLOW** | ~2-3 min/request, causes 300s timeouts |
| DeepSeek API | ❌ Invalid Key | "Authentication Fails" |
| Anthropic API | ❌ No Key | ANTHROPIC_API_KEY not set |
| OpenAI/NIM | ❌ No Keys | Not configured |
| Proxy/Network | ❌ Blocks External | sing-box intercepts 172.19.0.1:* |

### Books Status
| Book | ID | BU2 Status | P13 Synthesis |
|------|-----|------------|---------------|
| Thomas Calculus 14e | 01KWRXP646FQEPPRPHS3R617MZ | ✅ VERIFIED | ✅ Persisted |
| Principles of Macro 3e | 01KX8VF4V24YEQNK1GG72HTBD1 | ⚠️ PARTIAL (50%) | ❌ Pending |

### Latest BU2 Run (v7)
- **Run ID**: `br_01M4FJMFHNXCJDHE4YKN3T5569`
- **Coverage**: 50% (1/2 chapters)
- **Chapter 1**: TIMEOUT after 300s (NIM)
- **Chapter 2**: SUCCESS (NIM)

---

## 2. Root Causes

### Primary: NIM API Too Slow
- **Model**: `meta/llama-3.2-90b-vision-instruct` (90B params)
- **Latency**: ~2-3 minutes per request
- **Timeout**: 300s default → increased to 600s (still insufficient)
- **Impact**: BU2 chapter processing times out → 50% coverage

### Secondary: Invalid Cloud Credentials
| Provider | Status | Issue |
|----------|--------|-------|
| DeepSeek | ❌ | "Authentication Fails" (key in aii/aii/.env invalid) |
| Anthropic | ❌ | ANTHROPIC_API_KEY not configured |
| OpenAI | ❌ | OPENAI_API_KEY not set |
| NIM | ⚠️ | Works but extremely slow |

### Infrastructure: Proxy Blocks External
- **sing-box** at 172.19.0.1:10808 intercepts ALL 172.19.0.1:* traffic
- Intercepts Ollama (11434) and external APIs
- no_proxy includes 172.19.0.1 but **still intercepts port 11434 and external domains**
- No root access to modify sing-box config

---

## 3. Phase Results

| Phase | Task | Status | Evidence |
|-------|------|--------|----------|
| **0** | Protect v4 DRAFT | ✅ | Task history preserved |
| **1** | Fix DeepSeek Creds | ❌ | Key invalid, no replacement |
| **2** | Fix Network Path | ❌ | Proxy blocks, no root access |
| **3** | Verify Provider Config | ⚠️ | NIM works but too slow |
| **4** | Backup Providers | ❌ | No valid Anthropic/OpenAI keys |
| **5** | BU2 Recovery | ⚠️ | 50% coverage, chapter 1 timeout |
| **6** | P13 Synthesis | ❌ | Blocked on BU2 VERIFIED |
| **7** | P14 E2E | ❌ | Blocked on Book 2 BU2 |

---

## 4. Verification Commands

```bash
# Test NIM provider (slow but works)
curl --noproxy '*' -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer ***REMOVED***" \
  -d '{"model": "meta/llama-3.2-90b-vision-instruct", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50}' \
  https://integrate.api.nvidia.com/v1/chat/completions

# Check BU2 runs
docker exec stratum-sl python3 -c "
from stratum.db import query
rows = query(\"SELECT id, run_id, substrate_id, version, status, coverage_score FROM stratum.book_understandings_v2 WHERE substrate_id = '01KX8VF4V24YEQNK1GG72HTBD1' ORDER BY created_at DESC LIMIT 5\")
for r in rows: print(f'{r[\"id\"]} | {r[\"run_id\"]} | v{r[\"version\"]} | {r[\"status\"]} | cov:{r[\"coverage_score\"]}')
"

# Test NIM provider directly
cd /data/soffy/projects/stratum/deploy && docker exec stratum-sl python3 -c "
from stratum.services.bu_v2_provider import resolve_provider
provider = resolve_provider('nim', model='meta/llama-3.2-90b-vision-instruct')
result = provider.complete('Hello', max_tokens=10)
print(result.text)
"
```

---

## 5. Gate Status

| Gate | Requirement | Status | Evidence |
|------|-------------|--------|----------|
| **G0** Baseline | Git, env, DB, WIP | ✅ | Documented |
| **G1** Service | Ollama stable, API reachable | ✅ | Verified |
| **G2** CPU Inference | Model loads, generates | ❌ | 2-3 tok/sec (too slow) |
| **G3** Cloud Inference | NIM works, returns data | ⚠️ | Works but 2-3 min/req |
| **G4** BU2 Book 2 | VERIFIED + persisted | ⚠️ | 50% coverage, ch1 timeout |
| **G5** P13 Book 2 | Synthesis persisted | ❌ | Needs BU2 VERIFIED |
| **G6** P14 Cross-Book | Run completes | ❌ | Needs Book 2 VERIFIED |
| **G6** API Consistency | API ↔ DB match | ✅ | Verified |
| **G7** Browser E2E | Real data visible | ❌ | Blocked on Book 2 |
| **G8** Regression | Tests pass | ✅ | 261/261 pass |

---

## 6. Required to Unblock

### Option 1: Fix NIM Latency (Best if possible)
- **Root cause**: NIM API latency ~2-3 min/request
- **Solutions**:
  1. Use smaller/faster model on NIM (e.g., `google/gemma-3-4b-it`)
  2. Optimize NIM request parameters (lower max_tokens, temperature=0)
  3. Increase timeout to 1200s (10 min) - may work but very slow

### Option 2: Valid Cloud API Keys (Fastest)
1. **DeepSeek**: Get valid API key → set `DEEPSEEK_API_KEY` + `BU2_MODEL_PROVIDER=deepseek`
2. **Anthropic**: Get key → set `ANTHROPIC_API_KEY` + `BU2_MODEL_PROVIDER=anthropic`
3. **OpenAI**: Get key → set `OPENAI_API_KEY` + `BU2_MODEL_PROVIDER=openai`

### Option 3: Proxy Fix (Infrastructure)
- Configure sing-box to bypass `api.deepseek.com`, `api.anthropic.com`, `integrate.api.nvidia.com`
- Or run Ollama inside container with direct internet access

### Option 4: GPU/Alternative Hardware (Best Performance)
- Provision RTX 3080+/4090 → 50-100 tok/s
- Apple Silicon/Metal (M-series) → 20-40 tok/s
- Cloud GPU (RunPod, Lambda, etc.)

---

## 6. Immediate Next Steps

1. **Try smaller NIM model**: Test `google/gemma-3-4b-it` or `mistralai/mistral-7b-instruct-v0.3` for speed
2. **Request valid DeepSeek key** from key owner
3. **If keys unavailable**: Provision GPU or use cloud GPU service
4. **Do NOT continue CPU-only** — 6-12h/book is unacceptable for production

---

## 7. Artifacts Preserved

| Artifact | Location |
|----------|----------|
| Ollama Service Log | `/tmp/ollama.log` |
| BU2 Run v7 | `br_01M4FJMFHNXCJDHE4YKN3T5569` (50% coverage) |
| BU2 Run v6 | `br_01M4FJ7KMBPCWC2X06YD593657` (50% coverage) |
| BU2 Run v5 | `br_01M4FGFNW10MPMJ4VDFD2K180B` (50% coverage) |
| Thomas Calculus BU | `bu_br_01M3YRFF5YWTXNJF56MS0EDEAC` (VERIFIED) |
| Crossbook Migration | `083_bu2_p14_crossbook_tables.sql` |
| Provider Config | `src/stratum/services/bu_v2_provider.py` (NIM timeout=600s) |
| NIM API Key | `docker-compose.yml` (NVIDIA_NIM_API_KEY) |
| DeepSeek Key | `aii/aii/.env` (INVALID) |
| Proxy Config | `docker-compose.yml` (NO_PROXY updated) |

---

## 8. Final Status

```yaml
BU2_CLOUD_INFERENCE_UNBLOCK_003:
  infrastructure: PARTIAL (proxy blocks, NIM slow)
  deepseek_credentials: FAIL (invalid key)
  anthropic_credentials: FAIL (no key)
  openai_credentials: FAIL (no key)
  nim_provider: WORKS_BUT_SLOW (2-3 min/req)
  cpu_fallback: FAIL (2-3 tok/s)
  book2_bu2_coverage: 50% (ch1 timeout)
  book2_p13_synthesis: BLOCKED
  p14_crossbook: BLOCKED
  regression_tests: PASS (261/261)

  final_status: BLOCKED
  primary_blocker: "NIM_LATENCY_TOO_HIGH + INVALID_CLOUD_CREDENTIALS"
  next_action: "TEST_SMALLER_NIM_MODEL OR PROVIDE_VALID_DEEPSEEK_KEY"
```
