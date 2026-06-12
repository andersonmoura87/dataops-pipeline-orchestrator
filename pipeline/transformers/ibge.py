"""
Transforms raw IBGE rows into validated PopulationEstimate objects.
"""
import structlog
from pydantic import BaseModel, ValidationError, field_validator

logger = structlog.get_logger()

# IBGE uses these tokens to signal "no data available" for a locality/period.
_MISSING = {"...", "-", "..", "X"}


class PopulationEstimate(BaseModel):
    state_code: str
    state_name: str
    year: int
    population: int

    @field_validator("population", mode="before")
    @classmethod
    def parse_population(cls, v: str | int) -> int:
        if isinstance(v, str) and v.strip() in _MISSING:
            raise ValueError(f"missing population value: {v!r}")
        return int(v)


def transform_ibge(raw: list[dict]) -> list[PopulationEstimate]:
    clean: list[PopulationEstimate] = []
    errors = 0
    for row in raw:
        try:
            clean.append(PopulationEstimate(**row))
        except (ValidationError, ValueError) as exc:
            errors += 1
            logger.warning("ibge.transform_error", row=row, error=str(exc))
    logger.info("ibge.transformed", total=len(raw), clean=len(clean), errors=errors)
    return clean
