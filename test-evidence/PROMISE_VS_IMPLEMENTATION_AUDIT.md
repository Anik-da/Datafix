# DataFix Promise vs. Implementation Audit

Date: 2026-11-20. Scope: the supplied assignment, checked-in handoff/README/docs, current frontend, backend routes, live API and one browser-to-API run.

## Reference availability

| Reference | Status | Evidence |
|---|---|---|
| Landing page / walkthrough | Working and verified | Inspected `/walkthrough` and its rendered browser view at `http://127.0.0.1:5173/#/walkthrough`. |
| Canva presentation | Blocked by missing credentials or external access | `https://canva.link/5mzqsf0vyns8a1z` returned inaccessible/internal error; no slide contents inferred. Need exported PDF or screenshots. |
| Official problem statement | Blocked by missing credentials or external access | No official PDF is present in this workspace; `docs/LIMITATIONS.md` also records this. Need the source PDF. |
| Handoff contract/engineering plan | Working and verified | Read local files under `handoff/`. |

## Promises vs. implementation

| Promise | Implementation observed | Status |
|---|---|---|
| Upload/profile CSV | Real multipart upload and analysis routes; browser live sample returned 1,001 rows and 14 declared columns. | Working and verified |
| XLSX ingestion and worksheet selection | Backend adapter/routes and frontend selection flow exist; this audit did not run an XLSX lifecycle. | Implemented but not fully verified |
| JSON dataset ingestion | Not advertised as a supported upload format in the current backend README/API. JSON is used for reports/exports. | Not implemented |
| Missing, placeholder, invalid-format, category, duplicate, anomaly, relationship and row-width findings | Deterministic detectors returned evidence and row references on the sample. Fifteen planted error cases matched the expected detector and row. | Working and verified |
| Near-duplicate detection | The sample verifies exact duplicates only. No near-duplicate detector was demonstrated. | Not implemented |
| Diagnosis and typed suggestions | Actual issue records and typed proposals are returned; unsafe/ambiguous cases remain flagged/refused. | Working and verified |
| Simulation, impact and Safety Gate | Proposal simulation and gate data are returned; approval/rejection/apply were exercised through HTTP. | Working and verified |
| Human review, atomic apply, history, verification/undo | Backend routes exist and suite covers them; this run approved one proposal, rejected one, applied two operations, fetched history and verified replay. | Working and verified |
| Before/after metrics | Backend calculates quality dimensions and issue deltas from the run; no arbitrary score is used in the live overview. | Working and verified |
| Trust Passport and export bundle | Actual run exports returned CSV and valid JSON report/log/recipe/passport. | Working and verified |
| Cross-file/database referential integrity | Only explicitly supported same-row and within-table rules are documented; no cross-dataset graph is inferred. | Partially working |
| Live Groq/Supabase | Health advertises LLM configured/available; no provider-side authenticated check or live Supabase lifecycle was part of this audit. Supabase live auth is documented as unverified. | Implemented but not fully verified |

## Walkthrough issue found and corrected

Before this change, the cinematic sample showed hard-coded row/issue counts, an 80% quality score, a fake run ID/hash, a “verified” badge, and a local-only duplicate approval toggle. The toggle did not call the backend. The walkthrough now labels the animated sample as an illustrative storyboard, removes fabricated live metrics and proof claims, and provides **Run Live Sample Analysis**, which uploads the checked-in synthetic CSV using the configured `VITE_API_BASE_URL`, calls upload + analysis, stores the returned run, and opens its real overview. The actual approval/apply/verify/history/export controls live in the workspace.

The official presentation could not be compared, so presentation parity remains blocked pending source material.
