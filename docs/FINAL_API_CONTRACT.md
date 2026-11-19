# DataFix API contract snapshot

The generated source of truth is `docs/openapi.json`; generated TypeScript is `frontend/src/api/generated.ts` (also mirrored at `frontend/src/lib/generated-types.ts`). The OpenAPI file was inspected and includes the routes listed below. The current working tree contains CSV and XLSX ingestion; JSON is not advertised as supported.

## Routes in the generated OpenAPI document

- `GET /health`
- `POST /api/v1/runs`
- `POST /api/v1/datasets/worksheets`
- `POST /api/v1/runs/{run_id}/analyze`
- `POST /api/v1/runs/{run_id}/proposals/{proposal_id}/edit`
- `POST /api/v1/runs/{run_id}/decisions`
- `POST /api/v1/runs/{run_id}/bulk-decisions`
- `POST /api/v1/runs/{run_id}/apply`
- `GET /api/v1/runs/{run_id}/operations`
- `POST /api/v1/runs/{run_id}/verify`
- `POST /api/v1/runs/{run_id}/undo/{op_id}`
- `GET /api/v1/runs/{run_id}/export/passport`
- `GET /api/v1/runs/{run_id}/export/{artifact}`
- `GET /api/v1/runs/{run_id}/uncertainty`
- `POST /api/v1/datasets/profile`

For exact field names, types, nullability, request bodies, and error schemas, consult the generated OpenAPI JSON rather than hand-maintained examples.

## Format behavior

- Run upload accepts CSV and XLSX. XLSX clients first call the worksheet-listing endpoint and pass the selected worksheet on upload.
- Analysis and repair use the common canonical dataset/lifecycle pipeline.
- Cleaned export returns the appropriate CSV or XLSX media type and filename extension.
- XLSX export preserves the selected workbook/sheets where possible and rejects unsafe formula overwrites; duplicate-row removal is withheld for XLSX.
- JSON, JSONL, Parquet, and database connectors are not currently supported.
