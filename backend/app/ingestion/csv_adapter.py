from __future__ import annotations

import io
from typing import Any

import pandas as pd

from .base import ParsedDataset


class CsvAdapter:
    format_name = "csv"
    extensions = (".csv",)

    def parse(self, raw: bytes, filename: str, selection: str | None = None) -> ParsedDataset:
        from ..services import parse_csv_details

        frame, headers, encoding, delimiter = parse_csv_details(raw)
        return ParsedDataset(frame, headers, {"format": self.format_name, "encoding": encoding, "delimiter": delimiter})

    def export_cleaned(self, original: bytes, frame: pd.DataFrame, metadata: dict[str, Any]) -> bytes:
        visible = frame[[c for c in frame.columns if not str(c).startswith("__datafix_")]]
        delimiter = metadata.get("delimiter", ",")
        return visible.apply(lambda col: col.map(_csv_safe)).to_csv(index=False, sep=delimiter, lineterminator="\n").encode("utf-8")


def _csv_safe(value: Any) -> str:
    from ..lifecycle import csv_safe

    return csv_safe(value)
