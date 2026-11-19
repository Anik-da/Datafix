# Multi-format ingestion

## CSV

CSV uploads keep their original bytes and SHA-256. The parser detects UTF-8,
UTF-8 BOM, UTF-16 BOM, Windows-1252, and comma, semicolon, tab, or pipe
delimiters. Repaired CSV exports use the detected delimiter and UTF-8 encoding.
Malformed quoted records and ambiguous schemas remain errors; recoverable rows
with a different field count are preserved by the existing structural recovery.

## XLSX

`POST /api/v1/datasets/worksheets` accepts an XLSX file and returns worksheet
names plus the active worksheet. Upload the selected name as the `worksheet`
form field to `POST /api/v1/runs`; if omitted, DataFix analyzes the active
worksheet. The exact original workbook bytes are retained. Analysis and repairs
operate on the selected sheet's canonical dataset through the shared pipeline.

The cleaned export writes changed values into a copy of the original workbook.
Unselected worksheets, sheet names, styles, and unchanged formulas are retained.
Formula cells are protected from repair proposals and manual edits. Operations
that remove rows or alter columns are intentionally left unresolved for XLSX so
formula references and workbook layout are not silently shifted. If a workbook
would require a row/column structure change, export returns a structured conflict
instead of returning a lossy workbook.

This adapter targets standard `.xlsx` workbooks. It does not claim JSON support,
and it does not guarantee preservation of Excel extensions or embedded objects
that openpyxl does not support. Original workbook bytes remain available in the
run's immutable source record.

## Future adapters

Format adapters expose `parse` and `export_cleaned`; they return a canonical
string DataFrame for the existing profile, detect, diagnose, fingerprint,
propose, simulate, RippleGuard, Safety Gate, apply and verify services. JSONL,
Parquet, and database connectors are not implemented.
