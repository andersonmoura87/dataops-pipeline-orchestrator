# dataops-pipeline-orchestrator

![CI](https://github.com/andersonmoura87/dataops-pipeline-orchestrator/actions/workflows/ci.yml/badge.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)

Pipeline DataOps automatizado que extrai dados de APIs públicas (Bacen/SGS e IBGE), transforma e valida com Pydantic, persiste no PostgreSQL via upsert e expõe métricas no Prometheus. Roda em schedule dentro do Docker.

## O que faz

```
┌──────────────────────────────────────────────────────────┐
│                    Scheduler (APScheduler)                │
│                    executa a cada 6 horas                 │
└────────────────────┬─────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │     Extractor       │
          │  API Bacen SGS      │  → IPCA, SELIC, USD/BRL
          │  API IBGE           │  → Estimativas populacionais
          └──────────┬──────────┘
                     │ JSON bruto
          ┌──────────▼──────────┐
          │    Transformer      │
          │  Valida schema      │
          │  Normaliza campos   │
          │  Descarta inválidos │
          └──────────┬──────────┘
                     │ registros limpos
          ┌──────────▼──────────┐
          │      Loader         │
          │  PostgreSQL (upsert)│
          │  Métricas Prometheus│
          └─────────────────────┘
```

## Por que essas fontes de dados?

| Fonte | O que coletamos | Motivo |
|---|---|---|
| Bacen SGS | IPCA, SELIC, USD/BRL | API pública estável, indicadores econômicos reais |
| IBGE | Estimativas populacionais por UF | Demonstra cruzamento de datasets |

As duas APIs são gratuitas, não exigem autenticação e são confiáveis — ideais para um projeto de portfólio reproduzível.

## Stack

| Componente | Tecnologia |
|---|---|
| Pipeline | Python 3.11 |
| Agendamento | APScheduler |
| HTTP | httpx (async) |
| Validação | Pydantic v2 |
| Banco de dados | PostgreSQL + SQLAlchemy 2 |
| Métricas | Prometheus client |
| Containers | Docker + Docker Compose |
| CI | GitHub Actions |
| Logs | structlog (saída JSON) |

## Início rápido

```bash
git clone https://github.com/andersonmoura87/dataops-pipeline-orchestrator
cd dataops-pipeline-orchestrator

cp .env.example .env
docker compose up --build
```

Para disparar uma execução imediatamente:

```bash
docker compose exec pipeline python -m pipeline.run --once
```

## Estrutura do projeto

```
dataops-pipeline-orchestrator/
├── pipeline/
│   ├── __init__.py
│   ├── run.py            ← CLI + scheduler
│   ├── settings.py       ← configuração via Pydantic Settings
│   ├── extractors/
│   │   ├── bacen.py      ← cliente API Bacen SGS
│   │   └── ibge.py       ← cliente API IBGE
│   ├── transformers/
│   │   ├── bacen.py      ← normalização + validação
│   │   └── ibge.py
│   └── loaders/
│       ├── database.py   ← upsert com SQLAlchemy
│       └── metrics.py    ← counters/histograms Prometheus
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

## Métricas expostas

O pipeline expõe `/metrics` na porta `8080`:

| Métrica | Tipo | Descrição |
|---|---|---|
| `pipeline_runs_total` | Counter | Total de execuções por fonte e status |
| `pipeline_records_processed_total` | Counter | Registros processados por fonte |
| `pipeline_run_duration_seconds` | Histogram | Duração end-to-end por fonte |
| `pipeline_last_success_timestamp` | Gauge | Timestamp Unix da última execução bem-sucedida |
| `pipeline_extract_errors_total` | Counter | Erros de HTTP/parse por fonte |

## Schema dos dados

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

## Executando os testes

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --tb=short
```

Para rodar o teste de integração com PostgreSQL:

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://dataops:changeme@localhost:5432/dataops_test
pytest tests/test_loader.py -v
```

## CI/CD

O pipeline do GitHub Actions:

1. Lint com `ruff`
2. Testes com `pytest` (HTTP mockado — sem chamadas externas no CI)
3. Build e push da imagem Docker para o GHCR no merge na `main`

## Decisões de design

**Por que APScheduler em vez de Airflow/Prefect?**
Airflow adiciona overhead operacional significativo para um pipeline de máquina única. O APScheduler roda in-process, é containerizado e mantém o projeto autocontido sem abrir mão do agendamento.

**Por que upsert em vez de append?**
A API do Bacen revisa valores históricos ocasionalmente. Fazer upsert em `(series_code, reference_date)` garante que o banco reflita sempre os valores mais recentes, sem duplicatas.

**Por que structlog em vez do logging padrão?**
Logs em JSON integram naturalmente com ferramentas de agregação (Loki, CloudWatch, Datadog) sem configuração extra.
