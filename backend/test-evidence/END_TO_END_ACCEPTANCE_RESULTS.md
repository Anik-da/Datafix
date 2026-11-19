# End-to-End Backend Acceptance Results

Date: 2026-11-20. API: `http://127.0.0.1:8014`; Swagger: `http://127.0.0.1:8014/docs`.

## Canonical 1,000-row fixture workflow

Run `1b1a1f78-7266-446a-863a-1ff52d1d7769`; source fixture was not modified.

- Upload: HTTP 201. Uploaded SHA-256 matched fixture SHA-256 `3d00c55b6f5540a1b97a318c73bc4acd87a46902f28a91408cb1ff85845b6fff`.
- Analyze: HTTP 200; profile 1,001 input records × 10 columns (1,000 base records plus one injected duplicate); 12 grouped findings and 6 proposals.
- Ground truth: 13/13 planted error cases matched expected detector and row reference. This is positive-case coverage; a representative clean negative set was not used for precision.
- Decisions: all eligible approval proposals received explicit approval (HTTP 200). Attempting to approve the refused proposal returned HTTP 409 (`invalid_decision_state`).
- Apply: HTTP 200, `status=applied`; 4 active operations.
- History: HTTP 200; 4 ledger records.
- Verify: HTTP 200; replay hash matched, 12→8 findings, 4 resolved, 0 introduced, 0 valid-cell damage.
- Cleaned export: HTTP 200, `text/csv`, parsed as 1,000 rows × 10 columns with uniform row widths.
- Quality report, modification log, recipe and Trust Passport: each HTTP 200, `application/json`, all parsed successfully.

Proposal decisions and API response details are in `api-responses/final_audit_1000_*.json`. Export files are in `exports/final_audit_1000_*`.

## Browser-to-backend edited lifecycle

Run `98b99b4c-63de-4ec2-aa1c-6be592fdeef9` exercised the actual React app, not Swagger alone:

- Upload 201 → analyze 200 → edit proposal version 2 (HTTP 200) → explicit approval (200) → apply (200) → history (200) → verify (200) → each of five exports (200).
- Manual correction: synthetic fixture placeholder `N/A` to known original `standard`; Safety Gate required approval. The operation history records `manual_edit`, `decided_by=user`, one cell changed. Two other automatic operations were applied.
- Verification: replay matched; 12→10 grouped findings, 2 resolved, 0 introduced, 0 previously valid cells damaged.
- Every browser-downloaded file matched the API artifact bytes by SHA-256. CSV parsed as 31 rows × 10 columns; all four JSON outputs parsed. Passport reports original and cleaned hashes and `verified` status.

Downloaded evidence: `exports/manual_edit_e2e_cleaned.csv`, `manual_edit_e2e_report.json`, `manual_edit_e2e_log.json`, `manual_edit_e2e_recipe.json`, `manual_edit_e2e_passport.json`.

## Other checks

- CORS preflight from documented origin `http://localhost:5173`: HTTP 200; allowed origin echoed correctly.
- OpenAPI: live and checked-in `docs/openapi.json` each contain the same 15 paths; no path differences found.
- Frontend route scan: all 9 route URL forms rendered; final scan had 0 console and HTTP errors.
- Backend tests: 48 passed.
- Supabase: not live acceptance-tested. Current runtime storage backend is local. Existing live probe evidence shows HTTP 404 `PGRST205` because `public.datafix_runs` is missing from the remote schema cache; no Supabase lifecycle write/restart/retrieve claim is made.
- Groq: current configuration reports enabled/model/key-presence, but this acceptance did not make a new authenticated inference request. Configuration is not treated as proof of live inference.

## Commands and local URLs

- `npm run build` (from `frontend/`): PASS; Vite reports a large-chunk advisory for the 533 kB main bundle.
- `python -m pytest -q` (from `backend/`): 48 passed.
- Frontend: `http://127.0.0.1:5173/#/app`
- API health: `http://127.0.0.1:8014/health`
- Swagger: `http://127.0.0.1:8014/docs`

See `frontend/test-evidence/COMPLETE_FUNCTIONAL_AUDIT.md` for defects fixed and limitations.
