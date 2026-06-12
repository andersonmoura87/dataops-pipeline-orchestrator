# dataops-pipeline-orchestrator

Automated DataOps pipeline that extracts data from public APIs (Bacen/SGS and IBGE), transforms and validates it, persists in PostgreSQL and exposes metrics via Prometheus. Runs on schedule inside Docker.

## What it does

```
┌──────────────────────────────────────────────────────────┐
│                    Scheduler (APScheduler)                │
│                    runs every 6 hours                     │
└────────────────────┬─────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │     Extractor       │
          │  Bacen SGS API      │  → IPCA, SELIC, USD/BRL
          │  IBGE API           │  → Population estimates
          └──────────┬──────────┘
                     │ raw JSON
          ┌──────────▼──────────┐
          │    Transformer      │
          │  Validate schema    │
          │  Normalize fields   │
          │  Detect anomalies   │
          └──────────┬──────────┘
                     │ clean records
          ┌──────────▼──────────┐
          │      Loader         │
          │  PostgreSQL (upsert)│
          │  Prometheus metrics │
          └─────────────────────┘
```

## Why these data sources?

| Source | What we collect | Why |
|---|---|---|
| Bacen SGS | IPCA, SELIC, USD/BRL | Stable public API, real economic indicators |
| IBGE | Population estimates by state | Demonstrates joining datasets |

Both APIs are free, no auth required, and highly reliable — ideal for a reproducible portfolio project.

## Stack

| Component | Technology |
|---|---|
| Pipeline | Python 3.11 |
| Scheduling | APScheduler |
| HTTP | httpx (async) |
| Validation | Pydantic v2 |
| Database | PostgreSQL + SQLAlchemy 2 |
| Metrics | Prometheus client |
| Containers | Docker + Docker Compose |
| CI | GitHub Actions |
| Logging | structlog (JSON output) |

## Quick Start

```bash
git clone https://github.com/andersonmoura87/dataops-pipeline-orchestrator
cd dataops-pipeline-orchestrator

cp .env.example .env
docker compose up --build
```

To trigger a run immediately:
```bash
docker compose exec pipeline python -m pipeline.run --once
```

## Project Structure

```
dataops-pipeline-orchestrator/
├── pipeline/
│   ├── __init__.py
│   ├── run.py            ← CLI entry point + scheduler
│   ├── settings.py       ← Pydantic settings
│   ├── extractors/
│   │   ├── bacen.py      ← Bacen SGS API client
│   │   └── ibge.py       ← IBGE API client
│   ├── transformers/
│   │   ├── bacen.py      ← Normalize + validate
│   │   └── ibge.py
│   └── loaders/
│       ├── database.py   ← SQLAlchemy upsert
│       └── metrics.py    ← Prometheus counters/histograms
├── tests/
│   ├── test_extractors.py
│   ├── test_transformers.py
│   └── fixtures/
├── infra/
│   └── prometheus.yml
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Metrics exposed

The pipeline exposes `/metrics` on port `8080`:

| Metric | Type | Description |
|---|---|---|
| `pipeline_runs_total` | Counter | Total pipeline executions by source and status |
| `pipeline_records_processed_total` | Counter | Records extracted per source |
| `pipeline_run_duration_seconds` | Histogram | End-to-end duration per source |
| `pipeline_last_success_timestamp` | Gauge | Unix timestamp of last successful run |
| `pipeline_extract_errors_total` | Counter | HTTP/parse errors per source |

## Data Schema

```sql
-- economic_indicators
id          SERIAL PRIMARY KEY
source      VARCHAR(50)     -- 'bacen'
series_code VARCHAR(20)     -- '433' (IPCA), '11' (SELIC), '10813' (USD/BRL)
reference_date DATE
value       NUMERIC(18, 6)
unit        VARCHAR(20)
ingested_at TIMESTAMPTZ DEFAULT now()
UNIQUE (series_code, reference_date)

-- population_estimates
id          SERIAL PRIMARY KEY
state_code  CHAR(2)
state_name  VARCHAR(80)
year        INT
population  BIGINT
ingested_at TIMESTAMPTZ DEFAULT now()
UNIQUE (state_code, year)
```

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

## CI/CD

The GitHub Actions pipeline:
1. Lints with `ruff`
2. Runs tests with `pytest` (mocked HTTP — no external calls)
3. Builds and pushes the Docker image to GHCR on merge to `main`

## Design Decisions

**Why APScheduler instead of Airflow/Prefect?**
Airflow adds significant operational overhead for a single-machine pipeline. APScheduler runs in-process, is containerized, and keeps the project self-contained without sacrificing scheduling capabilities.

**Why upsert instead of append?**
The Bacen API occasionally revises historical values. Upserting on `(series_code, reference_date)` ensures the database always reflects the latest values without duplicates.

**Why structlog over standard logging?**
JSON-formatted logs integrate naturally with log aggregation tools (Loki, CloudWatch, Datadog) with no additional config.

## License

MIT
