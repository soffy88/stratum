# AII observability contract

Services emit structured logs to stdout/stderr. Request logs include timestamp,
service, environment, request/trace ID, route, status and duration. They never
include passwords, tokens, raw document content or full Authorization headers.

Minimum signals are API health/readiness, PostgreSQL pool saturation and
migration version; route count/error/latency (p50/p95); retrieval result count
and provider latency/errors; ingestion/parser outcomes and queue age; and
backup age, restore-test result and storage capacity.

Trace/request IDs propagate through API, ingestion, retrieval, projections and
background jobs. Alerts distinguish canonical-authority failures from optional
provider failures. Logs and traces use an operator-configured retention period
and are redacted before third-party export.
