"""Lightweight Prometheus-format metrics for Stratum."""

import time
from collections import defaultdict
from fastapi import Request

_MAX_SERIES = 500  # hard cap — drop new series once reached (cardinality DoS guard)


def _escape_label(value: str) -> str:
    """Escape per Prometheus exposition spec: \\ → \\\\, " → \\", \\n → \\n."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _route_template(request: Request) -> str:
    """Return the matched route template (e.g. /share/{token}) or '<unmatched>'."""
    route = request.scope.get("route")
    if route is None:
        return "<unmatched>"
    return getattr(route, "path", "<unmatched>")


class MetricsCollector:
    def __init__(self):
        self.request_count: dict = defaultdict(int)
        self.request_latency_sum: dict = defaultdict(float)
        self.request_latency_count: dict = defaultdict(int)

    def record(self, method: str, path: str, status: int, duration: float) -> None:
        if len(self.request_count) >= _MAX_SERIES:
            return
        key = (method, path, status)
        self.request_count[key] += 1
        self.request_latency_sum[key] += duration
        self.request_latency_count[key] += 1

    def render(self, active_sessions: int = 0, corpus_count: int = 0) -> str:
        lines = []
        lines.append("# HELP http_requests_total Total HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        for (method, path, status), count in sorted(self.request_count.items()):
            m, p, s = _escape_label(method), _escape_label(path), _escape_label(str(status))
            lines.append(f'http_requests_total{{method="{m}",path="{p}",status="{s}"}} {count}')

        lines.append("# HELP http_request_duration_seconds HTTP request latency")
        lines.append("# TYPE http_request_duration_seconds summary")
        for (method, path, status), total in sorted(self.request_latency_sum.items()):
            count = self.request_latency_count[(method, path, status)]
            m, p, s = _escape_label(method), _escape_label(path), _escape_label(str(status))
            lines.append(
                f'http_request_duration_seconds_sum{{method="{m}",path="{p}",status="{s}"}} {total:.6f}'
            )
            lines.append(
                f'http_request_duration_seconds_count{{method="{m}",path="{p}",status="{s}"}} {count}'
            )

        lines.append("# HELP stratum_active_sessions Current active sessions")
        lines.append("# TYPE stratum_active_sessions gauge")
        lines.append(f"stratum_active_sessions {active_sessions}")

        lines.append("# HELP stratum_corpus_count Total corpora (users)")
        lines.append("# TYPE stratum_corpus_count gauge")
        lines.append(f"stratum_corpus_count {corpus_count}")

        return "\n".join(lines) + "\n"


metrics = MetricsCollector()


async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path
    if path not in ("/api/admin/metrics", "/health"):
        normalized = _route_template(request)
        metrics.record(request.method, normalized, response.status_code, duration)
    return response
