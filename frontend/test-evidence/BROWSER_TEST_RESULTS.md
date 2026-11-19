# Browser Test Results

## Environment

- Microsoft Edge headless through the locally installed `puppeteer-core` runtime; no new project dependency was added.
- Frontend: `http://127.0.0.1:5173`.
- Backend: `http://127.0.0.1:8014`.
- Fixture: `backend/tests/fixtures/datafix_dirty.csv` (synthetic, 31 data rows; unchanged).
- Canonical fixture acceptance was also run through real HTTP requests using `backend/tests/fixtures/datafix_1000_dirty.csv`.

## Real browser workflow

Run ID: `98b99b4c-63de-4ec2-aa1c-6be592fdeef9`.

1. Upload + analysis: HTTP 201 + HTTP 200.
2. Findings displayed: 12, matching analysis response.
3. Selected placeholder suggestion and edited `N/A` to the fixture’s known original `standard`.
4. Proposal edit: HTTP 200; proposal version 2, operation `manual_edit`, new simulation and Safety Gate result `needs_approval`.
5. Approval: HTTP 200; proposal version 2 explicitly approved.
6. Apply: HTTP 200; operation ledger recorded `manual_edit` by `user`, plus two `auto` operations.
7. Verify: HTTP 200; replay matched, 12→10 findings, 2 resolved, 0 introduced, 0 previously valid cells damaged.
8. History: HTTP 200; actual operation history rendered.
9. Five browser downloads: each export returned HTTP 200. CSV content parsed as 31×10; JSON report/log/recipe/Passport parsed. All downloaded file SHA-256 values matched the corresponding API bytes.

Additional checks: refusing to approve a refused proposal returned HTTP 409 with `invalid_decision_state`. CORS preflight for `http://localhost:5173` returned HTTP 200 and `Access-Control-Allow-Origin: http://localhost:5173`.

## Route, device and browser diagnostics

- 9 route URL forms rendered: `/`, `/walkthrough`, `/app`, `/intake`, and all five run tabs.
- Desktop viewport: 1440×960. Mobile Intake viewport: 390×844; document width remained 390px. A Tab key moved focus to a button with a visible outline.
- Final route scan: 0 console errors and 0 HTTP errors. Final export browser run: 0 console errors and five successful artifact requests.
- An earlier browser run logged a missing `/favicon.ico` 404. The favicon was added; the later route scan returned no errors.
- Tablet, reduced-motion, screen-reader, all chart filters, drag/drop, forced API failure UI, rejection, and undo/reapply were not fully tested in the browser.

## Browser evidence

- `frontend/test-evidence/screenshots/intake.png`
- `frontend/test-evidence/screenshots/overview-31-row-run.png`
- `frontend/test-evidence/screenshots/export.png`
- `frontend/test-evidence/screenshots/mobile-intake.png`
- `backend/test-evidence/api-responses/browser_manual_edit_live_run.json`
- `backend/test-evidence/exports/manual_edit_e2e_*`
