# Local DataFix demo

## Current local URLs

- Frontend: http://127.0.0.1:5173/#/app
- Backend health: http://127.0.0.1:8014/health
- Swagger UI: http://127.0.0.1:8014/docs

These are local-only URLs and require the corresponding development servers to remain running.

## Start the services

PowerShell, repository root:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

In another PowerShell window:

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8014
```

## Demonstrate CSV/XLSX

Open the frontend URL, upload a CSV, or choose an XLSX and select a worksheet when prompted. Analyze, review proposals, edit only where offered, approve/reject, apply eligible changes, verify, then download cleaned data and reports from Export. Alternatively use Swagger at `/docs`; follow the request schemas shown there.

The live XLSX evidence is `backend/test-evidence/api-responses/xlsx_live_run.json`; CSV encoding/delimiter evidence is `backend/test-evidence/api-responses/csv_detection_live_run.json`.

## Run checks

```powershell
python -m pytest backend/tests -q --tb=short
cd frontend
npm run build
```

Supabase is not active in the current local environment. Follow `docs/SUPABASE_LIVE_SETUP.md` before demonstrating remote persistence. No JSON support is claimed.
