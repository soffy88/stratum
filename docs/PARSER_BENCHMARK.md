# Parser benchmark

`eval_parser_benchmark.py` 是本地 gold-set 门槛，维度对齐 OmniDocBench：

- layout：单栏、多栏、表格密集、扫描件等；
- language：zh、en、mixed；
- structure_elements：heading、table、list、code、formula。

每个 case 还可以声明 `required_markers` 和 `min_chars`。报告按维度输出通过率，
便于季度性 shadow 运行 Docling、pymupdf4llm 或 oprim，并把 olmOCR-Bench 作为外部
对照，而不是另造一套不可比较的总分。

运行：

```bash
python scripts/eval_parser_benchmark.py path/to/parser-gold.json
# real-data release gate: default minimum is 20 cases
python scripts/eval_parser_benchmark.py path/to/parser-gold.json \
  --min-cases 20 --require-provenance --require-files \
  --baseline parser-baseline.json --report-out parser-report.json
python scripts/check_eval_release_gate.py \
  --retrieval-report retrieval-report.json --parser-report parser-report.json
```

Manifest schema is [parser_benchmark.schema.json](../scripts/parser_benchmark.schema.json).
The runner rejects duplicate IDs, unsupported dimensions, and invalid review metadata before
invoking a parser. Baseline
reports can be compared with `--baseline`; the release gate requires a successful non-regressing
baseline comparison from the same manifest fingerprint. A sample fixture may be used locally by lowering `--min-cases` and passing
`--allow-missing-baseline` to the gate, but it does not satisfy the default release gate.
Each case report also preserves missing markers, missing structure dimensions, and
`failure_reasons`; dimension aggregates include marker/structure coverage so a real benchmark
can distinguish parser failures from incomplete gold annotations.
When supplied by the manifest, each case trace also echoes `source_ref`, `reviewer`, and
`review_status` for auditability.
If every parser dependency is unavailable and the converter returns `passthrough`, the case is
now marked `parser_passthrough` and cannot count as a pass; this prevents PDF bytes from being
mistaken for extracted Markdown.
When installed, the converter has a final `pdftotext` fallback for text extraction. It is useful
for local smoke checks, but it does not establish table/layout fidelity; reviewed gold annotations
and a real parser baseline are still required for release evaluation.

To inventory local PDFs without pretending that their dimensions were reviewed:

```bash
python scripts/discover_parser_candidates.py \
  --root experiments/02-batch/samples/pdf \
  --output /tmp/parser-candidates.json --limit 20
```

This produces `candidate` cases with `unknown` dimensions and empty markers. A reviewer must
replace those placeholders with actual layout/language/structure annotations before running a
release benchmark; the inventory command is preparation only.

To prepare a stable manual-review packet with file hashes and a short extracted-text preview:

```bash
python scripts/build_parser_review_packet.py \
  --manifest /tmp/parser-candidates.json \
  --output /tmp/parser-review-packet.json
```

The packet deliberately preserves candidate annotations and marks every case as requiring review;
it is a review aid, not a gold-set generator.

After a human fills a decision file, apply it to a new manifest (the source remains unchanged):

```bash
python scripts/apply_eval_reviews.py --kind parser \
  --manifest /tmp/parser-candidates.json \
  --reviews parser-decisions.json \
  --output parser-gold-reviewed.json
```

The default mode requires one valid reviewed decision per case and revalidates the resulting
manifest. `--allow-partial` is only for local preparation and cannot satisfy the release gate.

Release runs must pass `--require-provenance`: every case needs `source_ref`, `reviewer`, and
`review_status: "reviewed"`. The retrieval runner applies the same rule to
`source_ref`/`reviewer`/`rationale`. `--allow-unreviewed` is only a local fixture escape hatch;
it is not a release sign-off.
