# DataFix — Locked Phase 2 Execution Plan

**Decision owner:** Akash / technical architecture review  
**Purpose:** Binding execution instructions for the two-person human team, Antigravity and supporting design/review tools.  
**Design authority:** `docs/FRONTEND_DESIGN_SPEC.md`  
**Competitive direction:** Repair Preview & Safety Gate  
**Rule:** Execute the assigned work. Do not independently expand scope or change the architecture. Raise blockers with evidence.

---

## 1. Team ownership

### Akash — frontend owner and technical lead

- Own the React + TypeScript frontend and all frontend UX decisions.
- Use Antigravity as the implementation agent; review its changes and test results.
- Own frontend/backend integration and approve shared API contract changes.
- Coordinate the optional Groq integration, Vercel configuration, final deployment and live demo.
- Own GitHub coordination, branch integration and release readiness.
- Do not independently rewrite backend business logic.

### Teammate 3 — sole backend and data-engine owner

- Own the FastAPI backend, API schemas, ingestion, profiling, detection, diagnosis, repair proposals, simulation, invariants, gate decisions, apply, verification and exports.
- Own the canonical synthetic demonstration dataset, clean ground truth, injected-error manifest, benchmark script and backend test suite.
- Coordinate API contract changes with Akash before implementation.
- Do not modify frontend source code or frontend architecture.

### Supporting tools (not additional team members)

- **Antigravity:** implements frontend tasks under Akash's direction. It does not independently change product scope or API semantics.
- **Claude:** provides design and product review documents. It does not own implementation or make binding architecture decisions.
- **ChatGPT:** provides architecture decisions, task instructions, prompt preparation, code/contract reviews and integration guidance.

There are exactly two human developers. Do not assign work to a third teammate.
---

## 2. Product and architecture decisions — locked

1. Product identity: **DataFix — a trust-first data repair engine**.
2. Signature feature: **Repair Preview & Safety Gate**.
3. Pipeline: **Detect → Diagnose → Propose → Simulate → Gate → Apply → Verify**.
4. Frontend: React + TypeScript + Tailwind CSS.
5. Backend: one modular FastAPI monolith.
6. Data engine: deterministic Python/Pandas logic.
7. Database/storage: local adapter for local development; add Supabase adapter for hosted persistence after local vertical slice passes.
8. Frontend hosting target: Vercel. Backend hosting target: Render. LLM provider: personal GroqCloud free tier, optional.
9. Initial required ingestion format: CSV. XLSX is the next format only after CSV workflow and test suite pass. Do not add JSON, Parquet, SQL connectors or multi-file joins in this phase.
10. Initial hosted safety limits: maximum 5 MB CSV, 50,000 rows, 60 columns. Keep limits in one backend config and return them from policy/health metadata. Reduce if measured memory use requires it.
11. No user accounts/authentication, no autonomous agent loop, no chat-with-data, no microservices, no Redis/Celery, no paid API dependency.
12. The LLM is optional and constrained to choosing among deterministic hypotheses and writing short explanations. It must never generate executable code or directly write cell values. The core flow must work with `LLM_ENABLED=false`.
13. Never invent confidence. If the backend cannot calculate a defensible estimate, return `null` and show evidence without a percentage.
14. A refused repair is a successful safety outcome, not a system error. Indigo/violet is used for refusal; red is reserved for actual system/network/parse failures.

---

## 3. Repair policy — locked for v1

| Case | v1 decision | Notes |
|---|---|---|
| Lossless date/format normalization | Auto-apply only when unambiguous and all invariants pass | Ambiguous dates must be refused or held; never guess locale. |
| Trim whitespace / safe case normalization | Auto-apply only when semantics are unchanged and checks pass | Record every changed cell. |
| Placeholder-to-null (`N/A`, `-`, configured tokens) | Auto-apply only when token is explicitly configured/detected with strong evidence | Preserve literal text otherwise. |
| Exact duplicate rows | Needs approval | Row removal is destructive in v1. |
| Near-duplicate records | Needs approval only if a supported matching rule exists; otherwise flag only | Never auto-merge. |
| Category standardization | Needs approval | Map only to an existing canonical value; no free-form invented values. |
| Missing-value imputation | Needs approval if evidence is sufficient; otherwise refuse/abstain | Never auto-impute in v1. Confidence/backtest can be P1. |
| Statistical outlier with no violated business rule | Flag and preserve; no repair proposal | If the UI represents it as “kept as valid”, it must be backed by actual rule checks. |
| Cross-column inconsistency with no unambiguous correction | Refuse/flag; do not guess | Example: `total != quantity × unit_price`. |
| Any failed integrity invariant | Refuse the repair | No bypass/override in v1. |

**Definition:** “Previously valid cell” means a cell that was not flagged by the detector/rule set before the proposed operation. The backend must calculate this from the original dataset, not from an LLM judgement.

**Confidence:** Evidence-based estimate only. Start with losslessness, rule support, sample support and similarity evidence. Backtested imputation confidence is P1. Show `null` if the evidence is insufficient.

**Application safety:** The apply operation must stage the full selected plan on a copy, run the operations in deterministic order and re-check invariants. If any selected operation makes the staged plan violate an invariant, abort the whole batch without mutating the saved run. Return the blocking proposal and invariant details. Do not partially apply a plan silently.

---

## 4. Canonical API contract — backend and frontend must follow this

All routes use the `/api/v1` prefix except the existing `GET /health` health endpoint. Keep the current `POST /api/v1/datasets/profile` endpoint for compatibility, but the primary product workflow uses runs below.

### 4.1 `POST /api/v1/runs`

- Content type: `multipart/form-data` with field `file`.
- v1 accepts CSV only.
- Validate extension, content, encoding, size, row/column limits and duplicate headers.
- Store the untouched original and compute SHA-256.
- Response `201`:

```json
{
  "run": {
    "id": "run_id",
    "filename": "orders_dirty.csv",
    "file_sha256": "hex",
    "file_size_bytes": 12345,
    "row_count": 1000,
    "column_count": 14,
    "status": "uploaded",
    "created_at": "ISO-8601",
    "engine_version": "0.1.0"
  }
}
```

### 4.2 `POST /api/v1/runs/{run_id}/analyze`

Runs profiling, detection, deterministic diagnosis, typed proposal generation, simulation, invariant checks and gate decisions.

Response:

```json
{
  "run": { "id": "run_id", "filename": "orders_dirty.csv", "row_count": 1000, "column_count": 14, "file_sha256": "hex", "status": "analyzed", "engine_version": "0.1.0" },
  "profile": {
    "row_count": 1000,
    "column_count": 14,
    "columns": [
      {"name":"city","inferred_type":"category","null_count":0,"null_pct":0.0,"distinct_count":8,"is_key_candidate":false}
    ]
  },
  "issues": [
    {
      "id":"issue_id",
      "category":"missing|duplicate|invalid_format|inconsistent|anomaly|relationship",
      "title":"Human-readable title",
      "column":"city",
      "description":"Evidence-backed description",
      "affected_rows":12,
      "affected_cells":12,
      "evidence":[{"kind":"count|example|rule|statistic","label":"...","detail":"...","metrics":{},"examples":[]}],
      "disposition":"repair_proposed|flagged_only|preserved_as_valid"
    }
  ],
  "proposals": [
    {
      "id":"proposal_id",
      "issue_ids":["issue_id"],
      "op":"normalize_date|trim_text|map_values|set_null|impute|drop_exact_dupes|merge_near_dupes|cast_numeric|derive_from_rule",
      "column":"city",
      "risk_class":"format_only|value_substitution|imputation|destructive",
      "source":"rule|stat|llm_assisted",
      "title":"Standardize city values",
      "explanation":"Short evidence-backed explanation",
      "params":{},
      "evidence":[{"kind":"count|example|rule|statistic","label":"...","detail":"...","metrics":{},"examples":[]}],
      "confidence":{
        "value":null,
        "method":"rule_support|backtest|similarity|losslessness",
        "components":[{"label":"...","value":0.0,"note":"..."}],
        "n_support":0,
        "lower_bound":null,
        "caveat":"..."
      },
      "simulation":{
        "cells_changed":0,
        "rows_affected":0,
        "rows_removed":0,
        "previously_valid_cells_changed":0,
        "aggregate_drift":{},
        "new_issues_introduced":0,
        "sample_diff":[{"row_id":"row_1","column":"city","before":"...","after":"...","was_valid":false}],
        "invariants":[{"name":"schema_preserved","status":"pass|fail|skipped","detail":"...","observed":null,"threshold":null,"unit":null}]
      },
      "gate":{
        "decision":"auto_apply|needs_approval|refused",
        "reasons":["..."],
        "refusal_kind":"invariant_failed|insufficient_evidence|null"
      }
    }
  ],
  "summary": {"issue_count":0,"proposal_count":0,"auto_apply_count":0,"needs_approval_count":0,"refused_count":0}
}
```

The example values are schema illustrations, not defaults. Empty/unknown values must be represented honestly. The API must not return fabricated metrics.

### 4.3 `POST /api/v1/runs/{run_id}/decisions`

Request:

```json
{"decisions":[{"proposal_id":"proposal_id","action":"approve|reject"}]}
```

Only `needs_approval` proposals may be approved/rejected. Refused proposals cannot be overridden in v1. Return the updated decision state for each proposal. Repeating the same decision must be idempotent.

### 4.4 `POST /api/v1/runs/{run_id}/apply`

Apply all `auto_apply` and user-approved proposals in deterministic order using the atomic staged-plan rule in section 3. Pending and refused proposals are not applied.

Response:

```json
{
  "status":"applied|aborted",
  "applied_operations":[{"op_id":"op_id","proposal_id":"proposal_id","op":"normalize_date","column":"order_date","cells_changed":10,"rows_removed":0,"decided_by":"auto|user","applied_at":"ISO-8601"}],
  "skipped":[{"proposal_id":"proposal_id","reason":"..."}],
  "blocking_invariants":[]
}
```

### 4.5 `POST /api/v1/runs/{run_id}/verify`

Response:

```json
{
  "replay":{"operations":2,"input_hash":"hex","replay_hash":"hex","match":true},
  "issues":{"before":10,"after":3,"resolved":7,"introduced":0,"by_category":[]},
  "valid_cells_damaged":0,
  "quality_score":{"before":null,"after":null,"method":"Do not provide a composite score until its formula is documented; dimension metrics may be returned instead."},
  "remaining":[]
}
```

Prefer dimension metrics over an arbitrary single 0–100 score. If a composite is implemented, document the formula and its limitations in the response and README.

### 4.6 `GET /api/v1/runs/{run_id}/operations`

Return ordered applied operations, including operation id, proposal id, operation, column, cell count, actor (`auto` or `user`) and timestamp.

### 4.7 `GET /api/v1/runs/{run_id}/export/{artifact}`

Supported artifact names: `cleaned`, `report`, `log`, `recipe`.

- `cleaned`: cleaned CSV.
- `report`: human-readable HTML quality report and/or JSON report (document exact format).
- `log`: cell-level modification log CSV/JSON.
- `recipe`: ordered JSON operations and input hash.

Return a proper downloadable attachment with content type and filename.

### 4.8 Error envelope

All API errors use:

```json
{"code":"stable_error_code","message":"Human-readable message","details":{},"request_id":"id"}
```

Use appropriate HTTP status codes: 400 malformed input, 413 too large, 415 unsupported format, 404 unknown run, 409 invalid decision/state or aborted conflicting plan, 422 invalid schema/data, 500 unexpected server error. Never return stack traces to the browser.

### 4.9 Health

Keep `GET /health`. Return API availability and whether the optional LLM is enabled/available. LLM unavailable must not mean the core API is unhealthy.

---

## 5. Backend implementation order — Teammate 3

Implement in this exact order. Do not skip ahead to Groq.

1. **Contract and schemas:** Pydantic models for all request/response objects above. Update `FRONTEND_BACKEND_CONTRACT.md` and verify generated OpenAPI.
2. **CSV ingestion:** size/shape/encoding/content validation, immutable original, SHA-256, safe temporary storage behind a storage interface.
3. **Profiling:** row/column totals, inferred types, missing/null counts, distinct counts, candidate keys.
4. **Detectors:** actual nulls/placeholders, exact duplicates, invalid date/numeric/email formats, category inconsistencies, statistical/rule-based anomalies, at least two cross-column rules.
5. **Diagnosis:** deterministic hypotheses with evidence. No generic LLM-created diagnosis.
6. **Typed proposals:** allowed operation enum and validated parameters. Never accept executable Python/SQL from a model.
7. **Simulation:** run on a copy; generate diff, blast radius and invariant results.
8. **Gate:** apply the policy in section 3. Any failed invariant means refused.
9. **Decision/apply:** approve/reject, staged deterministic application, atomic abort on failed combined checks, cell-level operation log.
10. **Verify/export:** re-detection, replay hash, damage count, cleaned CSV, report, modification log and recipe.
11. **Tests:** unit tests for each detector/op/invariant/gate rule; integration test for the full run lifecycle.
12. **Only after all above:** optional Groq client behind `LLM_ENABLED`, timeout, bounded retries, cache, request cap and deterministic fallback.

---

## 6. Frontend implementation order — Antigravity under Akash

1. Read `AGENTS.md`, `docs/FRONTEND_DESIGN_SPEC.md`, `docs/FRONTEND_IMPLEMENTATION_PLAN.md` and `docs/FRONTEND_BACKEND_CONTRACT.md`.
2. Preserve the existing Phase 1 structure; do not rewrite the app.
3. Remove hardcoded `http://127.0.0.1:8000` references. Use `VITE_API_BASE_URL` with a local `.env.example`.
4. Use generated OpenAPI types as the source of truth for implemented endpoints. Keep proposed contract types separate and clearly named until backend endpoints exist.
5. Finish real Intake → upload → profile → Overview using the existing real `/api/v1/datasets/profile` endpoint while the run API is being implemented.
6. Build Repair Studio against isolated development fixtures matching section 4. The UI must show an unmistakable DEVELOPMENT / DEMO DATA banner in fixture mode.
7. Never fall back silently to fixtures after a live API failure.
8. Implement the exact three decision lanes and Guardian refusal treatment from the design spec. No action buttons on refused proposals.
9. Implement Proof, History and Export states only when backed by the API response; otherwise display locked/coming-later states, not fake success.
10. Add loading, empty, error, success and cold-start states. No fake progress percentages.
11. Run `tsc --noEmit`, `npm run build` and manual route/API tests. Report actual results and changed files.
12. Do not edit backend business logic or independently change API contract semantics.

---

## 7. Dataset, benchmark and QA — Teammate 3

Teammate 3 owns this work in addition to backend engineering. Build it alongside the detector tests, but keep the first priority on the ingestion/profiling/detection API vertical slice.

Create one canonical synthetic e-commerce orders dataset under `samples/`:

- `orders_dirty.csv` — about 1,000 rows and 12–14 columns.
- `orders_clean_truth.csv` — clean source table before error injection.
- `orders_error_manifest.json` — exact row/cell, injected value, original value and error type.
- `README.md` — generator seed, columns, injected errors and known limitations.
- `generate_dataset.py` — deterministic error-injection generator with fixed seed.
- `benchmark.py` — score true repairs against the manifest.

Include at least these examples:

1. Missing values and placeholder tokens.
2. Exact duplicate rows.
3. Mixed date formats including genuinely ambiguous examples.
4. Category/case/whitespace variants.
5. Invalid email or numeric formats.
6. One suspicious but legitimate outlier that must be preserved.
7. A cross-column inconsistency such as `total != quantity * unit_price`.
8. One date-order rule violation such as `ship_date < order_date`.
9. If feasible, a pair of similar-looking but distinct category values that a relationship rule must prevent from merging.

Use synthetic names, emails and phone numbers only. No real personal data.

The benchmark must report precision, recall, abstentions and previously-valid cells changed. Clearly label results as a synthetic benchmark; do not claim general accuracy. Use a separate tuning seed from the final demo seed.

Also prepare:
- `docs/DEMO_SCRIPT.md` — three-minute demo.
- `docs/QA_CHECKLIST.md` — reproducible manual and edge-case tests.

Do not build frontend features. Do not change frontend architecture. Dataset generation and tests are part of Teammate 3's backend/QA ownership; Akash remains responsible for frontend and project integration.
---

## 8. Git workflow — locked

- `main` must remain deployable.
- Branch naming: `feat/<owner>/<scope>` or `fix/<owner>/<scope>`.
- Keep branches short-lived; merge small PRs.
- Commit format: `feat(detect): add placeholder-null detector`, `fix(gate): refuse failed invariant`, `test(sim): cover date ambiguity`, `docs: add demo dataset manifest`.
- Do not commit `.env`, keys, `node_modules`, `.venv`, `__pycache__` or generated large data.
- Commit lockfiles and `.env.example`.
- Generate OpenAPI types after backend schema changes; do not hand-edit generated types.
- Any API contract change requires Akash's approval and a simultaneous update to fixture JSON and generated types.

---

## 9. Integration checkpoints and acceptance criteria

### CP0 — contract lock

- Pydantic schemas exist.
- OpenAPI JSON generated.
- Frontend/backend request and response types agree.
- Sample dirty/clean/manifest files agreed.

### CP1 — real analysis

- Upload the canonical CSV through the public or local frontend.
- Backend returns actual profile, issues, proposals, simulations and decisions.
- Frontend renders real issues and proposals without fixtures.

### CP2 — complete repair lifecycle

- At least one safe auto-apply, one approval-required repair and one refusal work end to end.
- A legitimate outlier is preserved.
- Apply is staged and atomic.
- Cell-level log is produced.

### CP3 — proof and export

- Re-detection runs after apply.
- Replay hash matches.
- Previously-valid cells damaged is measured.
- Cleaned CSV, report, modification log and recipe download correctly.

### CP4 — demo readiness

- Frontend typecheck/build pass.
- Backend test suite passes.
- Demo dataset runs through public URL.
- Core workflow works with LLM disabled.
- No mock data is shown in production.
- README provides clean Windows setup and deployment information.
- Local backup demo is available if hosting/network fails.

**Hard rule:** Do not spend time on P2 features until CP3 works.

---

## 10. Reporting format

Each owner reports only:

1. Completed task(s).
2. Files created/modified.
3. Commands and tests actually run, with pass/fail results.
4. Current blocker, if any, with reproduction steps.
5. Next assigned task.

Do not ask the team to choose the next feature. The order above is the decision.
