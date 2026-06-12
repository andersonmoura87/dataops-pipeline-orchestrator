"""
Prometheus metrics for the pipeline.
Starts a lightweight HTTP server on /metrics.
"""
import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server

RUNS_TOTAL = Counter(
    "pipeline_runs_total",
    "Total pipeline executions",
    ["source", "status"],
)

RECORDS_PROCESSED = Counter(
    "pipeline_records_processed_total",
    "Records processed per source",
    ["source"],
)

RUN_DURATION = Histogram(
    "pipeline_run_duration_seconds",
    "End-to-end pipeline duration",
    ["source"],
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

LAST_SUCCESS = Gauge(
    "pipeline_last_success_timestamp",
    "Unix timestamp of last successful run",
    ["source"],
)

EXTRACT_ERRORS = Counter(
    "pipeline_extract_errors_total",
    "HTTP/parse errors per source",
    ["source"],
)


def record_run(source: str, status: str, records: int, duration: float) -> None:
    RUNS_TOTAL.labels(source=source, status=status).inc()
    RECORDS_PROCESSED.labels(source=source).inc(records)
    RUN_DURATION.labels(source=source).observe(duration)
    if status == "success":
        LAST_SUCCESS.labels(source=source).set(time.time())


def record_extract_error(source: str) -> None:
    EXTRACT_ERRORS.labels(source=source).inc()


class MetricsServer:
    def __init__(self, port: int = 8080) -> None:
        self.port = port

    def start(self) -> None:
        start_http_server(self.port)
