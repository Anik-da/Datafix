# DataFix backend functionality audit

Audit date: 2026-11-19. Server tested with `LLM_ENABLED=false` and local SQLite. Evidence files under this directory contain real HTTP responses and downloaded exports.

## Checklist

| Area | Status | Evidence / limits |
|---|---|---|
| FastAPI startup, `/health`, OpenAPI/Swagger | WORKING | Live server at `http://127.0.0.1:8010`; health returned 200. Swagger is `/docs`. |
| CORS | WORKING | OPTIONS preflight for `http://localhost:5173` returned 200 and matching allow-origin. |
| Error envelope | WORKING | Unsupported extension 415, renamed PDF 415, malformed CSV 400; responses include code/message/details/request_id. |
| CSV validation and upload limits | WORKING | Valid CSV upload 201; centralized default limit is 5 MiB. Encoding, malformed rows, duplicate headers and limits are covered by the backend suite. |
| Clean-data baseline | WORKING | `datafix_1000_clean.csv`: 1,000 rows, 10 columns, 0 issues and 0 proposals. |
| Dirty data profiling/detection | WORKING | `datafix_1000_dirty.csv`: 1,001 rows including the injected duplicate, 10 columns, 12 issue signatures, 6 proposals. Detectors include missing/placeholder, duplicate, invalid email/numeric/date format, category/whitespace inconsistency, anomaly and cross-column date rule. |
| Diagnoses/evidence/confidence | WORKING | Live analysis includes affected row IDs, supporting evidence and hypotheses. Confidence is null where no calibrated evidence supports a value. |
| Typed proposals and preview/RippleGuard | WORKING | Proposal simulations include impact metrics, invariants and gate reasons. Live proposal lanes included auto_apply, needs_approval and refused. |
| Approval/rejection/bulk review | WORKING | Approved the edited city proposal; bulk rejected two other proposals; refused proposal approval returned 409. Rejected proposals were absent from applied operation history. |
| Manual proposal editing | WORKING | Live edit of `city`, `row_90`, from `BENGALURU ` to `Bengaluru`; version 2, re-simulated and still required approval. |
| Apply/atomicity/operation history | WORKING | Live apply returned 200/applied with 2 operations. Existing regression test injects a failed invariant and confirms no partial writes. |
| Repeat apply | WORKING after fix | Initial live repeat returned `aborted` because a manual proposal was executed twice. Fixed by skipping recorded applied proposals; regression test and live repeat returned `applied` with 0 new operations. |
| Undo/reapply/replay | WORKING after fix | Live small-fixture run exercised apply → undo → verify → reapply → verify; both replay checks matched. A second bug where undo left status `applied` was fixed; undo now restores proposal review state and appends audit history. |
| Verification | WORKING | Dirty run: replay match true, issues 12 → 9, previously valid cells damaged 0. |
| Exports | WORKING | Cleaned CSV, report, modification log, recipe and passport all returned 200; JSON parsed, CSV parsed, output hashes checked. |
| Trust Passport / fingerprints / uncertainty | WORKING | Live passport digest independently recomputed; original and cleaned hashes matched. Uncertainty returned 200 with bounded rows. Pattern responses are included in live analysis. |
| Compatibility profile | WORKING | `POST /api/v1/datasets/profile` returned 200. |
| Dedicated GET run retrieval | NOT IMPLEMENTED | There is no `GET /api/v1/runs/{run_id}` route; run state is retrieved through analysis, operations and exports. |
| Student sample dataset | NOT TESTED | `sample_student_data(1).csv` is not in the workspace. |
| Official Problem Statement 01 PDF | NOT TESTED | No PDF is present. The engineering review itself states that the official PS was not seen. |
| Supabase live | NOT TESTED | No URL/service-role or secret key configured; local SQLite was exercised. Mocked adapter coverage is included in the automated suite. |
| Groq live in this audit | NOT TESTED | A key and Qwen model setting are present, but this audit explicitly ran deterministic mode (`LLM_ENABLED=false`). No new live request was made. |
| Frontend | OUT OF SCOPE | No frontend application code changed. Swagger is the interactive API test interface. |

## Actual repair example

Run `648fdf5c-7bcc-4597-b44b-6146b6f8fa57` contained `city` row `row_90` value `BENGALURU `. The user edit proposed `Bengaluru`, version 2; the gate still required approval. The operation history records a user `manual_edit` with 1 changed cell and an automatic `normalize_date` with 1 changed cell. Duplicate removal and placeholder nulling were rejected and left unchanged. Final verification reported 12 issues before, 9 after, replay matched, and 0 previously valid cells damaged. The exported dirty-run CSV therefore retains 1,001 rows because the duplicate-removal proposal was rejected.

## Bugs fixed during this audit

1. Repeated apply attempted to execute a manual edit using its stale original value and returned `aborted`. Applied proposals are now skipped idempotently.
2. Undo marked the operation inactive but left proposal status `applied`, preventing reapply. Undo now restores `approved`/`pending`/`rejected` as appropriate and records an audit event. A live follow-up confirmed the undone proposal was actually applied again.

The two fixes have regression coverage; full suite result is in `TEST_RESULTS.md`.
