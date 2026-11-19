from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from typing import Any

import pandas as pd
from openpyxl import load_workbook

from ..config import settings
from ..errors import InputProblem
from .base import ParsedDataset


class XlsxAdapter:
    """Excel adapter: edits only values in the selected sheet, retaining workbook structure/styles."""

    format_name = "xlsx"
    extensions: tuple[str, ...] = (".xlsx",)

    def worksheet_names(self, raw: bytes) -> tuple[list[str], str]:
        try:
            book = load_workbook(BytesIO(raw), read_only=True, data_only=False)
        except Exception as exc:
            raise InputProblem(
                400, "malformed_xlsx", "The uploaded Excel workbook could not be parsed."
            ) from exc
        return list(book.sheetnames), book.active.title

    def parse(self, raw: bytes, filename: str, selection: str | None = None) -> ParsedDataset:
        if not raw:
            raise InputProblem(400, "empty_file", "The uploaded workbook is empty.")
        if not raw.startswith(b"PK"):
            raise InputProblem(
                415,
                "unsupported_content",
                "The uploaded .xlsx file is not a valid Office workbook.",
            )
        try:
            book = load_workbook(BytesIO(raw), read_only=False, data_only=False)
        except Exception as exc:
            raise InputProblem(
                400, "malformed_xlsx", "The uploaded Excel workbook could not be parsed."
            ) from exc
        names = list(book.sheetnames)
        sheet_name = selection or book.active.title
        if sheet_name not in names:
            raise InputProblem(
                422,
                "unknown_worksheet",
                "Select a worksheet present in the workbook.",
                {"worksheets": names},
            )
        sheet = book[sheet_name]
        last_row = max(
            (r for r in range(1, sheet.max_row + 1) if any(c.value is not None for c in sheet[r])),
            default=0,
        )
        last_col = max(
            (
                c
                for c in range(1, sheet.max_column + 1)
                if any(sheet.cell(r, c).value is not None for r in range(1, last_row + 1))
            ),
            default=0,
        )
        if last_row < 1 or last_col < 1:
            raise InputProblem(400, "missing_header", "The selected worksheet has no header row.")
        headers = [_cell_text(sheet.cell(1, c).value) for c in range(1, last_col + 1)]
        if any(not x.strip() for x in headers):
            raise InputProblem(422, "empty_header", "Worksheet column headers cannot be empty.")
        if len(set(headers)) != len(headers):
            raise InputProblem(
                422,
                "duplicate_headers",
                "The selected worksheet contains duplicate column headers.",
            )
        if last_col > settings.max_columns:
            raise InputProblem(
                422,
                "column_limit_exceeded",
                "The selected worksheet exceeds the configured column limit.",
                {"limit": settings.max_columns},
            )
        rows = [
            [_cell_text(sheet.cell(r, c).value) for c in range(1, last_col + 1)]
            for r in range(2, last_row + 1)
        ]
        if len(rows) > settings.max_rows:
            raise InputProblem(
                422,
                "row_limit_exceeded",
                "The selected worksheet exceeds the configured row limit.",
                {"limit": settings.max_rows},
            )
        frame = pd.DataFrame(rows, columns=headers, dtype="string")
        frame.attrs["source_headers"] = headers
        if any(len(v) > settings.max_cell_chars for row in rows for v in row):
            raise InputProblem(
                422,
                "cell_too_long",
                "A worksheet cell exceeds the configured maximum length.",
                {"limit_characters": settings.max_cell_chars},
            )
        formula_cells = [
            {"row_id": f"row_{r - 1}", "column": headers[c - 1]}
            for r in range(2, last_row + 1)
            for c in range(1, last_col + 1)
            if sheet.cell(r, c).data_type == "f"
        ]
        return ParsedDataset(
            frame,
            headers,
            {
                "format": self.format_name,
                "worksheet_names": names,
                "selected_worksheet": sheet_name,
                "header_row": 1,
                "source_row_count": len(rows),
                "source_column_count": len(headers),
                "headers": headers,
                "formula_cells": formula_cells,
            },
        )

    def export_cleaned(
        self, original: bytes, frame: pd.DataFrame, metadata: dict[str, Any]
    ) -> bytes:
        from ..lifecycle import csv_safe

        book = load_workbook(BytesIO(original), read_only=False, data_only=False)
        sheet_name = metadata.get("selected_worksheet")
        if sheet_name not in book.sheetnames:
            raise InputProblem(
                409, "worksheet_unavailable", "The original worksheet is unavailable for export."
            )
        sheet = book[sheet_name]
        visible_columns = [str(c) for c in frame.columns if not str(c).startswith("__datafix_")]
        if len(visible_columns) != metadata.get("source_column_count") or len(
            frame
        ) != metadata.get("source_row_count"):
            raise InputProblem(
                409,
                "xlsx_structure_change_unsupported",
                "This workbook export cannot change row or column structure; no workbook data was exported.",
            )
        if visible_columns != metadata.get("headers"):
            raise InputProblem(
                409,
                "xlsx_schema_change_unsupported",
                "This workbook export cannot change worksheet headers.",
            )
        for col_idx, name in enumerate(visible_columns, start=1):
            if _cell_text(sheet.cell(1, col_idx).value) != name:
                raise InputProblem(
                    409,
                    "xlsx_header_changed",
                    "The original worksheet headers changed after upload.",
                )
        for row_idx, row in enumerate(
            frame[visible_columns].itertuples(index=False, name=None), start=2
        ):
            for col_idx, value in enumerate(row, start=1):
                cell = sheet.cell(row_idx, col_idx)
                text = "" if pd.isna(value) else csv_safe(value)
                # Leave unchanged cells untouched so formulas, number formats, and cell types survive.
                if _cell_text(cell.value) != text:
                    if cell.data_type == "f":
                        raise InputProblem(
                            409,
                            "xlsx_formula_edit_unsupported",
                            "A repair would change a formula cell; the workbook was not exported.",
                        )
                    cell.value = text or None
        output = BytesIO()
        book.save(output)
        return output.getvalue()


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)
