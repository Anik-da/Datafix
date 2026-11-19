# Testing DataFix

## Backend

From `backend/`, install the test/quality extras and run the full suite with external calls disabled:

```powershell
python -m pip install -e ".[test,quality]"
$env:LLM_ENABLED = "false"
python -m pytest -q
ruff check app tests
ruff format --check app tests
python generate_openapi.py
```

The tests use deterministic synthetic fixtures under `backend/tests/fixtures/`, a temporary SQLite store, and mocked external service behavior where required. They do not imply a live Groq request or Supabase lifecycle persistence. A live integration test must use rotated/configured credentials and report the authenticated operation separately.

## Frontend and contract

From repository root:

```powershell
cd frontend
npm ci
npm run build
npm audit
npm exec -- openapi-typescript ../docs/openapi.json --output src/api/generated.ts
```

The generated API types must be regenerated after OpenAPI changes. The build runs TypeScript's `tsc --noEmit` before Vite.

## API smoke test

Start the backend in one terminal from `backend/`:

```powershell
$env:LLM_ENABLED = "false"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check health and Swagger at `http://127.0.0.1:8000/health` and `/docs`. Upload a fixture, analyze the returned run, then use only IDs and payload shapes returned by the API/OpenAPI. Do not use fixture files as repair outputs; copy them before manual workflows. See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for paths and lifecycle order.

## Interpreting checks

- A unit/API test pass demonstrates only the tested cases.
- Mocked Supabase/Groq tests do not demonstrate live authentication or persistence.
- Local HTTP requests are not browser-rendered frontend acceptance tests.
- `npm audit` and `pip check` check dependency metadata/vulnerability advisories, not application security correctness.
- MyPy currently reports unresolved static type errors; see `CODE_QUALITY_AUDIT.md`.
