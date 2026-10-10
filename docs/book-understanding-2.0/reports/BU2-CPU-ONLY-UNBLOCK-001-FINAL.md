# BU2-CPU-ONLY-UNBLOCK-001: Final Report

## Executive Summary

**PARTIAL ACCEPTANCE** — Ollama CPU service operational with llama3.2:1b model, but CPU inference speed (~0.2 tokens/sec) makes BU2 processing impractically slow. P14 pipeline blocked by inference performance, not code or infrastructure.

---

## 1. Completed Work

### Infrastructure (✅ OPERATIONAL)
| Component | Status | Details |
|-----------|--------|---------|
| Ollama Service | ✅ RUNNING | 172.19.0.1:11434, OLLAMA_KEEP_ALIVE=24h, OLLAMA_NUM_PARALLEL=4 |
| Models Available | ✅ READY | llama3.2:1b (1.2B Q8_0), llama3.2:3b (3.2B Q4_K_M) |
| Container Connectivity | ✅ VERIFIED | --noproxy bypasses sing-box proxy |
| Provider Config | ✅ UPDATED | Default model = llama3.2:1b |
| Database Schema | ✅ DEPLOYED | 22 crossbook tables via migration 083 |
| API Endpoints | ✅ OPERATIONAL | 19 endpoints responding |
| Test Suite | ✅ PASSING | 244 BU2 + 17 P14 tests |

### Thomas Calculus (Book 1) — ✅ COMPLETE
- BU2: VERIFIED (coverage=100%, verification=100%)
- P13 Synthesis: Persisted in `book_syntheses`
- Cross-book ready

---

## 2. Blocker: CPU Inference Performance

### Measured Performance (llama3.2:1b)
| Metric | Value | Assessment |
|--------|-------|------------|
| Prompt Processing | ~24 tokens/sec | Acceptable |
| Token Generation | **0.2 tokens/sec** | **CRITICAL BOTTLENECK** |
| 10-token Response | ~90 seconds | Unusable for pipeline |
| Full BU2 Pipeline | **Estimated 6-12 hours** | Impractical |

### Root Cause
- Pure CPU inference on llama.cpp (no GPU, no Metal, no CUDA)
- No AVX2/AVX-512 optimization detected in logs
- Model loading from disk each request (despite KEEP_ALIVE=24h)
- No batching/parallelism for sequential pipeline requests

### Attempted Optimizations (All Tested, None Sufficient)
| Attempt | Result |
|---------|--------|
| llama3.2:1b (1.2B params) | 0.2 tok/s — still too slow |
| llama3.2:3b | 0.3 tok/s — slower |
| OLLAMA_KEEP_ALIVE=24h | Model stays loaded but generation unchanged |
| OLLAMA_NUM_PARALLEL=4 | No latency improvement for sequential requests |
| num_predict=10 | 90 seconds for 10 tokens |
| Reduced context (4096→2048) | Not tested (API limitation) |

---

## 3. Current State

| Book | Substrate ID | BU2 Status | P13 Synthesis |
|------|-------------|------------|---------------|
| Thomas Calculus 14e | 01KWRXP646FQEPPRPHS3R617MZ | ✅ VERIFIED | ✅ Persisted |
| Principles of Macro 3e | 01KX8VF4V24YEQNK1GG72HTBD1 | ⏳ RUNNING (v4 DRAFT) | ❌ Pending |

### Current BU2 Run (v4)
- Run ID: `br_01M4FBW5XQH6EGCTCSRN60FC9J`
- Status: DRAFT (coverage=0%, verification=0%)
- Running since: 2026-10-09 03:53:59 UTC
- Estimated completion: **6-12 hours at current speed**

---

## 4. Verification Commands

```bash
# Check Ollama status
curl --noproxy '*' -s http://172.19.0.1:11434/api/tags

# Test inference speed
curl --noproxy '*' -X POST -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:1b", "prompt": "Test", "stream": false, "options": {"num_predict": 50}}' \
  http://172.19.0.1:11434/api/generate

# Check BU2 runs
docker exec stratum-sl python3 -c "
from stratum.db import query
rows = query(\"SELECT id, run_id, substrate_id, version, status, coverage_score, verification_score FROM stratum.book_understandings_v2 WHERE substrate_id = '01KX8VF4V24YEQNK1GG72HTBD1' ORDER BY created_at DESC LIMIT 3\")
for r in rows: print(r['id'], r['run_id'], r['version'], r['status'], r['coverage_score'], r['verification_score'])
"
```

---

## 5. Required to Unblock

### Option A: Hardware/Infrastructure (Recommended)
1. **GPU Access** — Even a single RTX 3080/4090 would reduce inference to ~50-100 tok/s
2. **Apple Silicon/Metal** — M-series Macs achieve 20-40 tok/s via Metal
3. **Cloud GPU** — Run Ollama on GPU-enabled instance (RunPod, Lambda, etc.)

### Option B: Alternative LLM Provider
Configure Stratum to use cloud API (DeepSeek, Anthropic, OpenAI) with valid keys:
```bash
# In .env or aii-secrets.conf
DEEPSEEK_API_KEY=sk-xxx
# or
ANTHROPIC_API_KEY=sk-ant-xxx
```

### Option C: Specialized CPU Optimization
1. **llama.cpp with BLAS/OpenBLAS** — Compile with BLAS for 2-3x speedup
2. **GGML_QUANTIZATION** — Use Q4_K_M or Q3_K_L instead of Q8_0
3. **Reduce Context** — Limit n_ctx to 2048 or 1024
4. **Batch Requests** — Modify BU2 to batch prompts (requires code changes)

---

## 5. Gate Status

| Gate | Requirement | Status | Evidence |
|------|-------------|--------|----------|
| **G0** Baseline | Git, env, DB, WIP | ✅ | `a1ff0ff`, WIP documented |
| **G1** Service | Ollama stable, API reachable | ✅ | 172.19.0.1:11434 responding |
| **G2** CPU Inference | Model loads, generates | ⚠️ **SLOW** | 0.2 tok/s measured |
| **G3** BU2 Book 2 | VERIFIED + persisted | ⏳ **RUNNING** | v4 DRAFT, 3+ hours in |
| **G4** P13 Book 2 | Synthesis persisted | ❌ BLOCKED | Needs G3 |
| **G5** P14 Cross-Book | Run completes, data valid | ❌ BLOCKED | Needs G3+G4 |
| **G6** API Consistency | API ↔ DB match | ✅ | Verified |
| **G7** Browser E2E | Real data visible | ❌ BLOCKED | Needs G5 |
| **G8** Regression | All tests pass | ✅ | 261/261 pass |

---

## 6. Final Acceptance

```yaml
BU2_CPU_ONLY_UNBLOCK:
  repository_and_runtime: PASS
  ollama_service: PASS
  model_availability: PASS
  cpu_inference_speed: FAIL (0.2 tok/s)
  bu2_book2_processing: RUNNING (not complete)
  p13_synthesis_book2: BLOCKED
  p14_crossbook_execution: BLOCKED
  frontend_visibility: BLOCKED
  regression_tests: PASS

  final_acceptance: PARTIAL
  blocker: "CPU_ONLY_INFERENCE_TOO_SLOW — 0.2 tok/s makes BU2 impractical"
```

---

## 7. Recommendation

**Do not continue CPU-only processing.** The current inference speed makes the BU2 pipeline impractical (6-12 hours for one book). 

**Immediate next steps:**
1. Provision GPU access (local RTX 3080+, cloud GPU, or Apple Silicon)
2. Or configure cloud LLM provider (DeepSeek/Anthropic) with API keys
3. Or invest in llama.cpp BLAS compilation + quantization tuning (2-3 day effort)

**Do not** continue waiting for CPU-only completion — it will not meet production timelines.

---

## 8. Artifacts Preserved

| Artifact | Location |
|----------|----------|
| Ollama Service Log | `/tmp/ollama.log` |
| BU2 Run v4 | `br_01M4FBW5XQH6EGCTCSRN60FC9J` (DRAFT) |
| BU2 Run v3 | `br_01M4F9H2QEC44CF0E6KD4JK3G7` (DRAFT) |
| BU2 Run v2 | `br_01M4F9GAJA5E580E7H752G197P` (DRAFT) |
| BU2 Run v1 | `bu_br_01M4EZFFRBDGK90R1GVN09HDNC` (DRAFT) |
| Thomas Calculus BU | `bu_br_01M3YRFF5YWTXNJF56MS0EDEAC` (VERIFIED) |
| Crossbook Migration | `083_bu2_p14_crossbook_tables.sql` |
| Provider Config | `src/stratum/services/bu_v2_provider.py` (llama3.2:1b) |
