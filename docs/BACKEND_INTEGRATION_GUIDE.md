# DataFix backend integration guide

This guide describes the current API contract for frontend integration. The
generated OpenAPI document is the source of truth:
[`openapi.json`](openapi.json). Generated TypeScript types are at
[`frontend/src/api/generated.ts`](../frontend/src/api/generated.ts); do not
hand-edit that generated file.

## Local development

Run the backend from `backend/`:

```powershell
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Configure the frontend API base URL as `http://127.0.0.1:8000` (the agreed
frontend variable is `VITE_API_BASE_URL`). CORS permits `http://localhost:5173`
and `http://127.0.0.1:5173` by default. Set `DATAFIX_CORS_ORIGINS` to the exact
development or production origins when deploying. The health response reports
optional LLM availability; the deterministic backend works with `LLM_ENABLED=false`.

## Upload and analyze

1. Send `POST /api/v1/runs` as `multipart/form-data` with one field named `file`
   containing a `.csv` file. The current default upload limit is 5 MiB. The
   endpoint validates the content and returns HTTP 201 with `run.id`, original
   SHA-256, file size, row/column counts and `status: "uploaded"`.
2. Send `POST /api/v1/runs/{run_id}/analyze` with no request body. It returns a
   measured profile, issues with evidence and affected row IDs, typed proposals,
   proposal simulations and gate decisions, and counts by gate decision.
3. Show the proposal's `gate.decision` and evidence. A `null` confidence is
   intentional when no calibrated confidence method is available. The analyze
   endpoint does not change the uploaded dataset.

Both responses are described in OpenAPI. Use the generated `paths` types for
request and response payloads. The uploaded bytes remain immutable; operations
change only the separate working dataset.

## Decisions and apply

Only proposals whose gate is `needs_approval` accept a decision. Send one or more
decisions in the OpenAPI `DecisionsRequest` format:

```json
{
  "decisions": [
    {"proposal_id": "proposal-id-from-analysis", "action": "approve"}
  ]
}
```

`action` is `approve` or `reject`. Repeating the same decision is idempotent;
changing a saved decision returns HTTP 409. Proposals gated `refused` cannot be
overridden and are never applied.

Send `POST /api/v1/runs/{run_id}/apply` with no body to stage all `auto_apply`
and user-approved proposals. Pending, rejected and refused proposals are
returned in `skipped`. The server checks the complete batch before committing;
an invariant failure returns HTTP 200 with `status: "aborted"` and no mutation.
A persistence failure returns the common HTTP 500 error envelope and also
leaves the batch unapplied. A successful response lists each applied operation
and its counts. Proposals made redundant by an earlier operation can be skipped
with `No changes remained applicable after earlier operations.`

## History, verification, undo and downloads

- `GET /api/v1/runs/{run_id}/operations` returns the ordered operation audit
  history, including an `active` flag for operations later undone.
- `POST /api/v1/runs/{run_id}/verify` replays active operations from the
  immutable original, compares the replay with the saved working dataset, and
  returns issue counts, remaining issues and quality dimensions. Treat
  `replay.match` as the confirmation that the cleaned result is reproducible.
- `POST /api/v1/runs/{run_id}/undo/{op_id}` can undo only the latest active
  operation. Check its `status`; a refused undo does not change data.
- `GET /api/v1/runs/{run_id}/export/{artifact}` downloads `cleaned` as CSV and
  `report`, `log`, `recipe`, or `passport` as JSON. The response includes
  `Content-Disposition: attachment`. Parse JSON exports as JSON; do not assume
  they are all the same shape. The cleaned CSV escapes spreadsheet formula
  prefixes.

Only show an applied or verified state after the corresponding response
confirms it. An analysis proposal is not an applied change.

## Errors and request IDs

Errors use this envelope:

```json
{
  "code": "stable_error_code",
  "message": "Human-readable message",
  "details": {},
  "request_id": "request-id"
}
```

Common statuses are 400 for malformed input, 404 for an unknown run/resource,
409 for invalid state transitions or refused overrides, 413 for oversized
uploads, 415 for unsupported file type, 422 for invalid/unprocessable input,
and 500 for unexpected server errors. Preserve `request_id` when surfacing a
support report, but do not display internal environment configuration.

## Regenerate API types

Run these commands from `backend/` after an approved schema change:

```powershell
python generate_openapi.py
npx --yes openapi-typescript ../docs/openapi.json --output ../frontend/src/api/generated.ts
```

The current frontend is a React/TypeScript API client. It has its own
`frontend/package.json` and uses the generated API types. It does not need a
Supabase SDK for this workflow; if a future client uses Supabase directly, use
only the publishable key in browser code. Keep any Supabase secret/service-role
key on the backend.

## Endpoint reference and response nullability

| Method and path | Purpose | Success |
|---|---|---|
| `GET /health` | API, optional LLM state and configured input limits | 200 |
| `POST /api/v1/runs` | Multipart upload with `file` | 201 |
| `POST /api/v1/runs/{run_id}/analyze` | Profile, issues, typed proposals, simulations and gates | 200 |
| `POST /api/v1/runs/{run_id}/decisions` | Approve/reject `needs_approval` proposals | 200 |
| `POST /api/v1/runs/{run_id}/proposals/{proposal_id}/edit` | Edit one typed proposal value and rerun simulation/gate | 200 |
| `POST /api/v1/runs/{run_id}/bulk-decisions` | Validate and record explicit eligible proposal IDs | 200 |
| `GET /api/v1/runs/{run_id}/uncertainty` | Bounded column/record uncertainty analysis (`limit` 1–500) | 200 |
| `POST /api/v1/runs/{run_id}/apply` | Atomically stage and persist eligible proposals | 200; inspect `status` for `applied`/`aborted` |
| `GET /api/v1/runs/{run_id}/operations` | Ordered operation history | 200 |
| `POST /api/v1/runs/{run_id}/verify` | Re-detection, damage metric and replay hash | 200 |
| `GET /api/v1/runs/{run_id}/export/{artifact}` | Download `cleaned`, `report`, `log`, `recipe` or `passport` | 200 attachment |
| `POST /api/v1/datasets/profile` | Legacy compatibility profile; multipart `file` | 200 |
| `POST /api/v1/runs/{run_id}/undo/{op_id}` | Extension: undo latest active operation only | 200 with `undone`/`refused` |

The exact required fields and data types are generated from the canonical
Pydantic models in OpenAPI. A `null` confidence value means no calibrated
confidence estimate is available. `ColumnProfile.minimum`/`maximum` are null
when the column has no measured numeric/date bounds. `Issue.column` is null for
row-wide rules. `Gate.refusal_kind` is null when the proposal was not refused.
`Invariant.observed`, `threshold` and `unit` can be null when not meaningful.
`DecisionState.decided_at` and operation timestamps are always present.
No `null` or omitted value should be replaced by a frontend-invented metric.

## Gate lane and lifecycle display

- `auto_apply`: show the measured simulation and passed invariants; this is still
  applied only by the explicit apply request.
- `needs_approval`: allow approve/reject, then show the recorded decision.
- `refused`: display the refusal reason and failed invariant/evidence. Do not
  show override controls.
- Treat an apply `status: aborted` as no successful operation; keep the previous
  dataset state and display `blocking_invariants`.

## Render and frontend configuration

The Render settings are prepared in root `render.yaml` and described in
[`backend/RENDER.md`](../backend/RENDER.md). Configure `DATAFIX_CORS_ORIGINS` to
the exact HTTPS Vercel origin (no path or trailing slash). The frontend should
set `VITE_API_BASE_URL` to the deployed API origin, for example
`https://<render-service>.onrender.com`; local development uses
`http://127.0.0.1:8000`. Render, Vercel and Supabase have not been live-tested.
For Supabase, apply the latest `backend/docs/supabase_schema.sql` before enabling
the adapter; it defines the transactional review RPCs used for bulk decisions
and decision-history updates, artifact metadata, and persisted verification
records. The configured key authenticated and the private bucket was created and
verified, but live run persistence is blocked until the SQL is applied: the
project currently reports `PGRST205` for `public.datafix_runs`. Local SQLite was
used for the completed live HTTP acceptance run; do not treat bucket access as
proof of hosted lifecycle persistence.
Groq was live-tested locally with `qwen/qwen3.8-27b`; the account model list
and a constrained DataFix analysis request succeeded. The Groq key remains in
the ignored backend `.env` and must be configured separately for deployment.

## Windows local setup

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` or check `http://127.0.0.1:8000/health`.
Start the independently owned frontend in its own terminal and set
`VITE_API_BASE_URL=http://127.0.0.1:8000`. Do not silently switch to local
fixtures after a live API error.

## Advanced trust and review features

Each proposal's simulation now contains `impact`, with directly affected rows
and cells, direct before/after metrics, separately measured indirect metrics,
supported dependency checks, resolved/introduced issue signatures, invariants,
risk explanations and measurement limitations. No correlation based
dependencies or impact scores are generated.

Manual edit request:

```json
{
  "row_id": "row_5",
  "column": "city",
  "original_value": "BENGALURU ",
  "edited_value": "Bengaluru",
  "reason": "Use the existing canonical category"
}
```

Send this to `POST /api/v1/runs/{run_id}/proposals/{proposal_id}/edit`. The
server validates the current old value, affected row/column, type, observed
numeric range or allowed category, increments the proposal version, and reruns
the same simulation and Safety Gate. The edit does not modify working data.
An eligible edit becomes `edited_pending_reapproval` and needs approval through
the existing `/decisions` endpoint before `/apply`. Refused proposals cannot be
edited or overridden. Audit entries retain the original suggestion, edit,
reason, state transition, timestamp and version; application history records
the operation ID and actual values.

Bulk review accepts explicit unique IDs and `approve` or `reject`. Every ID is
validated before any decision is persisted. Any refused or ineligible ID
returns 409 and the batch is unchanged.

Issue fingerprints contain normalized issue metadata only, not cell values.
They do not transfer prior approvals or repair mappings across runs. The
uncertainty endpoint returns all column summaries and up to 500 stable-row
summaries per page. Whole-record correctness confidence is `null`; rule coverage
is reported separately. `verified_by_checks` means replay succeeded and no
implemented detector flags the row, not that the data is universally correct.

The downloadable `passport` JSON hashes original upload bytes, cleaned CSV
bytes and a canonical passport representation. Its timestamp is based on the
run/operation history for reproducibility. To verify `passport_sha256`, remove
that field, serialize the remaining JSON with sorted keys, UTF-8, no ASCII
escaping, and separators `,` and `:`, then SHA-256 the bytes. This digest is not
a cryptographic signature.

Example excerpts (actual IDs, counts and metrics are calculated from the run):

```json
{
  "impact": {
    "proposal_id": "prp_example",
    "direct_row_ids": ["row_5"],
    "direct_cells": 1,
    "direct_columns": ["city"],
    "direct_metrics": [
      {"metric":"distinct_count","column":"city","before":6,"after":5,"change":-1,"relationship":"direct","support":["measured on original and temporary simulated data"]}
    ],
    "indirect_metrics": [],
    "affected_dependency_checks": [],
    "potentially_resolved_issue_ids": ["iss_example"],
    "introduced_issue_ids": [],
    "invariants": [],
    "risk_explanations": ["Proposal risk class: value_substitution."],
    "limitations": ["Statistical correlations are not treated as dependencies."]
  }
}
```

```json
{
  "run_id":"run_example","offset":0,"limit":2,"total_records":1000,
  "columns":[{"column":"city","total_records":1000,"missing_count":0,"missing_rate":0.0,"invalid_count":0,"invalid_rate":0.0,"inconsistent_count":1,"inconsistent_rate":0.001,"anomaly_count":0,"pending_proposals":1,"refused_proposals":0,"unresolved_issues":1,"evidence_available":true,"confidence_available":false,"rule_coverage":["inconsistent"]}],
  "records":[{"row_id":"row_5","state":"pending_human_review","issue_density":1,"columns":["city"],"reasons":["Category variants"],"evidence_references":["iss_example"],"confidence":null}],
  "calculation_notes":["Rates are measured counts divided by row count."]
}
```

The passport also includes original/cleaned hashes, per-proposal decision traces,
operation history, unresolved issues, quality dimensions, replay result, and
hashes for the exact cleaned CSV, report, log, and recipe bytes. Its
`passport_sha256` hashes the canonical passport payload. This is an audit record,
not a signature or universal correctness claim. See the OpenAPI schema for the
complete typed response and `docs/feature_examples.json` for actual fixture-run
responses.
