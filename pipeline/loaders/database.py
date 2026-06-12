"""
Async SQLAlchemy loader. Persists validated records with upserts so that
re-running a pipeline reconciles revised values instead of duplicating rows.
"""
from datetime import date, datetime
from decimal import Decimal

import structlog
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..transformers.bacen import EconomicIndicator
from ..transformers.ibge import PopulationEstimate

logger = structlog.get_logger()


class Base(DeclarativeBase):
    pass


class EconomicIndicatorRow(Base):
    __tablename__ = "economic_indicators"
    __table_args__ = (UniqueConstraint("series_code", "reference_date", name="uq_indicator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    series_code: Mapped[str] = mapped_column(String(20))
    series_name: Mapped[str] = mapped_column(String(50))
    reference_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(20))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PopulationEstimateRow(Base):
    __tablename__ = "population_estimates"
    __table_args__ = (UniqueConstraint("state_code", "year", name="uq_population"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2))
    state_name: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer)
    population: Mapped[int] = mapped_column(BigInteger)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DatabaseLoader:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._session: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def upsert_indicators(self, records: list[EconomicIndicator]) -> int:
        if not records:
            return 0
        rows = [r.model_dump() for r in records]
        stmt = pg_insert(EconomicIndicatorRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_indicator",
            set_={
                "source": stmt.excluded.source,
                "series_name": stmt.excluded.series_name,
                "value": stmt.excluded.value,
                "unit": stmt.excluded.unit,
                "ingested_at": func.now(),
            },
        )
        async with self._session() as session:
            await session.execute(stmt)
            await session.commit()
        logger.info("db.upsert", table="economic_indicators", rows=len(rows))
        return len(rows)

    async def upsert_population(self, records: list[PopulationEstimate]) -> int:
        if not records:
            return 0
        rows = [r.model_dump() for r in records]
        stmt = pg_insert(PopulationEstimateRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_population",
            set_={
                "state_name": stmt.excluded.state_name,
                "population": stmt.excluded.population,
                "ingested_at": func.now(),
            },
        )
        async with self._session() as session:
            await session.execute(stmt)
            await session.commit()
        logger.info("db.upsert", table="population_estimates", rows=len(rows))
        return len(rows)

    async def close(self) -> None:
        await self._engine.dispose()
