import os

import pytest
from sqlalchemy import delete, func, select

from pipeline.loaders.database import (
    DatabaseLoader,
    EconomicIndicatorRow,
    PopulationEstimateRow,
)
from pipeline.transformers.bacen import transform_bacen
from pipeline.transformers.ibge import transform_ibge

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set TEST_DATABASE_URL to run the PostgreSQL integration test",
)


async def _count(loader: DatabaseLoader, model) -> int:
    async with loader._session() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar_one()


async def _truncate(loader: DatabaseLoader) -> None:
    async with loader._session() as session:
        await session.execute(delete(EconomicIndicatorRow))
        await session.execute(delete(PopulationEstimateRow))
        await session.commit()


@pytest.mark.integration
async def test_upsert_is_idempotent_across_reruns():
    loader = DatabaseLoader(TEST_DATABASE_URL)
    try:
        await loader.init()
        await _truncate(loader)

        indicators = transform_bacen(
            [{"series_code": "433", "series_name": "IPCA", "data": "01/05/2024", "valor": "0.46"}]
        )
        population = transform_ibge(
            [{"state_code": "35", "state_name": "São Paulo", "year": "2021", "population": "1"}]
        )

        await loader.upsert_indicators(indicators)
        await loader.upsert_population(population)
        await loader.upsert_indicators(indicators)
        await loader.upsert_population(population)

        assert await _count(loader, EconomicIndicatorRow) == 1
        assert await _count(loader, PopulationEstimateRow) == 1
    finally:
        await loader.close()
