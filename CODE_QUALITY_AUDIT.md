# DataFix code-quality audit

Audit date: 2026-11-20

Scope: repository quality, API contract generation, regression checks and security/configuration review. This report records measured results; it does not treat mocks, configuration, a successful build, or prior reports as proof of live integrations.

## Summary

The deterministic API and frontend build pass their current regression checks. The OpenAPI document and TypeScript declarations were regenerated from the same contract. The repository has a clear adapter → canonical dataset → analysis/lifecycle structure, but the backend remains a modular monolith: API orchestration, analysis, and lifecycle modules are still large. Static type checking is **not clean** (199 MyPy errors remain). Public deployment is **not ready** because run APIs have no authentication/tenant isolation, Supabase lifecycle persistence is unverified, and no hosted deployment exists.

## Architecture and refactoring

- Documented the product flow, module boundaries, trust boundaries, local setup, API, contribution and test practices in `README.md`, `ARCHITECTURE.md`, `API_DOCUMENTATION.md`, `CONTRIBUTING.md`, `TESTING.md`, and `CODE_QUALITY_AUDIT.md`.
- Added `backend/app/errors.py` as a shared typed home for expected upload/ingestion errors, removing adapter dependencies on the service layer for this error type.
- Replaced the FastAPI `app.openapi` method reassignment with a small `DataFixFastAPI` subclass that emits binary multipart schemas without monkey-patching an instance method.
- Fixed duplicate `DecisionState.state` declarations and the `EvidenceKind.count` name collision while preserving the serialized evidence value `"count"`.
- Corrected adapter protocol annotations and centralized generated API types at `frontend/src/api/generated.ts`. Removed the duplicate generated declarations at `frontend/src/lib/generated-types.ts`.
- Aligned frontend API defaults and upload limits with backend settings; retained local defaults as development configuration.
- Applied Ruff formatting and import/lint cleanup to backend application and test files.
- Added setuptools package discovery so editable installs include only `app*`, avoiding accidental package discovery of test/runtime directories.
- Updated `.gitignore` to cover environment files, Python/Node build state, local databases/storage, runtime artifacts, private datasets and `*.egg-info`.

The backend still has large `main.py` (routes/orchestration), `services.py` (profiling/detection/diagnosis/proposals), and `lifecycle.py` (simulation/gates/apply/verification) modules. Existing tests protect behavior, but a broader router/service extraction is outstanding. The frontend is separated into routes/pages, components, state/context, API client and generated types; this audit did not conduct an exhaustive component-by-component dead-code review.

## Contract and generated files

- Regenerated `docs/openapi.json` with `backend/generate_openapi.py` from the backend working directory.
- Regenerated `frontend/src/api/generated.ts` with `openapi-typescript` using `../docs/openapi.json` as input.
- `frontend` production build runs `tsc --noEmit` before Vite and passed after generation.
- `backend/actual_analysis_response.json` validated as an `AnalysisResponse` Pydantic model: 17 issues and 8 proposals. This validates shape only; it does not prove how that saved file was originally produced.
- `docs/FINAL_API_CONTRACT.md` now points to the single generated TypeScript file.

Commands:

```powershell
# backend directory
$env:LLM_ENABLED = "false"
.\.venv\Scripts\python.exe generate_openapi.py
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m mypy app --ignore-missing-imports --show-error-codes

# frontend directory
npm exec -- openapi-typescript ../docs/openapi.json --output src/api/generated.ts
npm run build
npm audit --audit-level=moderate
```

## Test and tool results

| Check | Result |
|---|---|
| Backend tests, isolated project venv, `LLM_ENABLED=false` | **48 passed**, 1 warning, 19.17 seconds. Warning: Starlette deprecates using `httpx` with `TestClient` and recommends `httpx2`. |
| Ruff lint (`app tests`) | **Passed**: all checks passed. |
| Ruff format check (`app tests`) | **Passed**: 19 files already formatted. |
| MyPy (`app`, `--ignore-missing-imports`) | **Failed**: 199 errors across `app/lifecycle.py` (109), `app/main.py` (50), and `app/services.py` (40). These are not suppressed; they need incremental type-boundary cleanup. |
| Clean Python venv dependency check (`pip check`) | **Passed**: no broken requirements found. |
| OpenAPI generation | **Passed**: `docs/openapi.json` generated. |
| OpenAPI TypeScript generation | **Passed**: generated `frontend/src/api/generated.ts`. |
| Frontend build (`tsc --noEmit && vite build`) | **Passed**. Vite reports the main JS bundle is 531.94 kB minified, above its 500 kB advisory threshold. |
| `npm audit --audit-level=moderate` | **Passed**: 0 vulnerabilities reported. |
| Fresh frontend dependency install | **Passed** in an isolated temporary directory: `npm ci` installed 73 packages and audited 80, 0 vulnerabilities. An initial in-repository `npm ci` failed with Windows `EPERM` while removing a locked native module; `npm install` restored dependencies and the subsequent build passed. It emitted cleanup warnings for three locked native modules. `package-lock.json` was unchanged. |
| Internal module-level import-cycle check | **Passed**: no cycles found among module-scope internal imports. Deferred imports inside parser/export functions remain intentionally lazy. |
| Tracked credential scan | **Passed**: no credential-pattern matches in tracked files. `backend/.env`, `frontend/.env`, local storage/database paths and `*.egg-info` are ignored. Only `.env.example` files are tracked. |
| Python dependency vulnerability audit | **Not run**: `pip-audit` is not installed. `pip check` checks dependency compatibility, not known CVEs. |
| Graphical browser acceptance | **Not completed**: the computer-use environment returned `Browsers: Local browser access is unavailable for this chat`. No physical cursor/keyboard interaction or screenshot evidence is claimed. |

The same 48-test suite also passed earlier in this work before the shared-error refactor; the final run above is after the refactor.

## Security and integrity review

- Backend environment files and local runtime data are Git-ignored; a scan of tracked files found no Groq/Supabase secret-pattern values.
- Upload parsing uses configured size/row/column/cell bounds and generated run IDs for storage paths; user filenames are reduced to a basename for display/metadata.
- Local SQLite statements use bound values. No user-controlled file path is used as a storage destination.
- API responses use a common error envelope and unexpected exceptions are logged server-side without returning stack traces. Request logs contain request ID, method, path and status, not row contents.
- CORS is configured with explicit origins; defaults are local development origins. Production origins must be set by environment.
- Supabase secrets remain backend-only. A secret key was exposed in conversation; **rotate it before use**. The project returned `404/PGRST205` for a missing `public.datafix_runs` table in prior live evidence. Current Supabase lifecycle persistence is not verified and its SQL schema/private bucket still need provisioning and a complete restart/persistence test.
- The API does not authenticate or tenant-isolate run access. Run IDs are not authorization. This is a blocker to public multi-user deployment.
- Groq is optional and disabled by default. This audit ran with `LLM_ENABLED=false`; it does not claim a current authenticated request. Historical reports conflict over later 403 status; current live model access is unverified and the deterministic fallback is the supported mode.
- `npm audit` found no known npm vulnerabilities. No Python CVE scanner was run.

## Actual implementation boundaries

- CSV and XLSX adapters use the same canonical analysis and repair lifecycle. JSON ingestion, recipe import/reuse, and JSONL/Parquet/database connectors are not implemented.
- RippleGuard impact, issue fingerprints, uncertainty output, manual proposal revisions, and Trust Passport are present in the tested local pipeline. Advanced schema discovery, multi-table relationship checks, and domain-configurable anomaly analysis remain partial; see `docs/FINAL_IMPLEMENTATION_STATUS.md`.
- Repair simulation, gate, apply, verification/replay, and undo are covered by backend tests, but this audit did not repeat a separate full real-server UI workflow.
- Supabase mocked adapter tests do not equal remote persistence. No Supabase credentials were used in this audit.
- Vercel/Render configuration and guides are preparation only. There is no deployed public URL.

## Remaining technical debt and blockers

1. Resolve the 199 MyPy errors without broad ignores; introduce typed request/run/storage boundaries and then type-check one module at a time.
2. Split large API orchestration, detection/proposal, and lifecycle modules into focused packages while keeping the regression suite green.
3. Replace the deprecated Starlette `TestClient`/httpx test combination when its supported replacement is confirmed for the dependency set.
4. Add authentication and per-user/tenant authorization before any public multi-user deployment.
5. Rotate the exposed Supabase key, provision schema and private bucket, and run a real persistence-after-restart lifecycle test.
6. Run a visual browser walkthrough and save genuine screenshots when browser access is available.
7. Add Python vulnerability scanning in CI and consider splitting the frontend bundle.
8. Do not claim the partially implemented or unsupported advanced features as complete; maintain the per-feature status report.

## Files changed in this milestone

- Root docs/config: `.gitignore`, `README.md`, `ARCHITECTURE.md`, `API_DOCUMENTATION.md`, `CONTRIBUTING.md`, `TESTING.md`, `SUPABASE_SETUP.md`.
- Backend: `backend/pyproject.toml`; `backend/app/config.py`, `errors.py`, `fingerprints.py`, `ingestion/base.py`, `ingestion/csv_adapter.py`, `ingestion/registry.py`, `ingestion/xlsx_adapter.py`, `lifecycle.py`, `llm.py`, `main.py`, `schemas.py`, `services.py`, `storage.py`; `backend/tests/fixtures/generate_fixture.py`, `generate_scale_fixture.py`, and `backend/tests/test_backend.py`.
- Contract/status docs: `docs/FINAL_API_CONTRACT.md`, `docs/LIMITATIONS.md`, `docs/openapi.json`.
- Frontend: `frontend/src/api/generated.ts`, `frontend/src/app/context/RunContext.tsx`, `frontend/src/components/story/data/demoState.ts`, `frontend/src/lib/api.ts`, and `frontend/src/lib/contract-types.ts`; removed duplicate `frontend/src/lib/generated-types.ts`.
- This report: `CODE_QUALITY_AUDIT.md`.

## GitHub status

The verified remote is `https://github.com/Anik-da/Datafix`, branch `main`. The staged diff passed whitespace and credential-pattern scans, and the changes were pushed to `main` as commit `acbe379990f6674a4c52b3b110744b77b08befc5`. `git ls-remote` confirmed the remote branch points to that commit. The working tree was clean after the push.
