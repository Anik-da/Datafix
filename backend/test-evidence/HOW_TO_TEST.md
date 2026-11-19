# How to test DataFix locally

## Server

The backend is currently running at **http://127.0.0.1:8010**. Open Swagger at **http://127.0.0.1:8010/docs**. The current process uses `LLM_ENABLED=false` and isolated local storage so results are deterministic. It will stop if the development process/session is closed.

If it is no longer running, open PowerShell:

```powershell
cd C:\Users\anikd\OneDrive\Documents\ChatGPT\Datafix\backend
$env:LLM_ENABLED='false'
$env:DATAFIX_STORAGE_DIR="$env:TEMP\datafix-local-test-storage"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Then open `http://127.0.0.1:8010/docs`. In Swagger, use **Try it out**. For upload, choose `POST /api/v1/runs`, select a `.csv` file for the `file` form field, and execute. Copy `run.id` from the response.

## Exact workflow

Set the returned run ID once in PowerShell (replace the sample value):

```powershell
$runId = 'PASTE_RUN_ID_HERE'
$base = 'http://127.0.0.1:8010'
```

Upload a fixture from `backend/`:

```powershell
curl.exe -X POST "$base/api/v1/runs" -F "file=@tests/fixtures/datafix_1000_dirty.csv"
```

Analyze and preview actual issues, evidence, proposals, RippleGuard impacts and gate decisions:

```powershell
curl.exe -X POST "$base/api/v1/runs/$runId/analyze"
```

To approve/reject, copy proposal IDs from analysis. Only `needs_approval` proposals are eligible; `refused` returns 409:

```powershell
curl.exe -X POST "$base/api/v1/runs/$runId/decisions" `
  -H "Content-Type: application/json" `
  -d '{"decisions":[{"proposal_id":"PASTE_ELIGIBLE_ID","action":"approve"}]}'
```

Bulk decision example (all IDs must be eligible and explicit):

```powershell
curl.exe -X POST "$base/api/v1/runs/$runId/bulk-decisions" `
  -H "Content-Type: application/json" `
  -d '{"proposal_ids":["PASTE_ID_1","PASTE_ID_2"],"action":"reject"}'
```

Manual edit is optional. Copy a proposal ID, affected stable `row_id`, `column`, and exact current value from the response. The edit must pass type/category/range/staleness checks and will be re-simulated; it is not applied until approved and then applied:

```powershell
curl.exe -X POST "$base/api/v1/runs/$runId/proposals/PASTE_PROPOSAL_ID/edit" `
  -H "Content-Type: application/json" `
  -d '{"row_id":"row_90","column":"city","original_value":"BENGALURU ","edited_value":"Bengaluru","reason":"Use the reviewed existing category"}'
```

Apply eligible automatic and approved proposals atomically, then inspect operation history and replay verification:

```powershell
curl.exe -X POST "$base/api/v1/runs/$runId/apply"
curl.exe "$base/api/v1/runs/$runId/operations"
curl.exe -X POST "$base/api/v1/runs/$runId/verify"
curl.exe "$base/api/v1/runs/$runId/uncertainty?offset=0&limit=100"
```

Download the five artifacts. `-OJ` uses the server's `Content-Disposition` filename:

```powershell
curl.exe -OJ "$base/api/v1/runs/$runId/export/cleaned"
curl.exe -OJ "$base/api/v1/runs/$runId/export/report"
curl.exe -OJ "$base/api/v1/runs/$runId/export/log"
curl.exe -OJ "$base/api/v1/runs/$runId/export/recipe"
curl.exe -OJ "$base/api/v1/runs/$runId/export/passport"
```

The corresponding tested lifecycle and output files are included in `api-responses/` and `exports/`. The importable collection is `postman/DataFix_API_Tests.postman_collection.json`; in Postman set `baseUrl`, upload a file in the form-data request, then use the live `run_id` returned by upload. Inspect analysis before selecting proposal IDs—IDs are generated per run.
