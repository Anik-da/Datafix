# Walkthrough End-to-End Test

## Result

- Frontend: `http://127.0.0.1:5173/#/walkthrough` responded HTTP 200.
- Backend configured by `frontend/.env`: `http://127.0.0.1:8014`; `/health` responded HTTP 200.
- A headless browser clicked the live sample CTA, observed upload and analysis network activity, and navigated to `/runs/89cf6dba-7bf7-4f3f-b1d4-9479d4874114/overview`.
- Overview rendered actual backend profile/issues; browser console/page errors: none.

## API lifecycle (separate real run)

| Stage | HTTP | Result |
|---|---:|---|
| Upload fixture | 201 | SHA matched the fixture bytes. |
| Analyze | 200 | 1,001 × 14 declared fields, 18 issue groups, 9 proposals. |
| Approve city mapping | 200 | Proposal `prp_15064eaf25cd`, `map_values`, `city`. |
| Reject duplicate removal | 200 | Proposal `prp_e2175c3d04ba`; held out of apply. |
| Attempt to override refused date proposal | 409 | Proposal `prp_95f619e8873f`; refusal remained blocked. |
| Apply | 200 | `applied`; two operations recorded. |
| Operation history | 200 | Two persisted operations fetched in a separate request. |
| Verify | 200 | Replay matched; 18 → 15 issues; 3 resolved, 0 introduced, 0 valid-cell damage. |
| Cleaned CSV export | 200 | Valid CSV, 1,001 data rows × 15 exported columns; preserved overflow value present. |
| Quality report | 200 | Valid JSON. |
| Modification log | 200 | Valid JSON. |
| Recipe | 200 | Valid JSON. |
| Trust Passport | 200 | Valid JSON. |

Rejected duplicate removal remained unapplied. The refused proposal did not enter the operation history. The full raw response bodies and export artifacts are in `test-evidence/live_walkthrough/`.

## What this test does not claim

The browser test validates the live CTA through upload, analysis and overview. Proposal decisions/apply/verify/exports were exercised as real HTTP API calls on a separate temporary run, not clicked through the browser UI. This task did not exercise every filter, sorting control, undo control, chart, export download button or XLSX workflow end to end. The local API process must be restarted to load the final explanation guard.
