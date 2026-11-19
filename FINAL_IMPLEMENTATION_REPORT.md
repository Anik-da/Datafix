# DataFix final implementation report

Audit date: 2026-11-20

## Work completed in this pass

- Fixed repeat analysis to return the saved analysis snapshot for `analyzed` and `applied` runs. This resolves the regression where repeating `POST /analyze` could return a different result and avoidable external explanation calls.
- Aligned the frontend API fallback with the documented local FastAPI port (`127.0.0.1:8000`).
- Aligned browser upload validation with the backend's default 5 MiB request limit (5,242,880 bytes).
- Added Vercel SPA rewrites and deployment/Supabase setup guides.
- Kept the existing CSV/XLSX deterministic pipeline and safety behavior; no new repair execution behavior was introduced.

## Verification

- Backend command from `backend/`: `$env:LLM_ENABLED='false'; python -m pytest -q` — **48 passed in 18.08s** after the analysis-idempotency fix. Groq was disabled for this verification.
- Frontend `npm run build` — **passed after the final API-base/upload-limit adjustment**. Vite emitted a non-failing advisory that the main JS chunk is 533 kB minified.
- Existing checked-in HTTP acceptance evidence covers upload, analysis, proposal edit/review, apply, history, verify/replay and exports on synthetic fixtures. It reports replay match, zero previously valid cells damaged, and downloadable artifacts with matching hashes.
- Local browser automation was unavailable in this session (`Browsers: Error: Local browser access is unavailable for this chat`). No claim is made that a new graphical click-through or screenshot capture was completed.

## Actual sample result (existing HTTP evidence)

The canonical dirty synthetic fixture uploaded as 1,001 rows × 10 columns (1,000 source records plus an injected duplicate), with 12 findings and 6 typed proposals: 2 auto-apply, 3 approval-required, 1 refused. Four approved/eligible operations were applied; verification reduced findings 12 → 8, replay matched, and previously valid-cell damage was 0. The cleaned CSV parsed as 1,000 × 10. This evidence is in `backend/test-evidence/api-responses/` and `backend/test-evidence/exports/`.

## Honest completion status

- Deterministic CSV lifecycle: implemented and tested.
- XLSX shared lifecycle: implemented and acceptance-tested; formula/structural destructive changes remain restricted.
- Five pipeline features (RippleGuard, fingerprints, uncertainty data, manual proposal revisions, Passport): implemented and covered by API tests/evidence.
- Smart schema discovery, broad relationship analysis, and contextual anomalies: partial, bounded to supported inferred profiles/rules.
- Recipe export exists; import/reuse with fresh compatibility analysis is not implemented.
- Supabase adapter exists, but hosted lifecycle persistence is not live-verified. Previous evidence records HTTP 404 `PGRST205` for the missing remote table.
- No Vercel or Render deployment was performed.
- A complete rendered browser walkthrough was not possible because local browser access was unavailable.

## Credential handling

The Supabase secret key shared in chat is treated as exposed. Rotate it before production use. It was not copied into source files, frontend configuration, logs, or this report.
