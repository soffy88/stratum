# Optional three-round deep-read supplements

`python -m stratum.services.web_ingest deep-read <path>` creates a JSON sidecar for a Markdown/text source or EPUB book. Its three rounds produce exactly 12 Q&A items: 4 for overview/framework, 5 for deep analysis, and 3 for synthesis/reflection. Each round receives the previous rounds' summaries and Q&A as context.

Example:

```bash
python -m stratum.services.web_ingest deep-read /path/to/article.md --json
python -m stratum.services.web_ingest deep-read /path/to/book.epub --kind book --force
```

The default output path is `<source-stem>.deep-read.json` next to the source. The artifact records source URI/title/kind, SHA-256 of the source text, source length, whether a long source was sampled, provider/model, the three rounds, evidence snippets, and confidence values. For sources over 18,000 characters, the prompt uses labeled excerpts from the beginning, middle, and end; `sampled_for_context` makes this limitation explicit.

Automatic enrichment after successful URL ingestion is **off by default**. Set `STRATUM_DEEP_READ_ENABLED=1` to opt in. Enrichment failures are logged and do not turn a successful source fetch/write into a failed ingestion. `--dry-run` never runs enrichment.

The sidecar is supplementary data targeting BU2/KU consumers; it deliberately does not mutate canonical BookUnderstandingV2 or KnowledgeUnit records. This avoids inventing a user/substrate/run identity for an article before the canonical pipeline has created one. A future consumer can validate the sidecar's `source.content_sha256` before attaching it to canonical records.

The CLI uses Stratum's existing `ModelProvider` via the shared PPT/BU2 Veya-fllm configuration; no new provider implementation or API key path is introduced. Tests use a mock provider and do not make live inference calls.
