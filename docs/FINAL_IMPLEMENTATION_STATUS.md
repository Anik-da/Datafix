# DataFix implementation status

Audit date: 2026-11-20

This report distinguishes implemented and tested behavior from unimplemented work. It does not treat a route, schema, mock, or configured credential as proof of a complete integration.

## Current status

| Area | Status | Evidence / limitation |
|---|---|---|
| Deterministic CSV ingestion and analysis | IMPLEMENTED_AND_TESTED | Backend suite passes 48 tests. Live CSV upload detected Windows-1252 and semicolon delimiter; evidence is in `backend/test-evidence/api-responses/csv_detection_live_run.json`. |
| XLSX ingestion, worksheet selection, shared repair lifecycle, export | IMPLEMENTED_AND_TESTED | Live workflow exercised upload, analysis, edit/approval, apply, verification, export. Other sheets, formula, style and original bytes were checked. Evidence: `backend/test-evidence/api-responses/xlsx_live_run.json`. |
| JSON ingestion/export | NOT_IMPLEMENTED | No JSON adapter or passing end-to-end lifecycle test. |
| RippleGuard | IMPLEMENTED_AND_TESTED | Simulation impact is calculated and is used by the safety gate; regression tests cover impacts and aggregate drift. This is not a claim that every listed impact dimension is modeled. |
| Error fingerprinting | IMPLEMENTED_AND_TESTED | Deterministic fingerprints are produced from detected issues; tests cover repeatability and cross-run decision isolation. |
| Uncertainty response | IMPLEMENTED_AND_TESTED | Paginated API response is derived from run analysis and decisions; tested in the backend suite. |
| Manual proposal editing | IMPLEMENTED_AND_TESTED | Revisions are re-simulated and require a fresh decision; covered by backend/API tests and live XLSX workflow. |
| Trust Passport | IMPLEMENTED_AND_TESTED | Generated from run state with file hashes, operations and verification; tested by API tests. |
| Smart schema discovery | PARTIALLY_IMPLEMENTED | Profiling/type inference exists. The requested complete semantic-role inference and user confirmation workflow is not established by end-to-end evidence. |
| Relationship Guardian | PARTIALLY_IMPLEMENTED | Deterministic within-dataset cross-column checks exist. No multi-table or multi-worksheet foreign-key joining is claimed. |
| Context-aware anomalies | PARTIALLY_IMPLEMENTED | Deterministic anomaly checks exist. User-configured domain constraints and all requested anomaly categories are not proven complete. |
| Recipe reuse/import | NOT_IMPLEMENTED | Recipe export exists; cross-dataset import, compatibility review, fresh simulation and approval workflow are not implemented/tested as a complete feature. |
| Supabase lifecycle persistence | BLOCKED_BY_USER_CONFIGURATION | A real authenticated REST probe returned HTTP 404 / `PGRST205`, stating `public.datafix_runs` is not in the schema cache. The checked-in SQL has not been applied/recognized by the project. Storage mode is `local`, so the live app is not using Supabase. |
| Groq | IMPLEMENTED_NOT_FULLY_TESTED | Optional settings/client and deterministic fallback exist. Current credentials/model were not live-tested in this audit; previous diagnostic reported 403, so no live success is claimed. |
| Frontend production build | IMPLEMENTED_AND_TESTED | `npm run build` passed. HTTP GET to the local frontend returned 200. A full interactive browser acceptance test of every screen was not completed in this audit. |
| Advanced feature visualization | IMPLEMENTED_NOT_FULLY_TESTED | Real-data Overview, Repair Studio, Proof and Export views added. Live Passport and uncertainty endpoints were checked. Browser screenshots, console inspection, and full responsive click-through were unavailable; see `test-evidence/visual-design-acceptance.md`. |

## Verification just run

- `python -m pytest backend/tests -q --tb=short` — 48 passed, 28.21 seconds.
- `npm run build` in `frontend` — TypeScript and Vite build passed.
- `GET http://127.0.0.1:8014/health` — HTTP 200.
- `GET http://127.0.0.1:5173/` — HTTP 200.
- Supabase REST read probe — HTTP 404, `PGRST205`; missing table in schema cache.

## Known blockers / not claimed

1. Apply `backend/docs/supabase_schema.sql` in the Supabase SQL Editor, create the private `datafix` Storage bucket, then set `DATAFIX_STORAGE_BACKEND=supabase` in `backend/.env` and restart. Re-run a complete persistence-after-restart test before claiming Supabase integration.
2. The workflow does not include JSON support or recipe reuse/import.
3. XLSX safeguards intentionally withhold row deletion and formula-cell overwrites. Openpyxl round-tripping may not preserve every unsupported Excel extension or embedded object; those have not been certified.
4. No deployment/live public URL is claimed. The URLs above are local development endpoints.

## Secret handling

The backend `.env` exists and is Git-ignored. Secret values are intentionally omitted. A Supabase secret key was included in chat content earlier; rotate it in Supabase and update only the local backend `.env` before relying on it.
