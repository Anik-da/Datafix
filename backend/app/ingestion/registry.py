from __future__ import annotations

from pathlib import Path

from ..errors import InputProblem
from .base import FileAdapter, ParsedDataset
from .csv_adapter import CsvAdapter
from .xlsx_adapter import XlsxAdapter

_ADAPTERS: list[FileAdapter] = [CsvAdapter(), XlsxAdapter()]


def get_adapter(filename: str) -> FileAdapter:
    suffix = Path(filename).suffix.lower()
    for adapter in _ADAPTERS:
        if suffix in adapter.extensions:
            return adapter
    raise InputProblem(415, "unsupported_format", "Supported upload formats are .csv and .xlsx.")


def parse_dataset(filename: str, raw: bytes, selection: str | None = None) -> ParsedDataset:
    adapter = get_adapter(filename)
    return adapter.parse(raw, filename, selection)


def list_worksheets(filename: str, raw: bytes) -> tuple[list[str], str]:
    adapter = get_adapter(filename)
    if not hasattr(adapter, "worksheet_names"):
        raise InputProblem(
            415, "unsupported_format", "Worksheet selection is available for .xlsx workbooks only."
        )
    return adapter.worksheet_names(raw)
