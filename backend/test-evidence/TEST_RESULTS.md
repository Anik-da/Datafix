# Test results

Audit execution used the locally running FastAPI process with `LLM_ENABLED=false` and isolated local SQLite storage.

## Automated tests

Command from `backend/`:

```powershell
$env:LLM_ENABLED='false'
$env:PYTHONPATH='.'
python -m pytest -q
```

Result: **42 passed in 14.01s**, 0 failed. This was run after both audit fixes. Relevant coverage includes detectors, proposal simulation/invariants, refused approval, manual edit and stale/out-of-range validation, bulk review, original preservation, atomic failure rollback, operation history, apply idempotency, undo/reapply/replay, exports, fingerprints, uncertainty pagination and passport digest reproducibility.

## Live HTTP requests

Base URL: `http://127.0.0.1:8010`. Full JSON request/response envelopes are saved in `api-responses/`.

| Request | Status | Observed result |
|---|---:|---|
| `GET /health` | 200 | API `ok`; LLM disabled; default upload limit 5,242,880 bytes. |
| `OPTIONS /api/v1/runs` with documented origin | 200 | `Access-Control-Allow-Origin: http://localhost:5173`. |
| Upload clean fixture | 201 | 1,000 rows, 10 columns. |
| Analyze clean fixture | 200 | 0 issues, 0 proposals. |
| Upload dirty fixture | 201 | Original SHA-256 recorded and matched local source bytes. |
| Analyze dirty fixture | 200 | 1,001 rows (includes injected duplicate), 10 columns, 12 issues, 6 proposals. |
| Edit proposal | 200 | `city` row `row_90`; `BENGALURU ` → `Bengaluru`; proposal version 2; gate remained `needs_approval`. |
| Approve edited proposal | 200 | Explicit decision recorded. |
| Bulk reject remaining eligible proposals | 200 | Two proposals rejected. Their IDs did not appear in applied operation history. |
| Attempt approval of refused proposal | 409 | `invalid_decision_state`; refused proposal stayed blocked. |
| Apply | 200 | `applied`; 2 operations: user manual edit and automatic date normalization. |
| Operation history | 200 | Two entries; persistent across requests. |
| Verify | 200 | Replay matched; issue signatures 12 → 9; valid cells damaged 0. |
| Cleaned/report/log/recipe/passport exports | 200 each | CSV parsed as 1,001 rows because duplicate removal was rejected; JSON exports parsed. Passport file hashes and canonical digest independently matched. |
| Compatibility profile | 200 | Profile returned for dirty CSV. |
| Unsupported `.txt` | 415 | `unsupported_format` error envelope. |
| PDF content renamed `.csv` | 415 | `unsupported_content` error envelope. |
| Malformed CSV field count | 400 | `malformed_csv`, expected/actual field details returned. |

Apply idempotency initially failed with `status: aborted`. After the fix, repeating apply returned 200, `status: applied`, 0 new operations. Undo initially left proposal state `applied`, blocking reapply. That was fixed; a live fixture run verified `apply → undo → verify → reapply → verify`; the undone proposal was reapplied and both replay checks matched. See `apply_repeat.json`, `apply_repeat_after_fix.json`, and `undo_reapply_*.json`.

## Exports

Artifacts are saved under `exports/`; `audit_summary.json` records actual filenames, sizes and paths. JSON parsing, CSV parsing, original/cleaned hashes and passport digest were checked. The dirty fixture’s original file remained byte-for-byte unchanged.

## Integrations

- **Supabase:** not live-tested; no backend URL plus secret/service-role key configured. The server used local SQLite. Existing adapter tests are mocks, not live evidence.
- **Groq:** not called during this audit. The audit process deliberately disabled LLM assistance to get deterministic evidence. A key-presence boolean and model setting were read without printing the secret; no authenticated request result is claimed here.
- **Student sample:** not available in this workspace, so not tested.
- **Problem Statement 01 PDF:** not available, so requirements could not be checked against that source document.
