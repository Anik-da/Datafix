# Advanced feature acceptance evidence

## Automated baseline and regression

- Command: `python -m pytest backend/tests -q --tb=short`
- Result: **45 passed** (run after structural ingestion and uncertainty metadata filtering).
- The combined run API test exercises actual deterministic detector outputs, fingerprints, proposal simulation/impact, heatmap, manual revision and reapproval, refusal enforcement, apply, verification, operation history, Passport, and export hash checks. Core data calculations are not mocked.

## Real HTTP structural CSV run

The supplied `messy_customer_data.csv` was uploaded to the updated local FastAPI server before restart on port 8011. The run ID is `7482677f-356c-43fa-bcfb-2d4ae04380f6`.

| Stage | HTTP | Result |
|---|---:|---|
| Health | 200 | API available; LLM disabled |
| Upload | 201 | 25 rows, 9 declared columns; source SHA-256 matched; 2 structural warnings |
| Analysis | 200 | 13 issues, 6 proposals; structural issue includes physical lines 20 and 21; 1 structural removal proposal required approval |
| Decision | 200 | Human approval recorded for proposal `prp_cf9228a64811` |
| Apply | 200 | Applied; operation history had 2 active operations (one automatic plus the approved structural operation) |
| Verify | 200 | Replay matched |
| Cleaned CSV | 200 | 25 rows, 9 columns; extra value removed after approval; missing trailing values remain blank |
| Quality report / log / recipe / Passport | 200 each | JSON parsed; log contains removed extra value and original field position; Passport reports 25×9 and verified replay |
| Undo / reapply | 200 each | Verification replay matched after both operations |

The original file remained byte-for-byte unchanged. Export checks were performed without printing customer records. This live HTTP run predates the latest additive Passport fields and RippleGuard risk label; those changes are covered by the final automated suite and regenerated OpenAPI/TypeScript contract. The persistent run was confirmed retrievable after restart; the current backend is on port 8014.

## Running endpoints

- Visual workbench: `http://127.0.0.1:5174/`
- Updated backend: `http://127.0.0.1:8014/`
- Swagger UI: `http://127.0.0.1:8014/docs`
- OpenAPI: `http://127.0.0.1:8014/openapi.json`

The frontend dev process was started with `VITE_API_BASE_URL=http://127.0.0.1:8014`; the backend CORS allowlist includes the preview origin. LLM is disabled in the backend process.

## Combined five-feature live HTTP scenario

The latest server on port 8014 was exercised over network HTTP using the
canonical dirty synthetic fixture (`backend/tests/fixtures/datafix_dirty.csv`),
with no mocks for the DataFix calculations. Run ID:
`b7191b40-d2f8-46ea-9987-c4ef37811423`.

- Health / upload / analysis: `200 / 201 / 200`.
- Analysis returned 12 evidence-backed issues and 6 proposals. All 12 issues
  had fingerprints; simulations included measured risk labels `low`, `moderate`,
  `high`, and `unknown`.
- Heatmap: `200`, 10 user columns and 5 requested paginated records.
- Manual edit: `200`, proposal version 2, fresh simulation measured one changed
  cell and returned `needs_approval`.
- Revised proposal approval / second proposal rejection: `200 / 200`.
- Refused-proposal approval attempt: `409 invalid_decision_state`.
- Apply / verify / operation history / Passport: `200 / 200 / 200 / 200`;
  replay matched and the Passport included 6 proposal summaries.
- Cleaned CSV, quality report, modification log and recipe: `200` each; all
  exported artifact SHA-256 values matched the Passport hashes.

This is a real network-backed combined run after the additive Passport and
RippleGuard schema changes. Customer data was not used in this scenario.
