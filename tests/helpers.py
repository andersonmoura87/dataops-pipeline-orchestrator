import json
from pathlib import Path

_FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> object:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
