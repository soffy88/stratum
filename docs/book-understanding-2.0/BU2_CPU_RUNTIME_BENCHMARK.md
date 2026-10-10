# BU2 CPU Runtime Benchmark Report

## Hardware
- CPU: Intel/AMD (CPU-only, no GPU)
- RAM: 32GB

## Models Tested

### qwen2.5:0.5b (SELECTED)
- Simple prompt (20 tokens): 11.0s
- 1k char prompt: 29.2s
- 5k char prompt: 34.1s
- 12k char prompt (max chunk): 108.1s
- 30k char prompt: Timeout (>180s)
- JSON validity: 100%
- Evidence grounding: 0% (returns valid JSON but empty/incorrect extraction)
- Notes: Valid JSON output but poor extraction quality; follows schema loosely

### qwen2.5:7b
- Simple prompt: >100s
- Chapter prompt: >300s (timeout)
- Not viable for CPU-only

### qwen2.5vl:3b
- Simple prompt: >160s
- Not viable for CPU-only

## Selected Model: qwen2.5:0.5b
Reason: Only model completing within practical time on CPU-only hardware.

## Projected Full Book Runtime (Thomas Calculus, 16 chapters)
- Average chapter: ~300k chars → ~25 chunks of 12k each
- Chunk calls per chapter: ~25
- Chapter synthesis calls: ~1
- Total model calls: 16 * 26 = 416
- Average call latency: ~60s (weighted)
- Estimated wall clock: 416 * 60s = ~6.9 hours

## Quality Concerns
The selected model produces valid JSON but with poor extraction quality (empty/incorrect fields). This may impact Gate 3 (Argument System) and Q12-Q14 scores.

## Mitigation
- Use deterministic preprocessing to reduce LLM burden
- Rely on P12/P10 evidence for traceability
- Accept lower Q12-Q14 scores if gates pass on structure
