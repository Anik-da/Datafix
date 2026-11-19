# DataFix — Frontend/Backend API Contract

**Status:** Binding implementation contract for v1  
**Owners:** Akash (frontend/integration) and Teammate 3 (backend)  
**Architecture:** React + TypeScript frontend; one modular FastAPI backend  
**Contract rule:** The backend's generated OpenAPI schema is the runtime source of truth. This document is the agreed target contract; update it and regenerate frontend types together when a change is approved.

---

## 1. Shared rules

1. All product endpoints use the `/api/v1` prefix. Keep the existing `GET /health` endpoint outside that prefix.
2. Keep `POST /api/v1/datasets/profile` for compatibility with the current starter. The primary product workflow uses the run endpoints in this document.
3. CSV is the only required ingestion format in the first vertical slice. Add XLSX only after CSV ingestion, detection and tests pass.
4. All request and response payloads must be validated with Pydantic models.
5. Generate TypeScript API types from FastAPI OpenAPI (`openapi-typescript`). Do not hand-maintain duplicate API types.
6. Do not return fabricated counts, confidence, scores, hashes or verification results. Unknown/unsupported values must be `null`, omitted, or represented as an explicit unavailable state according to the schema.
7. The original uploaded file is immutable. Repairs are proposals first; the backend simulates each proposal on a copy.
8. The LLM is optional. It may select among deterministic hypothesis IDs and write concise explanations. It must never generate executable code or directly write cell values.
9. A failed invariant means the proposal is refused. Refused proposals cannot be overridden in v1.
10. Every error response uses the common error envelope in Section 8.

## 2. Common types

### 2.1 Evidence

```json
{
  "kind": "count|example|rule|statistic",
  "label": "Human-readable evidence label",
  "detail": "Evidence description",
  "metrics": {"support_count": 42},
  "examples": ["example value"]
}
```

`metrics` may contain only measured numeric values. `examples` must be limited and must not expose unnecessary personal data.

### 2.2 Issue

```json
{
  "id": "issue_id",
  "category": "missing|duplicate|invalid_format|inconsistent|anomaly|relationship",
  "title": "Human-readable title",
  "column": "city",
  "description": "Evidence-backed description",
  "affected_rows": 12,
  "affected_cells": 12,
  "affected_row_ids": ["row_2", "row_9"],
  "evidence": [],
  "disposition": "repair_proposed|flagged_only|preserved_as_valid",
  "diagnosis": [{"id":"hypothesis_id","statement":"Possible cause","evidence_labels":[]}]
}
```

`column` may be null for multi-column issues. `disposition` indicates whether a repair proposal exists or the item is intentionally only flagged/preserved.

### 2.3 Confidence

```json
{
  "value": null,
  "method": "rule_support|backtest|similarity|losslessness",
  "components": [
    {"label": "Round-trip losslessness", "value": 1.0, "note": "No information lost"}
  ],
  "n_support": 0,
  "lower_bound": null,
  "caveat": "A proxy based on observed values, not a guarantee."
}
```

- `value` is a number in `[0, 1]` or `null` when there is insufficient evidence.
- Never return an LLM's self-reported confidence.
- A confidence value must have a documented method and measured supporting evidence.
- If the method is not implemented, return `null`; the frontend will display evidence without a percentage.

### 2.4 Invariant result

```json
{
  "name": "schema_preserved",
  "status": "pass|fail|skipped",
  "detail": "Column names and types remain unchanged",
  "observed": null,
  "threshold": null,
  "unit": null
}
```

`observed`, `threshold` and `unit` may be null when not applicable or unavailable. Any `fail` must result in a refused proposal.

### 2.5 Simulation report

```json
{
  "cells_changed": 0,
  "rows_affected": 0,
  "rows_removed": 0,
  "previously_valid_cells_changed": 0,
  "aggregate_drift": {},
  "new_issues_introduced": 0,
  "sample_diff": [
    {"row_id": "row_1", "column": "city", "before": "BLR", "after": "Bengaluru", "was_valid": false}
  ],
  "invariants": []
}
```

`sample_diff` is a bounded sample, not necessarily the complete diff. The frontend must label the coverage honestly. `was_valid` is calculated by the backend from the original detector/rule set, not by an LLM.

### 2.6 Gate decision

```json
{
  "decision": "auto_apply|needs_approval|refused",
  "reasons": ["The date conversion is unambiguous and lossless"],
  "refusal_kind": "invariant_failed|insufficient_evidence|null"
}
```

`refusal_kind` is required for refused proposals. For non-refused proposals it is null. `kept_as_valid` is an issue disposition, not a repair proposal decision.

---

## 3. `GET /health`

Keep the existing health endpoint.

Required behaviour:
- Return HTTP 200 when the API is available.
- Include backend/API status and whether optional LLM explanations are enabled/available.
- LLM unavailability must not mark the core API unhealthy.
- Do not expose secrets, environment values or internal stack traces.

The exact health response can retain the current implementation, but any frontend-consumed fields must be documented in OpenAPI.

## 4. `POST /api/v1/runs`

Create a run from an uploaded CSV.

**Request:** `multipart/form-data`, field name `file`.

**Validation:**
- CSV only for v1.
- Validate extension and file content; do not trust extension alone.
- Enforce one central configured upload-size limit (initial target: 5 MB).
- Enforce row and column limits (initial target: 50,000 rows and 60 columns; reduce if measured memory requires it).
- Detect/handle supported encodings; return a clear error for unsupported input.
- Reject empty files, malformed CSV and duplicate headers with actionable messages.
- Preserve original bytes immutably and compute SHA-256.
- Do not derive filesystem paths from user-supplied filenames.

**Response:** HTTP 201.

```json
{
  "run": {
    "id": "run_id",
    "filename": "orders_dirty.csv",
    "file_sha256": "sha256_hex",
    "file_size_bytes": 12345,
    "row_count": 1000,
    "column_count": 14,
    "status": "uploaded",
    "created_at": "2026-11-19T10:00:00Z",
    "engine_version": "0.1.0"
  }
}
```

## 5. `POST /api/v1/runs/{run_id}/analyze`

Run profiling, detection, diagnosis, typed proposal generation, simulation, invariant checks and gate decisions.

**Response:**

```json
{
  "run": {
    "id": "run_id",
    "filename": "orders_dirty.csv",
    "row_count": 1000,
    "column_count": 14,
    "file_sha256": "sha256_hex",
    "status": "analyzed",
    "engine_version": "0.1.0"
  },
  "profile": {
    "row_count": 1000,
    "column_count": 14,
    "columns": [
      {
        "name": "city",
        "inferred_type": "category",
        "null_count": 0,
        "null_pct": 0.0,
        "distinct_count": 8,
        "is_key_candidate": false
      }
    ]
  },
  "issues": [],
  "proposals": [],
  "summary": {
    "issue_count": 0,
    "proposal_count": 0,
    "auto_apply_count": 0,
    "needs_approval_count": 0,
    "refused_count": 0
  }
}
```

### 5.1 Proposal shape

Each item in `proposals`:

```json
{
  "id": "proposal_id",
  "issue_ids": ["issue_id"],
  "op": "normalize_date|trim_text|map_values|set_null|impute|drop_exact_dupes|merge_near_dupes|cast_numeric|derive_from_rule",
  "column": "city",
  "risk_class": "format_only|value_substitution|imputation|destructive",
  "source": "rule|stat|llm_assisted",
  "title": "Standardize city values",
  "explanation": "Short evidence-backed explanation",
  "params": {},
  "evidence": [],
  "confidence": {},
  "simulation": {},
  "gate": {}
}
```

Rules:
- `op` must be an allow-listed typed operation.
- `params` must be validated by an operation-specific Pydantic schema/discriminated union.
- No executable code, SQL or arbitrary expression is accepted in `params`.
- `source=llm_assisted` only means the LLM selected among system-generated hypotheses or supplied a constrained explanation. It does not mean the LLM created the repair value.
- Proposal simulation and gate evaluation are performed on copies. No data is changed by the analyze endpoint. Unsupported operation kinds are explicitly refused.

## 6. `POST /api/v1/runs/{run_id}/decisions`

Approve or reject proposals that are in `needs_approval` state.

**Request:**

```json
{
  "decisions": [
    {"proposal_id": "proposal_id", "action": "approve|reject"}
  ]
}
```

Rules:
- Only `needs_approval` proposals can be approved/rejected.
- Refused proposals cannot be overridden in v1.
- Repeating the same decision is idempotent.
- Return the updated decision state for each proposal.
- Invalid state transitions return HTTP 409 with the common error envelope.

## 7. `POST /api/v1/runs/{run_id}/apply`

Apply all `auto_apply` and user-approved proposals in deterministic order. Pending and refused proposals are not applied.

**Safety requirement:** stage the complete selected plan against a copy, apply in deterministic order, then re-check combined invariants. If any operation causes an invariant failure, abort the entire batch without mutating the saved run. Do not partially apply silently.

**Response:**

```json
{
  "status": "applied|aborted",
  "applied_operations": [
    {
      "op_id": "op_id",
      "proposal_id": "proposal_id",
      "op": "normalize_date",
      "column": "order_date",
      "cells_changed": 10,
      "rows_removed": 0,
      "decided_by": "auto|user",
      "applied_at": "2026-11-19T10:00:00Z"
    }
  ],
  "skipped": [
    {"proposal_id": "proposal_id", "reason": "Pending approval"}
  ],
  "blocking_invariants": []
}
```

If `status=aborted`, no operation in that batch is persisted as applied. Include the blocking proposal/invariant information.

## 8. `POST /api/v1/runs/{run_id}/verify`

Re-detect on the applied output, replay operations from the immutable original, compare hashes and measure collateral changes.

**Response:**

```json
{
  "replay": {
    "operations": 2,
    "input_hash": "sha256_hex",
    "replay_hash": "sha256_hex",
    "match": true
  },
  "issues": {
    "before": 10,
    "after": 3,
    "resolved": 7,
    "introduced": 0,
    "by_category": []
  },
  "valid_cells_damaged": 0,
  "quality_score": {
    "before": null,
    "after": null,
    "method": "Not calculated; return dimension metrics until a documented composite formula exists"
  },
  "remaining": []
}
```

Do not invent a 0–100 quality score. Prefer dimension metrics (completeness, validity, uniqueness, consistency) with disclosed formulas. If a composite score is later introduced, document its exact formula and caveats.

## 9. `GET /api/v1/runs/{run_id}/operations`

Return ordered applied operations:

```json
[
  {
    "seq": 1,
    "op_id": "op_id",
    "proposal_id": "proposal_id",
    "op": "normalize_date",
    "column": "order_date",
    "cells_changed": 10,
    "decided_by": "auto|user",
    "applied_at": "2026-11-19T10:00:00Z",
    "confidence_at_decision": null
  }
]
```

This endpoint lists applied operations only. Refused proposals are not operations; the frontend may display them in a separate Declined/Refused view from the analysis proposal data.

## 10. `GET /api/v1/runs/{run_id}/export/{artifact}`

Supported artifact names:

| Artifact | Required output |
|---|---|
| `cleaned` | Cleaned CSV |
| `report` | Human-readable HTML and/or JSON quality report; document exact returned format |
| `log` | Cell-level modification log in CSV or JSON; document exact returned format |
| `recipe` | Ordered JSON operations and original input hash |

Return a real downloadable attachment with correct `Content-Type` and `Content-Disposition` filename. Do not display a download action until the artifact is available.

Current export formats are CSV for `cleaned` and JSON for `report`, `log`, and `recipe`.

## 9.1 `POST /api/v1/runs/{run_id}/undo/{op_id}`

Undo is limited to the most recent active operation so that later cell changes
cannot be silently overwritten. The response reports `undone` or `refused`.
Operation history includes an `active` flag; inactive entries remain in the
audit trail but are excluded from replay and recipe exports.

## 11. Optional compatibility/profile endpoint

Keep `POST /api/v1/datasets/profile` working for the current starter UI during the migration. It is a compatibility endpoint only. New product workflows should use `POST /runs` followed by `/analyze`.

## 12. Common error envelope

All errors:

```json
{
  "code": "stable_error_code",
  "message": "Human-readable message",
  "details": {},
  "request_id": "request_id"
}
```

Use these HTTP statuses:

| Status | Meaning |
|---|---|
| 400 | Malformed request/input |
| 404 | Unknown run or resource |
| 409 | Invalid state transition or atomic apply aborted |
| 413 | Upload too large |
| 415 | Unsupported file type |
| 422 | Invalid schema or unprocessable data |
| 500 | Unexpected server error |

Never return stack traces, secrets or environment configuration to the browser.

## 13. Frontend integration requirements

- Frontend base URL comes from `VITE_API_BASE_URL`.
- Local `.env.example` may point to `http://127.0.0.1:8000`; production Vercel config points to the Render URL.
- CORS must allow the actual Vercel origin(s), not `*` in production.
- Generate frontend API types from the backend OpenAPI document after each approved schema change.
- Fixture mode is visibly labelled and never silently activates after a real API failure.
- UI never claims a proposal was applied until the apply response confirms it.
- UI never claims verification succeeded until the verify response confirms it.
- UI does not show percentages, progress stages, counts or hashes that the backend did not return.

## 14. Approval and change control

- Akash approves shared contract changes.
- Teammate 3 implements backend schemas and endpoints.
- Any contract change must update this file, Pydantic schemas, OpenAPI, generated TypeScript types and relevant fixtures in the same integration change.
- Backend and frontend must agree on response fixtures before the corresponding UI flow is considered integrated.

---

## 15. First integration checkpoint

The first working vertical slice is:

1. Frontend uploads CSV to `POST /api/v1/runs`.
2. Backend validates, preserves and hashes the original.
3. Frontend calls `POST /api/v1/runs/{run_id}/analyze`.
4. Backend returns real profile, issues, deterministic diagnosis, typed proposals and safety decisions.
5. Frontend displays the actual profile and issues without development fixtures.

Do not begin the full Repair Studio integration until this checkpoint passes.

## 16. Advanced trust and review extensions (additive)

The OpenAPI schema adds `Issue.pattern`, proposal `status`, `version`, and
`decision_history`, and `Simulation.impact` with distinct `direct_metrics` and
`indirect_metrics`. RippleGuard measures simulated values against a temporary
copy and reports explicit deterministic dependency checks only. It does not use
correlations or produce an impact score.

| Method and path | Purpose |
|---|---|
| `POST /api/v1/runs/{run_id}/proposals/{proposal_id}/edit` | Submit a typed cell value edit; validates row reference, current original value, observed type/range/category constraints, then re-simulates and requires reapproval. |
| `POST /api/v1/runs/{run_id}/bulk-decisions` | Explicit proposal IDs plus `approve` or `reject`; validates the complete batch before persistence. Refused proposals return 409. |
| `GET /api/v1/runs/{run_id}/uncertainty?offset=0&limit=100` | Column metrics and bounded record page; maximum `limit` is 500. Record correctness confidence remains null. |
| `GET /api/v1/runs/{run_id}/export/passport` | Download reproducible Trust Passport JSON from uploaded bytes, current CSV bytes, analysis and operation history. |

Manual edit request example:

```json
{
  "row_id": "row_5",
  "column": "city",
  "original_value": "BENGALURU ",
  "edited_value": "Bengaluru",
  "reason": "Use the existing canonical category"
}
```

Editing does not update the working dataset. The response contains a new
proposal version, recalculated impact and gate. An eligible edit becomes
`edited_pending_reapproval`; approve it through the existing `/decisions`
endpoint before `/apply`. A refused edit cannot be overridden. `decision_history`
records edits and transitions; operation history records applied operation IDs.

Fingerprint IDs use normalized issue metadata and contain no raw cell values.
The `pattern` response includes the inferred column type, normalized error type,
value-shape/format family, measured support frequency, detector-rule identifiers
and `match_method: exact_signature`; no fuzzy similarity percentage is claimed.
They do not transfer approvals between runs. The passport includes a SHA-256
digest of canonical exported JSON with the `passport_sha256` field omitted; use
sorted keys, UTF-8, no ASCII escaping and compact `,`/`:` separators to verify.
It is not cryptographically signed.
`verified_by_checks` means replay matched and no implemented detector currently
flags the record; it is not a universal correctness claim.

### 16.1 Persistent exports and prior proposal revisions

Each successful export request records the exact bytes by SHA-256 in the active
storage adapter. Supabase stores export objects under the private
`runs/{run_id}/artifacts/{name}-{sha256}` path and records content type, size,
hash, and object path in `datafix_artifacts`. Repeating an identical export is
idempotent; a changed export creates a distinct content-addressed object.

The Trust Passport is generated from the run's saved analysis, proposal and
decision history, active and undone operations, and a fresh replay verification.
It includes a full decision trace by proposal and SHA-256 values for the exact
cleaned CSV, report, modification log, and recipe export bytes. The passport's
own canonical payload digest is `passport_sha256`; its hash is excluded from
`exported_artifact_sha256` to avoid a circular self-hash. Completed verification
responses are append-only in local storage and `datafix_verifications` in
Supabase.

When a proposal is manually edited, the edit event contains `prior_proposal`, a
snapshot of the full previous typed proposal, as well as the old and edited
values. The new proposal version is re-simulated and requires fresh approval.

## 17. Structural CSV rows and advanced impact fields

The upload response may include `warnings` when recoverable row widths differ
from the declared header. Parseable rows are retained: short rows are padded
with blank/null values, while overflow values remain in internal structural
metadata and appear in a `row_structure_mismatch` issue with physical line,
stable row reference, expected/actual/missing/extra counts and evidence. The
untouched source bytes and source SHA-256 are preserved. Overflow values are
not silently dropped; a typed manual-edit proposal requires approval to remove
an unmappable value. Cleaned exports retain any still-unresolved overflow in
explicit `__unexpected_extra_N` columns. The UI should show upload warnings,
structural evidence and the proposal simulation before review.

Every proposal simulation includes `impact.remaining_issue_ids` and a
deterministic `impact.risk_level` (`low`, `moderate`, `high`, or `unknown`) in
addition to direct/indirect measurements, invariants and resolved/introduced
issue IDs. The Safety Gate remains authoritative.

The Trust Passport includes `passport_id`, `original_column_schema`, and safe
per-proposal summaries with redacted values, proposal version, operation,
simulation, gate and status. Generated TypeScript types in
`frontend/src/api/generated.ts` are synchronized from `docs/openapi.json`.
