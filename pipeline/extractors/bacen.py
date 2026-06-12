"""
Extractor for Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS).
Docs: https://www.bcb.gov.br/estatisticas/sgspub
"""
import asyncio

import httpx
import structlog

from ..http import get_json

logger = structlog.get_logger()

# Series codes: https://www3.bcb.gov.br/sgspub/localizarseries
SERIES = {
    "433": "IPCA",          # Consumer price index (monthly %)
    "11": "SELIC",          # Base interest rate (% p.a.)
    "10813": "USD_BRL",     # USD/BRL exchange rate
}

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/24?formato=json"


class BacenExtractor:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def fetch_series(self, client: httpx.AsyncClient, code: str, name: str) -> list[dict]:
        data = await get_json(client, BASE_URL.format(code=code))
        logger.info("bacen.fetched", series=name, code=code, records=len(data))
        return [{"series_code": code, "series_name": name, **row} for row in data]

    async def fetch_all(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            results = await asyncio.gather(
                *(self.fetch_series(client, code, name) for code, name in SERIES.items())
            )
        return [record for batch in results for record in batch]
