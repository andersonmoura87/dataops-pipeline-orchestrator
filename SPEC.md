# SPEC — dataops-pipeline-orchestrator

## Goal
Automated DataOps pipeline: extract from public APIs (Bacen SGS + IBGE),
validate and transform with Pydantic, upsert into PostgreSQL, expose Prometheus metrics.
Runs on a configurable schedule inside Docker.

## Pipeline flow
1. **Extract** — async HTTP calls to Bacen SGS and IBGE APIs
2. **Transform** — Pydantic models validate and normalize each record
3. **Load** — SQLAlchemy upsert into PostgreSQL (conflict = update)
4. **Observe** — Prometheus counters/histograms on every run

## Data sources
- Bacen SGS: series 433 (IPCA), 11 (SELIC), 10813 (USD/BRL) — last 24 months
- IBGE: population estimates by state, latest available year

## Acceptance criteria
- `docker compose up` starts pipeline + postgres + prometheus + grafana
- `python -m pipeline.run --once` completes without error
- All records are upserted (re-running twice produces same row count, not doubles)
- `/metrics` on port 8080 shows `pipeline_runs_total` with status=success
- Tests pass with mocked HTTP (no real API calls in CI)

## Non-goals (v1)
- No Airflow/Prefect
- No dbt transformations
- No streaming (batch only)
- No authentication on metrics endpoint
