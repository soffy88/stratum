"""Lightweight Prometheus-format metrics for Stratum."""

import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.responses import PlainTextResponse


class MetricsCollector:
    def __init__(self):
        self.request_count = defaultdict(int)
        self.request_latency_sum = defaultdict(float)
        self.request_latency_count = defaultdict(int)

    def record(self, method: str, path: str, status: int, duration: float):
        key = (method, path, status)
        self.request_count[key] += 1
        self.request_latency_sum[key] += duration
        self.request_latency_count[key] += 1

    def render(self, active_sessions: int = 0, corpus_count: int = 0) -> str:
        lines = []
        lines.append("# HELP http_requests_total Total HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        for (method, path, status), count in sorted(self.request_count.items()):
            lines.append(f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

        lines.append("# HELP http_request_duration_seconds HTTP request latency")
        lines.append("# TYPE http_request_duration_seconds summary")
        for (method, path, status), total in sorted(self.request_latency_sum.items()):
            count = self.request_latency_count[(method, path, status)]
            lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.6f}')
            lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}",status="{status}"}} {count}')

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
    # Normalize path to avoid high cardinality
    path = request.url.path
    if path != "/metrics" and path != "/health":
        metrics.record(request.method, path, response.status_code, duration)
    return response
