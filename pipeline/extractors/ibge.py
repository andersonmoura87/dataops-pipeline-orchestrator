"""
Extractor for IBGE — population estimates by state (UF).
Aggregate 6579 / variable 9324 = "População residente estimada".
Docs: https://servicodados.ibge.gov.br/api/docs/agregados
"""
import httpx
import structlog

from ..http import get_json

logger = structlog.get_logger()

# periodos/-1 = latest available year, N3[all] = every state.
URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/6579"
    "/periodos/-1/variaveis/9324?localidades=N3[all]"
)


class IBGEExtractor:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def fetch_all(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            payload = await get_json(client, URL)
        records = self._flatten(payload)
        logger.info("ibge.fetched", records=len(records))
        return records

    @staticmethod
    def _flatten(payload: list[dict]) -> list[dict]:
        # The IBGE response nests states under resultados[].series[], with the
        # actual values keyed by year inside "serie". Flatten to one row per (state, year).
        rows: list[dict] = []
        for variable in payload:
            for result in variable.get("resultados", []):
                for entry in result.get("series", []):
                    locality = entry.get("localidade", {})
                    for year, value in entry.get("serie", {}).items():
                        rows.append(
                            {
                                "state_code": locality.get("id"),
                                "state_name": locality.get("nome"),
                                "year": year,
                                "population": value,
                            }
                        )
        return rows
