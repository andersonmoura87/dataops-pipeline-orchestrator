"""
Transforms raw Bacen SGS records into clean, validated EconomicIndicator objects.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

import structlog
from pydantic import BaseModel, ValidationError, field_validator

logger = structlog.get_logger()


class EconomicIndicator(BaseModel):
    source: str = "bacen"
    series_code: str
    series_name: str
    reference_date: date
    value: Decimal
    unit: str

    @field_validator("reference_date", mode="before")
    @classmethod
    def parse_date(cls, v: str) -> date:
        # Bacen returns dates as "DD/MM/YYYY"
        day, month, year = v.split("/")
        return date(int(year), int(month), int(day))

    @field_validator("value", mode="before")
    @classmethod
    def parse_value(cls, v: str) -> Decimal:
        try:
            return Decimal(str(v).replace(",", "."))
        except InvalidOperation as exc:
            raise ValueError(f"Cannot parse value: {v!r}") from exc


UNITS = {
    "433": "%",
    "11": "% a.a.",
    "10813": "BRL",
}


def transform_bacen(raw: list[dict]) -> list[EconomicIndicator]:
    clean = []
    errors = 0
    for row in raw:
        try:
            record = EconomicIndicator(
                series_code=row["series_code"],
                series_name=row["series_name"],
                reference_date=row["data"],
                value=row["valor"],
                unit=UNITS.get(row["series_code"], ""),
            )
            clean.append(record)
        except (ValidationError, ValueError, KeyError) as exc:
            errors += 1
            logger.warning("bacen.transform_error", row=row, error=str(exc))
    logger.info("bacen.transformed", total=len(raw), clean=len(clean), errors=errors)
    return clean
