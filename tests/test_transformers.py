from datetime import date
from decimal import Decimal

from pipeline.transformers.bacen import transform_bacen
from pipeline.transformers.ibge import transform_ibge


def _bacen_row(code: str, name: str, data: str, valor: str) -> dict:
    return {"series_code": code, "series_name": name, "data": data, "valor": valor}


def test_transform_bacen_parses_dates_values_and_units():
    raw = [_bacen_row("433", "IPCA", "01/05/2024", "0,46")]

    [record] = transform_bacen(raw)

    assert record.source == "bacen"
    assert record.reference_date == date(2024, 5, 1)
    assert record.value == Decimal("0.46")
    assert record.unit == "%"


def test_transform_bacen_skips_invalid_rows_but_keeps_good_ones():
    raw = [
        _bacen_row("11", "SELIC", "01/05/2024", "10.5"),
        _bacen_row("11", "SELIC", "not-a-date", "10.5"),
        _bacen_row("11", "SELIC", "01/06/2024", "n/a"),
    ]

    clean = transform_bacen(raw)

    assert len(clean) == 1
    assert clean[0].reference_date == date(2024, 5, 1)


def test_transform_ibge_coerces_types_and_drops_missing_values():
    raw = [
        {"state_code": "35", "state_name": "São Paulo", "year": "2021", "population": "46649132"},
        {"state_code": "53", "state_name": "Distrito Federal", "year": "2021", "population": "..."},
    ]

    clean = transform_ibge(raw)

    assert len(clean) == 1
    assert clean[0].year == 2021
    assert clean[0].population == 46649132
