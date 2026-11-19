# DataFix backend

FastAPI backend for CSV and XLSX ingestion, deterministic profiling and
evidence-backed issue analysis. Both formats use the same canonical repair
pipeline. Local mode works without API keys or external services.

## Run locally

```powershell
cd backend
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Upload CSV or XLSX to `POST /api/v1/runs` using multipart field `file`, then analyze
with `POST /api/v1/runs/{run_id}/analyze`. For XLSX, call
`POST /api/v1/datasets/worksheets` first and pass the chosen sheet as the
`worksheet` multipart field. Interactive docs are at `/docs` and
health is at `/health`. See [backend/ENVIRONMENT.md](backend/ENVIRONMENT.md) for
configuration and optional service setup.

## Open the frontend

Start a second terminal from `frontend/`:

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`. Set `VITE_API_BASE_URL` in `frontend/.env` if the
backend uses a different origin. More frontend details are in
[frontend/README.md](frontend/README.md).

## Deterministic analysis and repair lifecycle

The detector suite reports measured profiles, row references, evidence and
diagnosis hypotheses. Typed proposals are simulated against copies and gated by
deterministic invariants. The API supports approval/rejection, atomic apply,
operation history, replay verification, last-operation undo, and CSV/JSON
exports. Unsupported operation kinds are refused. The immutable original upload
is retained separately from the active working dataset. CSV export escapes
spreadsheet formula prefixes. XLSX exports retain the original workbook and
unmodified worksheets; row/column removal and formula-cell edits remain
unresolved to avoid damaging workbook structure or formulas.

The optional Groq client is disabled by default and uses deterministic fallback
explanations. Supabase persistence is an optional backend adapter that requires
a service-role key configured on the backend. The published client key is not a
backend credential. Neither service has been live-tested in this environment;
see the environment guide for the distinction and setup steps.

The compatibility route `POST /api/v1/datasets/profile` is retained. The
frontend is a React and TypeScript API client; the generated TypeScript types
are derived from OpenAPI.

## Tests and generated contracts

From `backend/`:

```powershell
python -m pytest -q
python generate_openapi.py
npx --yes openapi-typescript ../docs/openapi.json --output ../frontend/src/api/generated.ts
```

The canonical OpenAPI file is `docs/openapi.json`; generated types are at
`frontend/src/api/generated.ts`. The compact fixture and separate 1,000-row
benchmark, each with an error manifest, are under `backend/tests/fixtures/`.

## Synthetic sample and benchmark

The full 1,000-row clean/dirty sample, manifest, deterministic generator and
benchmark live in `samples/`. Regenerate with `python samples/generate_dataset.py`
and run the end-to-end scorecard with `python samples/benchmark.py`. The compact
and 1,000-row detector regression fixtures remain in
`backend/tests/fixtures/`.

## Backend architecture and deployment notes

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md),
[limitations](docs/LIMITATIONS.md), [audit checklist](docs/BACKEND_AUDIT.md),
[QA checklist](docs/QA_CHECKLIST.md), [demo script](docs/DEMO_SCRIPT.md), and
[Render preparation](backend/RENDER.md). Render preparation is not deployment;
Supabase and Groq remain unverified with live credentials.
