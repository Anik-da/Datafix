# DataFix Output Correctness Report

## Live run

- API: `http://127.0.0.1:8014`; frontend: `http://127.0.0.1:5173` (`frontend/.env` sets `VITE_API_BASE_URL=http://127.0.0.1:8014`). Both responded HTTP 200 for health/page checks.
- Browser-triggered sample run: `89cf6dba-7bf7-4f3f-b1d4-9479d4874114`; upload HTTP 201 and analysis HTTP 200; rendered overview showed 1,001 records, 14 columns, 4 missing cells, one exact duplicate, and 18 findings. Browser console errors: 0.
- API lifecycle run: `18a5a30a-8881-4740-b1b5-42c80fa6d947`; analysis returned 18 findings, 9 typed proposals: 2 auto-apply, 6 approval-required, 1 refused.
- Source/upload SHA-256: `ef629d7b8330522397c35d66191d6de6dac74360a956c9b08d4b730311281a4b` on both sides.

## Output correctness

- All 15 known injected cases (14 base manifest errors plus one extra-field structural mismatch) had a matching issue by expected detector and affected row.
- `row_150` was identified as one extra field; its value was preserved and exported under `__unexpected_extra_1`, not silently discarded.
- A city standardization was approved; exact duplicate removal was rejected. Attempting to approve the refused ambiguous-date proposal returned HTTP 409.
- Apply returned HTTP 200 and applied two operations (approved city mapping and automatic date normalization). The rejected duplicate and refused date proposal were not applied.
- Verification returned HTTP 200; replay matched; issue groups changed 18 → 15 (3 resolved, 0 introduced); valid cells damaged: 0. The anomaly at `row_131`, the rejected duplicate, and structural mismatch remained.
- A clean-truth 1,000-row upload had 2 anomaly findings at `row_131` and 0 proposals. The manifest marks those outliers as correct values; they were preserved. This is not a “zero findings on every valid dataset” claim: unusual valid outliers are intentionally surfaced as review findings.
- The browser overview explained the structural row-width mismatch and showed measured profile values. The static storyboard now explicitly says it is illustrative and does not claim an actual verification or passport hash.

## Explanation-safety bug

The live LLM explanation converted a supplied hypothesis into a certain statement and dismissed the other supplied hypothesis. I changed `backend/app/llm.py` so model-written explanatory prose is not returned verbatim: only the validated hypothesis choice is rendered with “Possible explanation” / “not confirmed,” and other supplied hypotheses are retained. A regression test feeds overconfident model prose and asserts it is not exposed.

The running server process on port 8014 was not restarted because the process-restart command was rejected by the environment’s automatic command policy. Therefore the fix is covered by the new automated test, but the already-running process still needs a restart before the browser can demonstrate that guarded text. Do not treat the live HTTP narrative as post-fix evidence.

Artifacts and full HTTP payloads: `test-evidence/live_walkthrough/`. Screenshots: `test-evidence/walkthrough-before-live.png` and `test-evidence/walkthrough-live-run.png`.
