import httpx
import pytest
import respx
from helpers import load_fixture

from pipeline.extractors.bacen import BASE_URL, SERIES, BacenExtractor
from pipeline.extractors.ibge import URL as IBGE_URL
from pipeline.extractors.ibge import IBGEExtractor


@respx.mock
async def test_bacen_extractor_fetches_all_series_and_tags_rows():
    series = load_fixture("bacen_series_433.json")
    for code in SERIES:
        respx.get(BASE_URL.format(code=code)).mock(return_value=httpx.Response(200, json=series))

    rows = await BacenExtractor().fetch_all()

    assert len(rows) == len(series) * len(SERIES)
    codes = {row["series_code"] for row in rows}
    assert codes == set(SERIES)
    assert all("series_name" in row and "valor" in row for row in rows)


@respx.mock
async def test_bacen_extractor_retries_on_transient_5xx():
    route = respx.get(BASE_URL.format(code="433"))
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json=load_fixture("bacen_series_433.json")),
    ]
    for code in ("11", "10813"):
        respx.get(BASE_URL.format(code=code)).mock(
            return_value=httpx.Response(200, json=[])
        )

    rows = await BacenExtractor().fetch_all()

    assert route.call_count == 2
    assert any(row["series_code"] == "433" for row in rows)


@respx.mock
async def test_ibge_extractor_flattens_nested_payload():
    respx.get(IBGE_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("ibge_population.json"))
    )

    rows = await IBGEExtractor().fetch_all()

    assert len(rows) == 3
    sp = next(row for row in rows if row["state_code"] == "35")
    assert sp["state_name"] == "São Paulo"
    assert sp["year"] == "2021"
    assert sp["population"] == "46649132"


@respx.mock
async def test_bacen_extractor_raises_on_persistent_client_error():
    respx.get(BASE_URL.format(code="433")).mock(return_value=httpx.Response(404))
    for code in ("11", "10813"):
        respx.get(BASE_URL.format(code=code)).mock(return_value=httpx.Response(200, json=[]))

    with pytest.raises(httpx.HTTPStatusError):
        await BacenExtractor().fetch_all()
