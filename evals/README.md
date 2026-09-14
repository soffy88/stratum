# Layered evaluation contract

The release evaluation set is frozen as human-reviewed data, not inferred from
model output.  Every new record must provide `owner_id`, canonical
`source_ids`, an auditable `provenance` object, and `expected_output`; the
schema is `evals/real_gold.schema.json`.  Synthetic data is permitted only for
capacity testing and is never a release-quality gold set.
Each record has a `layer` from the list below, plus `expected` and `actual`
values produced by the corresponding production boundary:

`ingestion`, `fragmentation`, `evidence_extraction`, `claim_correctness`,
`citation_completeness`, `concept_normalization`, `relation_accuracy`,
`retrieval`, and `answer_grounding`.

Run `uv run python scripts/evaluate_layered_gold.py <frozen-results.json>`. The
runner prints the SHA-256 of the input and reports each layer independently;
missing layers are explicit and never treated as a pass. The existing
`gold_retrieval_verified_v1.json` remains unchanged and is the frozen
retrieval gold source.

`evals/coverage_manifest.json` records which layers are currently verified.
`evals/layered_gold.template.json` is an annotation template only; its draft
record is not a gold label and must be replaced by human review before use.

The checked-in `evals/baselines/retrieval-baseline-v1.json` is the observed
quality baseline for the immutable 100-case human gold.  The separate
`retrieval-capacity-baseline-v1.json` records synthetic 10K/100K/1M capacity
measurements and PostgreSQL plan proofs.  Capacity p99 values are explicitly
`INSUFFICIENT_SAMPLE_SIZE` because the recorded runs contain fewer than 100
samples per series.  Component timing and query-plan evidence are stored under
`evals/evidence/`; their source artifact checksums are retained for audit.

The `production_runtime` test is intentionally excluded from the ordinary
hermetic PR regression.  It is preserved for a deployed-runtime qualification
job because it probes the externally running service (including port 9304),
which is not a dependency of the P2 benchmark or PR test contract.

Compare frozen result documents with:
`uv run python scripts/check_evaluation_regression.py baseline.json candidate.json`.
The comparison is fail-closed for quality regressions, citation/provenance
regressions, leakage, and p95 latency budget overruns.
