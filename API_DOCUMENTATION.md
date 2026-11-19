# DataFix API

## Contract source of truth

[`docs/openapi.json`](docs/openapi.json) is generated from the FastAPI application by running `python generate_openapi.py` from `backend/`. Frontend declarations at `frontend/src/api/generated.ts` are generated from that JSON. Use the OpenAPI document for exact field names, request/response models, nullability, validation constraints, and status codes; do not copy schemas into handwritten clients.

Interactive Swagger UI is served at `/docs`; health is `/health`. The default local API origin is `http://127.0.0.1:8000`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service/configuration health summary; does not prove external storage is live. |
| `POST` | `/api/v1/runs` | Multipart CSV/XLSX upload (`file`; optional XLSX `worksheet`); stores original bytes and creates a run. |
| `POST` | `/api/v1/datasets/worksheets` | Multipart XLSX workbook inspection; returns worksheet names and active sheet. |
| `POST` | `/api/v1/runs/{run_id}/analyze` | Profiles and analyzes the uploaded run, producing evidence-backed issues and typed proposals. |
| `POST` | `/api/v1/runs/{run_id}/proposals/{proposal_id}/edit` | Creates a proposal revision, re-simulates it and re-runs gate checks. |
| `POST` | `/api/v1/runs/{run_id}/decisions` | Records approval/rejection for eligible proposals. |
| `POST` | `/api/v1/runs/{run_id}/bulk-decisions` | Records a batch of eligible proposal decisions. |
| `POST` | `/api/v1/runs/{run_id}/apply` | Applies eligible approved proposals atomically. |
| `GET` | `/api/v1/runs/{run_id}/operations` | Returns operation history. |
| `POST` | `/api/v1/runs/{run_id}/verify` | Checks issue changes, invariants and replay hash. |
| `POST` | `/api/v1/runs/{run_id}/undo/{op_id}` | Attempts to undo the latest active operation. |
| `GET` | `/api/v1/runs/{run_id}/uncertainty` | Returns paginated record/column uncertainty derived from run evidence and decisions. |
| `GET` | `/api/v1/runs/{run_id}/export/passport` | Generates and downloads a run Trust Passport JSON. |
| `GET` | `/api/v1/runs/{run_id}/export/{artifact}` | Downloads `cleaned`, `report`, `log`, `recipe`, or `passport` artifact. |
| `POST` | `/api/v1/datasets/profile` | Compatibility endpoint that returns a profile without creating a run. |

CSV upload is limited by `DATAFIX_MAX_UPLOAD_BYTES` (default 5 MiB); row, column, CORS, and cell limits are environment-configurable. CSV supports delimiter and encoding detection and retains row-structure discrepancies for analysis. XLSX requires worksheet selection when the active sheet is not desired. JSON upload is not supported.

## Error handling

Errors use the `ErrorEnvelope` model declared in OpenAPI, with a stable `code`, human-readable `message`, `details`, and request identifier. Common outcomes include `400` malformed/empty input, `404` unknown run/proposal, `409` stale or invalid lifecycle state, `413` upload too large, `415` unsupported type, and `422` invalid request/data constraints. Exact endpoint response codes are defined in the generated specification.

## Reproducible local request

```powershell
curl.exe -F "file=@samples/walkthrough_dirty.csv" http://127.0.0.1:8000/api/v1/runs
```

Take the returned `run.id`, then:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/runs/<run-id>/analyze
```

Use issue/proposal IDs and the exact schema from the analysis response/OpenAPI for review and apply requests. Never submit a decision for a proposal whose gate does not require review.

## Security note

The current API does not authenticate callers or isolate tenants. A run UUID is not an authorization mechanism. Keep the API local/private until authentication and authorization are designed and tested. Do not place Groq or Supabase secret keys in frontend variables or requests.
