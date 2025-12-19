from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class _Strings:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    def get(self, key: str, **kwargs) -> str:
        parts = key.split(".")
        value: Any = self._data
        for part in parts:
            if not isinstance(value, dict) or part not in value:
                raise KeyError(f"String '{key}' not found")
            value = value[part]
        if not isinstance(value, str):
            raise KeyError(f"String '{key}' does not resolve to a string")
        return value.format(**kwargs) if kwargs else value


@lru_cache(maxsize=1)
def _load_data() -> dict[str, Any]:
    strings_path = Path(__file__).resolve().parents[1] / "strings.yaml"
    with open(strings_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


STRINGS = _Strings(_load_data())


def t(key: str, **kwargs) -> str:
    return STRINGS.get(key, **kwargs)
