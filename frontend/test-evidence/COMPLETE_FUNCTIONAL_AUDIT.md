# Complete Functional Audit

Audit date: 2026-11-20 (Asia/Kolkata). Local environment: frontend `http://127.0.0.1:5173`, FastAPI `http://127.0.0.1:8014`.

## Result

The deterministic CSV workflow passed an actual browser-to-API run through upload, analysis, proposal revision, approval, apply, verification, history and all five downloads. A separate 1,000-row canonical fixture run matched all 13 planted error cases and completed apply, verification and export checks. The site is not fully complete: drag/drop and validation/error recovery were not all exercised in a real browser, semantic schema discovery and recipe import are not connected, and Supabase is not the active storage backend.

- Route cases: 9 URL forms rendered (walkthrough `/`, `/walkthrough`; intake `/app`, `/intake`; and the five run tabs). Six operational screens were inspected in-browser; the two walkthrough aliases rendered but their tour controls were not exhaustively tested.
- Interaction groups: 46; 23 PASS, 20 PARTIALLY_WORKING, 3 NOT_CONNECTED, 0 FAIL, 0 BLOCKED. Details are in `BUTTON_AND_INTERACTION_RESULTS.md`.
- Browser console / HTTP errors after the favicon fix: 0 observed in the route scan and export run. One earlier scan found `/favicon.ico` 404; a DataFix favicon was added and a subsequent scan returned no HTTP or console errors.
- Production build: PASS (`npm run build`; Vite reports a 533 kB main JavaScript chunk warning).
- Backend suite: 48 passed.

## Correctness evidence

Canonical fixture `backend/tests/fixtures/datafix_1000_dirty.csv` remained unchanged. Its SHA-256 was `3d00c55b6f5540a1b97a318c73bc4acd87a46902f28a91408cb1ff85845b6fff`, equal to the uploaded run hash. The backend returned 12 grouped issues and 6 proposals; all 13 expected injected error cases were represented by matching detector category and row reference. This measures planted-positive coverage (13/13); precision against a representative clean negative dataset was not calculated.

The approved canonical run completed with 4 active operations. Verification reported 12 → 8 grouped issues, 4 resolved, 0 introduced, 0 previously valid cells damaged, and a matching replay hash. The cleaned CSV parsed as 1,000 data rows × 10 columns. All five export endpoints returned 200; JSON artifacts parsed, and the CSV had uniform row widths.

The browser run `98b99b4c-63de-4ec2-aa1c-6be592fdeef9` revised `N/A` → `standard` on `note` (synthetic fixture ground truth). The backend returned a version 2 `manual_edit` proposal with a fresh simulation and `needs_approval` gate. The user approval reached the API, then apply created a `manual_edit` operation. Verification reported replay match, 12 → 10 findings, 2 resolved, 0 introduced, and 0 valid-cell damage. All five browser downloads matched their corresponding API artifact SHA-256.

## Bugs fixed during this audit

1. Manual editing showed “Revision saved” but immediately re-ran analysis and discarded the revised proposal before approval. The page now maps and keeps the proposal returned by the edit endpoint, including its new operation, simulation and gate state. A new real browser test verified version 2, explicit reapproval, a `manual_edit` ledger operation and successful replay.
2. History displayed proposal previews as applied operations and used a fabricated one-cell fallback. It now displays actual operation-ledger records, including active/undone state and real recorded counts.
3. History described a local JSON summary as a replayable recipe. It is now labeled as an operation summary; the actual recipe remains in Export.
4. The modification log was labeled CSV although the API returns JSON. The export label and filename now say JSON.
5. Approval/rejection network failures were unhandled in Repair Studio. The page now displays the error and prevents duplicate decisions while a request is pending.
6. Passport download opened a raw endpoint in a new tab. It now uses the download helper and displays errors in the page.
7. The browser requested a missing favicon (404). Added an inline favicon; later browser scan had no HTTP errors.

## Integration and limits

- Supabase: not live-tested as the active backend. Current settings select local storage. Existing audit evidence records a prior authenticated `PGRST205`/HTTP 404 because `public.datafix_runs` is absent from the Supabase schema cache. The current acceptance runs persisted locally; do not treat them as Supabase persistence proof.
- Groq: configuration is present according to local settings, but this audit did not make a new authenticated Groq request. Health/configuration flags alone are not proof of live inference.
- Semantic smart-schema discovery and recipe import/replay-on-another-dataset are not connected in the current API.
- Relationship checks detect supported explicit date-order and arithmetic inconsistencies. General foreign-key/orphan relationship discovery is not established by these tests.
- Drag-and-drop, oversize/empty selection, all error recovery states, tablet layout, reduced-motion behavior, reject action, undo/reapply, and every chart/filter/tooltip were not all exercised in the real browser; they remain partial or are identified separately below.

## Evidence files

- `backend/test-evidence/api-responses/final_audit_1000_summary.json`
- `backend/test-evidence/api-responses/browser_manual_edit_live_run.json`
- `backend/test-evidence/exports/final_audit_1000_*`
- `backend/test-evidence/exports/manual_edit_e2e_*`
- `frontend/test-evidence/screenshots/`
- `frontend/test-evidence/BROWSER_TEST_RESULTS.md`
