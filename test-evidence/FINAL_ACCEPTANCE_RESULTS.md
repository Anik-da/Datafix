# Final acceptance results

Audit date: 2026-11-20. This file records checked results only; it does not treat planned or mocked behavior as live proof.

## Automated checks

- Backend: `python -m pytest backend/tests -q --tb=short` — **48 passed**, 28.21 seconds.
- Frontend: `npm run build` — **passed** (`tsc --noEmit` and Vite production build).
- Live local API health: `GET http://127.0.0.1:8014/health` — **200**.
- Live frontend document: `GET http://127.0.0.1:5173/` — **200**.

## Live local API workflows

### CSV

A CSV using Windows-1252 and semicolon separators uploaded with HTTP 201 and analyzed with HTTP 200. The parser detected `cp1252` and `;`; the original hash matched the uploaded bytes. Response evidence: `backend/test-evidence/api-responses/csv_detection_live_run.json`.

### XLSX

The live API workflow exercised worksheet listing (200), upload (201), analysis (200), proposal edit (200), approval (200), apply (200), verification (200), cleaned XLSX export (200), and passport (200). It retained the source SHA-256 and checked the exported workbook's worksheet names, an unaffected worksheet, formula and formatting. Replay matched. Evidence: `backend/test-evidence/api-responses/xlsx_live_run.json` and `backend/test-evidence/sample-inputs/datafix_dirty_workbook.xlsx`.

This was a live local FastAPI test, not a live Supabase test. It did not exercise every feature listed in the master assignment or every frontend interaction.

## Supabase

Authenticated REST probe: HTTP 404, code `PGRST205`, message says `public.datafix_runs` is not in the schema cache. Storage mode is local. No live database/storage/restart acceptance is claimed. See `docs/SUPABASE_LIVE_SETUP.md`.

## Feature scope not accepted as complete

JSON ingestion, recipe import/reuse, multi-dataset relationship joins, all requested semantic schema confirmation, and a full browser walkthrough of every advanced visualization were not verified as complete. The status table in `docs/FINAL_IMPLEMENTATION_STATUS.md` is authoritative for limitations.
