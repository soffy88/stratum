# Retrieval evaluation

`scripts/eval_retrieval.py` measures recall, precision, hit-rate and MRR at `k`.
The release target is at least 50 queries with reviewed provenance and a
non-regressing baseline.

The repository contains a legacy AII question set at
`aii/scripts/eval/golden.json`. It has 55 curated query/substrate candidates,
but it predates the current review contract. Convert it into the current
schema with:

```bash
python scripts/import_legacy_retrieval_gold.py \
  --input aii/scripts/eval/golden.json \
  --output /tmp/retrieval-gold-candidate.json
```

The importer preserves `gold_ku_id` and source row references, but every item
remains `review_status: "candidate"`. A human must verify the substrate
mapping, add `reviewer` and `rationale`, and change the status to `reviewed`.
The release gate intentionally rejects the generated candidate file until
that review happens.

Create a stable human-review packet without changing those candidate records:

```bash
python scripts/build_retrieval_review_packet.py \
  --manifest /tmp/retrieval-gold-candidate.json \
  --output /tmp/retrieval-review-packet.json
```

The packet labels substrate IDs as proposed mappings and keeps
`mapping_review_required: true`; it is a review aid, not a reviewed gold set.

Before contacting a deployed API, check both manifests together:

```bash
python scripts/check_eval_manifest_readiness.py \
  --retrieval-manifest /tmp/retrieval-gold-candidate.json \
  --parser-manifest /tmp/parser-candidates.json \
  --output /tmp/eval-manifest-readiness.json
```

This preflight reports counts, review completeness, and parser-file availability only. A non-zero result is expected until
the real reviewed datasets exist; it is not a retrieval/parser metric result.

Reviewed decisions can be applied without mutating the candidate source:

```bash
python scripts/apply_eval_reviews.py --kind retrieval \
  --manifest /tmp/retrieval-gold-candidate.json \
  --reviews retrieval-decisions.json \
  --output retrieval-gold-reviewed.json
```

The default requires a complete reviewed decision set and validates the output with the retrieval
provenance contract.
The validator also rejects malformed optional review metadata or unknown review states before
contacting the retrieval API.

Per-query report traces echo optional `query_id`, `source_ref`, `reviewer`, and
`review_status` fields, so a metric can be traced back to its review record.

After review and deployment:

```bash
python scripts/eval_retrieval.py \
  --golden retrieval-gold-reviewed.json \
  --min-queries 50 --require-provenance \
  --baseline retrieval-baseline.json \
  --report-out retrieval-report.json
```

The baseline is required by the release gate and must be generated from a
documented previous retrieval configuration against the same reviewed manifest fingerprint.
This is a preparation step, not a real-data benchmark result. The current
environment still lacks the deployed retrieval service and the human review
needed for release sign-off.
