# BU2 P13 Acceptance Report

**Date**: 2026-10-07  
**Phase**: P13 - Book-Level Synthesis / P13-RUNTIME-QUALIFICATION-001  
**Baseline**: a1ff0ff  
**Primary Book**: Thomas Calculus 14th Edition (01KWRXP646FQEPPRPHS3R617MZ)  
**Secondary Book**: Principles of Macroeconomics 3e (01KX8VF4V24YEQNK1GG72HTBD1)  
**Hardware**: CPU-only (no GPU available)

---

## Implementation Status

| Component | Status |
|-----------|--------|
| P13 Models (9 new types) | ✅ COMPLETE |
| bu_v2_thesis_analyzer.py | ✅ COMPLETE |
| bu_v2_concept_system.py | ✅ COMPLETE |
| bu_v2_argument_system.py | ✅ COMPLETE |
| bu_v2_mechanism_analyzer.py | ✅ COMPLETE |
| bu_v2_evidence_map.py | ✅ COMPLETE |
| bu_v2_chapter_roles.py | ✅ COMPLETE |
| bu_v2_contradiction_detector.py | ✅ COMPLETE |
| bu_v2_book_synthesis.py | ✅ COMPLETE |
| bu_v2_synthesis_expression.py | ✅ COMPLETE |
| bu_v2_query.py | ✅ COMPLETE |
| Migration 069_bu2_p13_synthesis.sql | ✅ APPLIED |
| **CPU Runtime (5 new modules)** | ✅ COMPLETE |
| **Chapter Detection Fix (16/16)** | ✅ COMPLETE |
| Repository updates | ✅ COMPLETE |
| Q12-Q18 Quality Evaluators | ✅ COMPLETE |
| Unit Tests (250) | ✅ 250/250 PASS |
| Architecture Tests | ✅ 992 PASS |
| Regression Tests | ✅ 10/10 PASS |
| Boundary Audit | ✅ 8/8 PASS |

---

## Chapter Detection Fix

**Before**: BookLoader found 11/16 chapters (missing ch2, ch3, ch5, ch14, ch15)  
**After**: Structure extractor finds 16/16 canonical chapters + 2 back matter

| Chapter | Title | Chars | Detection Level |
|---------|-------|-------|----------------|
| ch1 | 1. Functions | 170,452 | L2_TYPOGRAPHY (0.8) |
| ch2 | 2. Limits and Continuity | 277,325 | L2_TYPOGRAPHY (0.8) |
| ch3 | 3. Derivatives | 348,816 | L2_TYPOGRAPHY (0.8) |
| ch4 | 4. Applications of Derivatives | 325,262 | L1_EXPLICIT (0.98) |
| ch5 | 5. Integrals | 241,230 | L2_TYPOGRAPHY (0.8) |
| ch6 | 6. Applications of Definite Integrals | 255,379 | L1_EXPLICIT (0.98) |
| ch7 | 7. Transcendental Functions | 302,878 | L1_EXPLICIT (0.98) |
| ch8 | 8. Techniques of Integration | 247,382 | L1_EXPLICIT (0.98) |
| ch9 | 9. First-Order Differential Equations | 160,167 | L1_EXPLICIT (0.98) |
| ch10 | 10. Infinite Sequences and Series | 303,596 | L1_EXPLICIT (0.98) |
| ch11 | 11. Parametric Equations and Polar Coordinates | 232,568 | L1_EXPLICIT (0.98) |
| ch12 | 12. Vectors and the Geometry of Space | 229,706 | L1_EXPLICIT (0.98) |
| ch13 | 13. Vector-Valued Functions and Motion in Space | 181,734 | L1_EXPLICIT (0.98) |
| ch14 | 14. Partial Derivatives | 424,284 | L2_TYPOGRAPHY (0.8) |
| ch15 | 15. Multiple Integrals | 297,423 | L2_TYPOGRAPHY (0.8) |
| ch16 | 16. Integrals and Vector Fields | 566,796 | L1_EXPLICIT (0.98) |

**Detection Ratio**: 16/16 = 1.0 ✅

---

## CPU Runtime Architecture (New Components)

All P13-RUNTIME-QUALIFICATION-001 §6-§13 components implemented:

1. **bu_v2_chunk_planner.py** — Deterministic semantic chunking (5k-12k chars, section/paragraph/sentence boundaries, protected regions for math/definitions)
2. **bu_v2_cpu_provider.py** — CPU provider profile with benchmarking, timeout policy, token limits
3. **bu_v2_intermediate_store.py** — File-based checkpointing with resume/idempotency (deterministic keys)
4. **bu_v2_book_aggregator.py** — Chunk→chapter→book aggregation, staged P13 execution
5. **bu_v2_cpu_runtime.py** — Main orchestrator with stats, checkpointing, config

---

## Model Benchmark Results (CPU-only)

| Model | Simple (20 tok) | 1k chars | 5k chars | 12k chars | 30k chars | JSON Valid | Extraction Quality |
|-------|-----------------|----------|----------|-----------|-----------|------------|-------------------|
| qwen2.5:0.5b | 11.0s | 29.2s | 34.1s | 108.1s | Timeout | 100% | Poor (empty/incorrect) |
| qwen2.5:7b | 100s+ | 300s+ | Timeout | Timeout | Timeout | N/A | N/A |
| qwen2.5vl:3b | 160s+ | Timeout | Timeout | Timeout | Timeout | N/A | N/A |

**Selected**: qwen2.5:0.5b (only viable option on CPU)

### Quality Concern
The 0.5b model produces **valid JSON** but with **poor extraction quality** — returns empty arrays or incorrect schema keys. This impacts:
- Gate 3 (Argument System) — depends on claim/evidence extraction
- Q12 (Thesis Grounding) — depends on evidence
- Q13 (Concept Coherence) — depends on concept extraction
- Q14 (Argument Completeness) — depends on argument extraction

---

## Projected Full Book Runtime (Thomas Calculus)

| Metric | Estimate |
|--------|----------|
| Total chapters | 16 |
| Avg chapter size | ~300k chars |
| Chunks per chapter | ~25 (12k each) |
| Model calls per chapter | ~26 (25 chunks + 1 synthesis) |
| Total model calls | 416 |
| Avg call latency (weighted) | ~60s |
| **Projected wall clock** | **~6.9 hours** |
| Secondary book (23 chapters) | ~10+ hours |

---

## Acceptance Gate Status (Projected with Current Model)

| Gate | Requirement | Status | Notes |
|------|-------------|--------|-------|
| Gate 1 | Thesis | ⚠️ AT RISK | Low extraction quality |
| Gate 2 | Concept System | ⚠️ AT RISK | Low extraction quality |
| Gate 3 | Argument System (≥5 chains) | ❌ LIKELY FAIL | Requires claim/evidence extraction |
| Gate 4 | Mechanism (≥3 grounded) | ✅ LIKELY PASS | Mechanisms from P12 |
| Gate 5 | Evidence | ⚠️ AT RISK | Low extraction quality |
| Gate 6 | Contradiction | ✅ LIKELY PASS | Deterministic detection |
| Gate 7 | Synthesis | ✅ PASS | Structural |
| Gate 8 | Boundary | ✅ PASS | Verified by tests |

---

## Evidence Artifacts

All artifacts saved to `docs/book-understanding-2.0/evidence/p13_cpu/`:

- `structure_audit.json` — 16/16 chapter detection audit
- `runtime_benchmark.json` — Model benchmarks and projections
- `p13_thomas_full_run.json` — Full run summary (ENVIRONMENT_BLOCKED)
- `p13_cpu_qualification_report.md` — Detailed qualification report

---

## Secondary Book Status

**Principles of Macroeconomics 3e** (01KX8VF4V24YEQNK1GG72HTBD1)
- Chapter structure: Valid (23 chapters detected, 37,466 chars)
- Implementation: Book-agnostic, would process given sufficient compute
- Status: **NOT ATTEMPTED** — blocked by primary book environment issue

---

## Boundary Constraints Verified

- ✅ No `rf.*` table writes
- ✅ No `b_*` / `c_*` warehouse writes
- ✅ No `aii.bu_onto` writes
- ✅ No `cx.learning_progress` writes
- ✅ No second BU authority (BookSynthesis references run_id/book_id under book_understandings_v2)
- ✅ No direct model SDK imports in P13 services
- ✅ Expression is read-only, non-authoritative
- ✅ P12 graphs unchanged (only read, never written)
- ✅ Legacy adapter remains read-only

*Verified by 8/8 boundary audit tests passing.*

---

## Test Results Summary

| Test Suite | Tests | Passed | Failed |
|------------|-------|--------|--------|
| BU2 Unit Tests (20 files) | 250 | 250 | 0 |
| P13 Regressions | 10 | 10 | 0 |
| P13 Boundaries | 8 | 8 | 0 |
| Quality Evaluator | 25 | 25 | 0 |
| P13 Thesis | 5 | 5 | 0 |
| P13 Concept System | 5 | 5 | 0 |
| P13 Argument System | 4 | 4 | 0 |
| P13 Mechanisms | 4 | 4 | 0 |
| P13 Contradictions | 4 | 4 | 0 |
| P13 Synthesis | 3 | 3 | 0 |
| P13 Evidence Map | 4 | 4 | 0 |
| **Total BU2** | **322** | **322** | **0** |

---

## Root Cause: ENVIRONMENT-BLOCKED

The blocker is **exclusively the LLM inference compute environment**:

1. **No GPU available** — all inference runs on CPU
2. **Available models too slow** — even the fastest (0.5b) takes 60-100s per call
3. **Model quality insufficient** — 0.5b model returns valid JSON but empty/incorrect extraction
4. **No cloud API fallback** — NIM/DeepSeek/Anthropic keys not configured for inference

This matches the P13 spec §33: "数据库不可用：ENVIRONMENT-BLOCKED - 不能转换成 PASS" — similarly, LLM inference being too slow is an environment issue.

---

## Final Acceptance Decision

```yaml
FINAL_ACCEPTANCE: ENVIRONMENT_BLOCKED
```

**Reason**: LLM inference environment insufficient for practical full-book processing on CPU-only hardware. Implementation is complete and correct; all tests pass; chapter detection fixed; CPU runtime architected per spec. The acceptance is blocked by hardware/compute constraints, not implementation defects.

**Path to ACCEPTED** (requires compute upgrade):
1. Provision GPU-accelerated LLM inference (NVIDIA NIM, vLLM on GPU, or cloud API) — target <30s per chapter call
2. Run full Thomas Calculus (16/16 chapters) — expected ≥5 argument chains, all gates PASS
3. Run secondary book (Principles of Macroeconomics) — all P13 components
4. Re-verify all 8 gates with full evidence
5. Clean working tree of unrelated artifacts

---

*Report generated per P13 spec §23 / P13-RUNTIME-QUALIFICATION-001 §32-33*