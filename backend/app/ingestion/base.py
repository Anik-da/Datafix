from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd


@dataclass
class ParsedDataset:
    frame: pd.DataFrame
    headers: list[str]
    metadata: dict[str, Any]


class FileAdapter(Protocol):
    format_name: str
    extensions: tuple[str, ...]

    def parse(self, raw: bytes, filename: str, selection: str | None = None) -> ParsedDataset: ...

    def export_cleaned(
        self, original: bytes, frame: pd.DataFrame, metadata: dict[str, Any]
    ) -> bytes: ...
