"""
Entry point for the DataOps pipeline.
Supports --once for a single immediate run, otherwise runs on schedule via APScheduler.
"""
import argparse
import asyncio
import sys
import time

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .extractors.bacen import BacenExtractor
from .extractors.ibge import IBGEExtractor
from .loaders.database import DatabaseLoader
from .loaders.metrics import MetricsServer, record_extract_error, record_run
from .settings import Settings
from .transformers.bacen import transform_bacen
from .transformers.ibge import transform_ibge

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


async def run_bacen_pipeline(loader: DatabaseLoader, http_timeout: float) -> None:
    source = "bacen"
    started = time.perf_counter()
    logger.info("pipeline.start", source=source)
    try:
        raw = await BacenExtractor(timeout=http_timeout).fetch_all()
        records = transform_bacen(raw)
        inserted = await loader.upsert_indicators(records)
        record_run(source, "success", len(records), time.perf_counter() - started)
        logger.info("pipeline.done", source=source, records=inserted)
    except Exception as exc:
        record_extract_error(source)
        record_run(source, "error", 0, time.perf_counter() - started)
        logger.error("pipeline.error", source=source, error=str(exc))
        raise


async def run_ibge_pipeline(loader: DatabaseLoader, http_timeout: float) -> None:
    source = "ibge"
    started = time.perf_counter()
    logger.info("pipeline.start", source=source)
    try:
        raw = await IBGEExtractor(timeout=http_timeout).fetch_all()
        records = transform_ibge(raw)
        inserted = await loader.upsert_population(records)
        record_run(source, "success", len(records), time.perf_counter() - started)
        logger.info("pipeline.done", source=source, records=inserted)
    except Exception as exc:
        record_extract_error(source)
        record_run(source, "error", 0, time.perf_counter() - started)
        logger.error("pipeline.error", source=source, error=str(exc))
        raise


async def run_all(settings: Settings) -> None:
    loader = DatabaseLoader(settings.database_url)
    try:
        await loader.init()
        # Sources are independent; isolate failures so one bad API doesn't sink the run.
        await asyncio.gather(
            run_bacen_pipeline(loader, settings.http_timeout),
            run_ibge_pipeline(loader, settings.http_timeout),
            return_exceptions=True,
        )
    finally:
        await loader.close()


async def run_scheduled(settings: Settings) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_all,
        args=[settings],
        trigger=IntervalTrigger(hours=settings.schedule_hours),
        id="pipeline",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("scheduler.started", interval_hours=settings.schedule_hours)

    await run_all(settings)  # run once on startup, then idle until the trigger fires

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        logger.info("scheduler.stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="DataOps Pipeline Orchestrator")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    settings = Settings()
    MetricsServer(port=settings.metrics_port).start()

    if args.once:
        asyncio.run(run_all(settings))
        sys.exit(0)

    try:
        asyncio.run(run_scheduled(settings))
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
