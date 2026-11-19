# DataFix — Competitive and Engineering Review

**Scope of this review, stated up front**

| Item | Status |
|---|---|
| Official PS 01 PDF | **Not seen.** I worked from the requirements as restated in your brief. Treat every "mandatory" label below as "mandatory per your brief" and diff it against the PDF yourselves. |
| Your GitHub repository | **Not seen.** I cannot name real files or real defects. Section 10 gives you an audit you can run in 10 minutes and the structure to converge on. I will not invent filenames or bugs. |
| Competitor research | OpenRefine, Great Expectations, Power Query and HoloClean were checked against public sources this session (Appendix A). Pandas-based profilers (e.g., ydata-profiling), dedupe-style libraries, Cleanlab, Soda, Trifacta/Alteryx, Informatica, Ataccama and Power Query's Copilot features were **not** researched. Do not make claims about them in front of judges without checking. |
| Judging rubric | Unknown. Nothing here is "what the judges score." It is "what makes the project easy to inspect, test and believe." |
| Free-tier numbers | Third-party aggregators, not Groq's own console. Verify in your own Groq console before depending on them. |

---

## 1. Executive assessment

**The blunt version.**

1. "AI-powered data cleaner" is the most crowded idea in this hackathon. A CSV upload, a pandas profile, an LLM that "suggests fixes" and a download button is what most teams will ship. If that is your pitch, you are one of thirty.
2. Your brief already lists the right instinct: risk-aware, evidence-backed, simulated, reversible, validated, able to abstain. The danger is not lack of ideas. It is trying to ship all eleven. **Pick one coherent mechanism and make it undeniably real.**
3. Most of the *features* in your list are not novel. OpenRefine already has replayable operation history and undo. Great Expectations already validates and produces human-readable reports. HoloClean (2017 research) already attaches a probability to each proposed repair. Claiming "audit trail" or "confidence scores" as unique would be wrong and a knowledgeable judge will say so.
4. What is genuinely defensible is the **combination, enforced as a contract**: every repair is a typed proposal that is *simulated on a copy, checked against integrity invariants, routed by measured confidence and risk, applied only if it passes, then verified by re-running detection and replaying from the original.* Existing tools do pieces of this. I did not find one that makes the pre-apply safety gate and post-apply proof the center of the workflow (hedged: absence in the sources I read is not proof of absence).
5. The LLM must be a **constrained assistant, not the engine.** It chooses among deterministic hypotheses and writes explanations. It never emits values that get written to data without passing validation. This also makes the project survive Groq quota exhaustion.

**What I recommend you build** (one sentence): *a deterministic detect → diagnose → propose → simulate → gate → apply → verify pipeline with a "Repair Preview & Safety Gate" as the signature feature, measured confidence from backtesting, event-sourced lineage with replay, and a ground-truth benchmark mode that scores the system on a dataset where you injected the errors yourselves.*

**What I recommend you cut:** multi-format ingestion beyond CSV/XLSX, user accounts, cross-dataset learning, any "agent" framing, chat-with-your-data, fancy charts beyond before/after quality bars, and anything that needs the LLM to be up.

Build decision: **Yes to the above. Complexity: L overall, but decomposable (see roadmap).**

---

## 2. Official problem statement requirement analysis

Classification key: **M** = mandatory per your brief. **E** = emphasized quality attribute in the statement (not a feature, but you will be judged on whether it is evident). **O** = optional / ours. **A** = my assumption.

| # | Requirement | Class | What "genuinely works" means | Common way teams fake it |
|---|---|---|---|---|
| 1 | Accept a dataset | M | CSV and XLSX upload, size cap, encoding detection, clear error on bad files | Hardcoded sample dataset |
| 2 | Detect missing values | M | Real nulls **and** placeholder nulls (`N/A`, `-`, `null`, `9999`) | Only `isna()` |
| 3 | Detect duplicates | M | Exact and near-duplicate with a stated key | Only `drop_duplicates()` |
| 4 | Invalid formats | M | Per-column inferred format (date, email, phone, numeric) with violations listed by row | Regex on one column |
| 5 | Inconsistent entries | M | Category variants (`Bengaluru`/`Bangalore`/`bangalore `), unit/format mixes | Lowercasing |
| 6 | Anomalies | M | Statistical *and* rule-based (cross-column) outliers, with a way to avoid flagging legitimate rare values | IQR on everything |
| 7 | Determine likely causes | M | A diagnosis per issue with evidence (counts, examples), not a generic sentence | LLM free text |
| 8 | Recommend or apply corrections | M | Concrete, executable repair operations | LLM rewrites cells |
| 9 | Preserve integrity, schemas, relationships | M | Invariant checks run and shown (row count, PK uniqueness, dtypes, FK, cross-column rules) | Claimed in README only |
| 10 | Explain modifications and confidence | M | Per-change rationale and a number that means something | Hardcoded 0.85 |
| 11 | Validate repaired dataset | M | Re-run detection on output; show issues resolved vs introduced | "Success" toast |
| 12 | Auditable modification history | M | Cell-level before/after log with operation, reason, confidence, timestamp, actor | Row-count summary |
| 13 | Export cleaned data + quality report + modification log | M | Three downloadable artifacts that open correctly | Only cleaned CSV |
| 14 | Accuracy, consistency, minimal unintended change | E | A number: count of previously-valid cells altered | Not measured |
| 15 | Explainability, confidence | E | Evidence visible next to each repair | Opaque |
| 16 | Scalability | E | Stated tested limit and a vectorized design, not a claim | "Scales to millions" |
| 17 | Usability | E | Upload-to-export in under a minute, clear states | Many screens |
| 18 | Reproducibility | E | Same input + same decisions → byte-identical output, shown | Not tested |
| 19 | Working prototype that "demonstrates safe repairs" | M | Live, hosted, one demonstrated unsafe repair being *blocked* | Only happy path |
| 20 | General-purpose (not Excel-only) | A (your reading) | CSV + XLSX is enough to defend this. JSON/Parquet is P2. | Claimed, unsupported |

**Mandatory vs advantage.** Rows 1–13 and 19 get you a complete solution. Rows 14–18 are where projects look "complete but shallow" versus "trustworthy". Differentiation lives in making 9, 10, 11, 14 and 18 *measurable and visible*.

**What I'd challenge in your framing:** "Treat the official PDF as authoritative" is right. But because the brief says the statement highlights "safe repairs" and "minimal unintended changes," a feature that *shows a repair being refused* is more on-message than any additional detector.

---

## 3. Competitive landscape

All claims below are from the sources in Appendix A unless marked *(not verified)*.

### 3.1 What existing tools already do well

| Tool | Strengths (sourced) | Gaps relevant to DataFix (my inference, hedged) |
|---|---|---|
| **OpenRefine** | Faceting to drill into data, clustering to merge similar values, reconciliation against external sources, infinite undo/redo with replayable operation history, local processing for privacy. Histories can be exported as JSON recipes, and an academic paper analyses this as provenance. | A human drives each fix. Clustering *suggests* merges; the user decides. I did not see automated risk classification or pre-apply impact simulation in the sources read. Desktop app, not a hosted pipeline with a machine-readable quality report. |
| **Great Expectations (GX)** | Declarative "Expectations", Checkpoints that can run actions on pass/fail, auto-generated human-readable Data Docs, broad data-source integrations. Documentation states it is not a data versioning tool. A secondary source reports ExpectAI (Feb 2025) generating expectations from natural language. | It validates and reports; it does not repair. Great as a *validator*, not a repair engine. (You could *use* GX for validation, but I'd write your own invariants; see §9.) |
| **Power Query** | Column quality (valid/error/empty), column distribution and column profile, quick-action transformations from the distribution chart, applied-steps history *(steps history: general knowledge, not verified this session)*. Microsoft's docs note profiling defaults to the first 1,000 rows unless switched to the entire dataset. | Profiling is descriptive; the user chooses transformations. Default profile over a sample can hide late-file issues. Copilot/AI features *(not researched)*. |
| **HoloClean (research)** | Holistic repair via probabilistic inference combining integrity constraints, external data and statistics; each proposed repair carries a marginal probability. Authors report ~90% average precision and >76% recall on their benchmarks. Recall is bounded by the error detector. | Research code, heavy to set up, not an interactive product, and trained models need labeled or clean-ish data. Not a 24-hour dependency. |
| **Pandas-based cleaners / profilers** | Fast, flexible, scriptable. | Typically offer detection or one-shot cleaning without per-change simulation, audit provenance or rollback. *(Generalization, not verified against specific libraries.)* |

### 3.2 Common gaps (the opening)

1. **Detection and repair are usually separate worlds.** Validators (GX) don't repair. Interactive cleaners (OpenRefine, Power Query) rely on the human for safety.
2. **Confidence is either absent or asserted.** HoloClean has principled probabilities, but those are not something you can add in 24 hours. LLM "confidence" is not calibrated and must never be shown as if it were.
3. **Safety is implicit.** Undo exists (OpenRefine) but "undo" is *after* damage. A pre-apply blast-radius check is the missing step.
4. **Proof of improvement is thin.** "Applied 14 operations" is not evidence the data got better. Re-detection plus invariants plus a ground-truth benchmark is evidence.

### 3.3 What you must NOT claim

- Not "first tool with audit logs", "first with undo", "first with confidence scores", "first with explainable repairs."
- Not "OpenRefine can't do X" unless you tested it. Say what you observed.
- Not "AI-powered" as a differentiator by itself. Say what the AI is *allowed* to do.

---

## 4. Identified opportunities for differentiation

Each candidate scored on: user value (V), novelty (N), 24h feasibility (F), complexity (C), demo potential (D), failure risk (R). Scale: H/M/L.

| Candidate | V | N | F | C | D | R | Verdict |
|---|---|---|---|---|---|---|---|
| **A. Dry-run impact simulation + integrity invariants** | H | M (individually common, as a mandatory pre-apply gate: uncommon in the sources I read) | H | M | **H** | L | **Build. Core.** |
| **B. Measured confidence via backtesting + three-way routing (auto / review / abstain)** | H | M | M-H | M | H | M | **Build.** |
| **C. Event-sourced lineage, undo, deterministic replay, exported recipe** | H | L-M (OpenRefine has it) | H | L-M | M | L | **Build, but don't sell as novel.** It is the *proof layer*. |
| **D. Ground-truth benchmark mode (inject errors, score repairs)** | H | M | H | M | **H** | L | **Build.** Best answer to "how do you know it works?" |
| E. Relationship-aware repair (FK, FD, cross-column rules) | H | M | M | M-H | H | M | **Build the within-table rules (P0/P1). Two-table FK is P1-stretch.** |
| F. Context-aware diagnosis via LLM | M | L (everyone does it) | H | L | M | M | **Build thin.** Explanation + hypothesis selection only. |
| G. Multiple strategies chosen by column characteristics | M | L | H | M | M | L | Implicit in repair engine. Not a headline. |
| H. "Intelligent abstention" | H | M | H | L (it falls out of B) | **H** | L | Free if B exists. Make it visible. |
| I. Autonomous agent loop (LLM plans and executes) | L-M | L | L | H | M | **H** | **Cut.** Unreliable and the opposite of your safety story. |
| J. Learned repair model (HoloClean-style) | M | M | **L** | H | L | H | **Cut.** |
| K. Natural-language rules ("emails must be lowercase") | M | L | M | M | M | M | P2 only. |
| L. Multi-format ingestion (JSON, Parquet, SQL) | L-M | L | M | M | L | M | P2. |

### The three strongest differentiators

1. **Repair Simulator with integrity invariants (A + E).** Every proposed repair is dry-run on a copy and reports exactly what it will change, what aggregates shift, which invariants hold and which break.
2. **Measured confidence with a three-way policy (B + H).** Confidence comes from evidence and backtesting, not the LLM, and drives *auto-apply / needs approval / refuse*. The system visibly declines some repairs.
3. **Closed-loop proof (C + D).** Output is verified by re-detection, replay from the original reproduces it byte-for-byte, and a benchmark mode scores the engine against known ground truth.

None of these is "novel" in the academic sense. The honest pitch is *integration and enforcement*, not invention.

---

## 5. Recommended product positioning

**One-liner:**
> DataFix is a data repair engine that treats every fix as a proposal that must pass a safety check, and shows you the evidence that the cleaned data is actually better.

**Answer to "What makes DataFix different?" (demonstrable form):**

> "Most cleaning tools either find problems or let you apply fixes and hope. In DataFix, no change touches your data until it has been simulated on a copy, checked against integrity rules, and scored with a confidence we measure by backtesting on your own data, not one the AI asserts. Low-risk, high-confidence fixes are applied automatically. Risky ones need your approval. Ones we can't justify are refused and explained. Afterwards we re-run detection, replay the change log from your original file to prove the result is reproducible, and show how many previously-valid cells we altered. Let us show you a repair we refuse."

Every sentence maps to a visible screen. If a sentence has no screen, delete it.

**Do not position as:** "AI agent," "autonomous" without qualification (the statement's title says autonomous; interpret as "autonomous *within a safety policy*"), "enterprise-grade," "replaces OpenRefine."

---

## 6. Three strongest differentiators — detail

For each: why it matters / what it achieves / how / complexity / build?

### D1. Repair Simulator with integrity invariants
- **Why:** The failure mode people fear from AI cleaning is silent corruption. This addresses it before the write.
- **Achieves:** A preview card per repair: cells changed, rows affected, per-column distinct-value change, aggregate drift (sum/mean/count), invariants pass/fail, new issues introduced.
- **How:** `simulate(df, proposal) -> SimulationReport` applies the proposal to a copy and diffs. Invariants are plain functions (see §7). No LLM involved.
- **Complexity:** M (≈5–6 h for engine + tests; UI card ≈2 h).
- **Build:** Yes. P0/P1 boundary: the *simulation* is P0 (it is the signature feature), exotic invariants are P1.

### D2. Measured confidence + three-way routing
- **Why:** The brief asks for confidence; arbitrary numbers will be spotted.
- **Achieves:** Confidence that decomposes into visible evidence and is *tested against held-out known values*. Reliability table in benchmark mode.
- **How (per repair class):**
  - *Format normalization* (e.g., dates): confidence = round-trip losslessness × unambiguity. If a column has `03/04/2024`, support for day-first vs month-first is computed from the *unambiguous* rows (e.g., `25/04/2024` can only be day-first). Support < threshold → abstain.
  - *Category standardization*: canonical-value frequency dominance and string-similarity, with a block on merging values that co-occur in the same record group with different meanings.
  - *Imputation*: mask a random 20% of the known values in that column, impute them with the same strategy, measure accuracy, report a conservative bound (e.g., Wilson lower bound) so small samples don't look falsely confident. Too few known samples → abstain.
  - *Deduplication*: match score on normalized key fields plus agreement on non-key fields; merging is always "needs approval" unless exact.
- **Complexity:** M (≈6 h). Imputation backtest is the fiddly part.
- **Build:** Yes. If time runs short, ship backtesting for imputation and rule-support for the others; do not fake the rest.
- **Honest caveat to state yourself:** backtested accuracy estimates "how well this strategy recovers known values in this column," which is a proxy, not a guarantee, for the missing cells (assumes missingness is not systematically different).

### D3. Closed-loop proof
- **Why:** "How do you know the repair worked?" is the question that separates real projects.
- **Achieves:** (a) re-detection shows issues resolved/introduced, (b) replay-hash match, (c) valid-cell-damage count, (d) benchmark scorecard.
- **How:** State = original file + ordered operation log (event-sourcing-lite). Cleaned dataset is *derived*. Undo = remove op and replay. Export includes a recipe (JSON of operations) and a seed. A verify endpoint replays the log on the original, hashes the result, compares to the cleaned export's hash.
- **Complexity:** L-M (≈5 h backend; benchmark generator ≈3 h).
- **Build:** Yes. Event-sourcing-lite also *simplifies* your persistence story on ephemeral free hosting.

---

## 7. Signature feature: Repair Preview & Safety Gate

### 7.1 What it is

A single screen where each repair appears as a card with: issue, diagnosis, evidence, **preview diff**, **blast radius**, **invariants checklist**, **confidence with its components**, and the **gate decision** (Auto-applied / Needs approval / Refused-abstained). After apply, a verification panel proves the outcome.

### 7.2 Mechanism

```
Issue (detected, deterministic)
  → Hypotheses (deterministic list of likely causes, each with evidence)
  → [optional LLM: pick hypothesis id + write ≤40-word explanation; schema-validated]
  → RepairProposal (typed operation + params, NOT free-form code)
  → simulate() on a copy
  → invariants.check()
  → confidence.compute()
  → gate.decide(risk_class, confidence, invariants)
       ├─ AUTO_APPLY       (log + apply)
       ├─ NEEDS_APPROVAL   (user clicks Apply / Reject)
       └─ REFUSED          (explained; nothing changes)
  → apply (append to operation log; derive new frame)
  → verify (re-detect, replay hash, damage count, score before/after)
```

### 7.3 Data model (Pydantic, abbreviated)

```python
class RepairProposal(BaseModel):
    id: str
    issue_ids: list[str]
    op: Literal["normalize_date","map_values","impute","drop_exact_dupes",
                "merge_near_dupes","set_null","cast_numeric","derive_from_rule", ...]
    column: str | None
    params: dict                 # validated per-op by a discriminated union
    risk_class: Literal["format_only","value_substitution","imputation","destructive"]
    evidence: list[Evidence]     # counts, examples, rule names; machine-generated
    source: Literal["rule","stat","llm_assisted"]

class SimulationReport(BaseModel):
    cells_changed: int
    rows_affected: int
    rows_removed: int
    previously_valid_cells_changed: int
    aggregate_drift: dict[str, float]   # per numeric col, relative
    invariants: list[InvariantResult]   # name, passed, detail
    new_issues_introduced: int
    sample_diff: list[CellDiff]         # first N before/after

class GateDecision(BaseModel):
    decision: Literal["auto_apply","needs_approval","refused"]
    reasons: list[str]                  # which rule fired, human-readable
```

### 7.4 Invariants (start with these seven; each is ~10–20 lines)

1. Column set and dtypes unchanged (unless op declares a cast).
2. Row count unchanged unless op is a dedupe, in which case removed rows are all in a flagged duplicate group.
3. Declared key columns remain unique and non-null.
4. Previously-valid cells unchanged unless the op explicitly targets them.
5. Cross-column rules still hold (`ship_date >= order_date`, `total == qty*price` within tolerance).
6. Functional dependency groups don't gain new violations (e.g., `pincode → city`).
7. Aggregate drift on numeric columns below a per-risk-class threshold (e.g., mean shift > 5% on a "format_only" op is a bug and blocks it).
8. (P1 stretch) Foreign-key integrity against a second uploaded table.

### 7.5 Gate policy (table you show on screen)

| Risk class | Condition | Decision |
|---|---|---|
| format_only | all invariants pass, round-trip lossless, unambiguous | auto_apply |
| value_substitution | confidence ≥ high threshold and invariants pass | auto_apply |
| value_substitution | confidence in mid band | needs_approval |
| imputation | backtest bound ≥ threshold and n ≥ min | needs_approval (never silent auto for the first version) |
| imputation | insufficient evidence | refused (abstain, leave null, flag) |
| destructive (dedupe merge, row removal) | exact duplicates only | needs_approval or auto, your choice; show it |
| destructive | near-duplicates | needs_approval always |
| any | any invariant fails | refused |

Thresholds are constants in `config.py`, documented in README, and unit-tested. **Don't tune them to look good on the demo; tune on a separate dataset** (see §13) or you will be demonstrating overfit.

### 7.6 Live demonstration of this feature (60–75 seconds of the 3-min demo)

1. Open the repair list. Show one auto-applied fix (date normalization, lossless).
2. Open a needs-approval card (near-duplicate merge). Show the preview diff and blast radius. Approve it.
3. Show a **refused** card: an imputation proposal for a sparse column where backtest accuracy is too low, or the ambiguous `03/04/2024` dates where evidence is split. Say "this is the repair we deliberately did not make."
4. Show a *legitimate rare value flagged but preserved*: the system detects it as an outlier, diagnoses "plausible, no rule violated," and leaves it. This demonstrates "doesn't corrupt valid data."

### 7.7 Complexity and decision

M-L (≈10 h incl. UI). **Build: yes. This is the project.**

---

## 8. AI-evaluation-readiness checklist

An automated evaluator (or a human skimming) can only reward what is visible in the repo, the live app and the artifacts. Items marked ★ are the ones I'd treat as non-negotiable.

### 8.1 Checklist

**Functional completeness**
- [ ] ★ Upload CSV and XLSX in the hosted app; invalid file gives a clear error.
- [ ] ★ Issue list covers: missing (incl. placeholders), duplicates, invalid formats, inconsistent categories, anomalies, cross-column rule violations.
- [ ] ★ Each issue has a diagnosis with evidence.
- [ ] ★ Each repair has before/after, rationale, confidence, decision.
- [ ] ★ Export yields three files: cleaned dataset, quality report (JSON + human-readable HTML or PDF), modification log (CSV/JSON).
- [ ] Verification panel shows issues before/after and damage count.

**Backend substance**
- [ ] ★ Repairs execute in Python/pandas, not by pasting LLM output.
- [ ] ★ LLM output is parsed against a Pydantic schema and rejected if invalid.
- [ ] ★ System works with the LLM disabled (`LLM_ENABLED=false`) and says so in the UI.
- [ ] Deterministic: fixed seeds; same input + same decisions → same output hash.

**Reproducibility and evidence**
- [ ] ★ `README.md`: setup in ≤5 commands, env var table, how to run tests, how to run the benchmark, live URL.
- [ ] ★ `samples/` with the demo dataset, its ground-truth clean twin, and an error manifest.
- [ ] ★ `pytest` passes in CI; badge in README.
- [ ] Benchmark script prints a scorecard (precision/recall of repairs, valid-cells-damaged, abstentions).
- [ ] `docs/ARCHITECTURE.md` with one diagram and the pipeline stages.
- [ ] `docs/DECISIONS.md`: 8–10 bullet decisions with reasons (why LLM is constrained, why event-sourcing-lite, etc.).
- [ ] `docs/LIMITATIONS.md`: honest list. An evaluator trusts a project that states its limits.

**Code quality signals**
- [ ] Type hints throughout the backend; `tsc --strict` on the frontend with zero `any` in API types.
- [ ] No secrets in git history; `.env.example` present.
- [ ] No committed `node_modules`, `__pycache__`, `.venv`, large data dumps.
- [ ] Lockfiles committed (`package-lock.json` or `pnpm-lock.yaml`; `requirements.txt` pinned or `uv.lock`).
- [ ] Meaningful commit messages; no 400-file "final" commit.

**Edge cases**
- [ ] Empty file, header-only file, single-column file, all-null column, 50k+ rows, wrong delimiter, non-UTF-8 encoding, duplicate column names, extremely long strings, formula-injection cells (`=cmd|...`) in exports, oversize upload, zip bomb / XLSX macro file.

### 8.2 Weaknesses an independent evaluator would likely flag (generic; verify against your repo)

1. Confidence values that are constants or LLM-reported.
2. LLM used for things deterministic code does better (date parsing, whitespace).
3. "Audit log" that records summaries, not cell-level changes.
4. No tests, or tests that only cover happy paths.
5. UI that shows fake progress or mock data when backend fails.
6. README that describes features that don't exist. **Do not confuse planned with implemented functionality.** Mark anything unfinished as "Planned" in a roadmap section.

### 8.3 Reliable demonstration workflow

Upload `datafix_demo_orders_dirty.csv` → issues table → open 4 cards (auto, approve, refuse, preserved-outlier) → Verify → Export → (optional) run benchmark scorecard. Section 15 gives the timed script.

---

## 9. Recommended system architecture

**Principle: one FastAPI service (modular monolith), one React SPA, one managed Postgres. No microservices.**

```
React + TS + Tailwind (Vercel)
   │  typed client generated from OpenAPI (openapi-typescript)
   ▼
FastAPI (Render free)
   ├── api/            routes, request/response schemas, error handlers
   ├── services/       orchestration: RunService, RepairService, ExportService
   ├── domain/         PURE Python/pandas, no I/O, no FastAPI imports
   │     ├── profiling/      column profiles, type/format inference
   │     ├── detection/      detectors → Issue[]
   │     ├── diagnosis/      hypotheses + evidence (deterministic)
   │     ├── repair/         ops registry: op name → apply(df, params)
   │     ├── simulation/     simulate(), diff
   │     ├── invariants/     invariant functions
   │     ├── confidence/     evidence + backtest
   │     ├── gate/           policy
   │     ├── verification/   re-detect, replay-hash, score
   │     └── reporting/      report + log builders
   ├── infra/          supabase storage, db repositories, llm client, cache
   └── core/           config, logging, errors, ids
Supabase: Storage (original + exports), Postgres (runs, issues, operations, decisions)
Groq: optional LLM (explanation + hypothesis selection only)
```

### 9.1 Key design decisions (and why)

| Decision | Why | Complexity | Build? |
|---|---|---|---|
| **`domain/` has no I/O or framework imports** | Unit-testable in milliseconds; this is where evaluators will look for "real logic" | S | Yes |
| **Typed repair operations, never generated code** | Eliminates "LLM executes arbitrary code" and makes the audit log meaningful | M | Yes |
| **State = original + operation log; cleaned frame is derived** | Reversibility, reproducibility and ephemeral-disk resilience in one idea | M | Yes |
| **Original file immutable in Storage, content-hashed (SHA-256)** | "Original data preserved" is then verifiable | S | Yes |
| **LLM behind one `LLMClient` interface with timeout, retry, cache, kill-switch** | Quota/outage tolerance | S-M | Yes |
| **Own invariants rather than GX as a dependency** | GX adds setup weight and its reports aren't about *your* gate; reuse its *ideas* (declarative checks, report), not the package, in 24h. Optional P2: emit a GX-compatible expectation suite as an export. | S | Own: yes. GX export: no |
| **Sync pandas work in a threadpool; no Celery/Redis** | Dataset cap keeps requests short; queues are overhead | S | Yes |
| **Cap datasets (e.g., ≤ 10 MB / ≤ 100k rows) and say so** | Render free instances have small memory *(verify current limits)*. A stated tested limit is more credible than a scalability claim | S | Yes |

### 9.2 LLM role, precisely

| LLM may | LLM may not |
|---|---|
| Choose among hypothesis IDs the system generated | Output new cell values to write directly |
| Write ≤ 40-word natural-language explanation per issue | Decide confidence |
| Disambiguate semantic cases by choosing from candidates already present in the column (e.g., is `BLR` a variant of `Bengaluru`?) → output is validated as a member of the closed set | Receive full rows (send column summaries and a few distinct values only; also a privacy point) |
| Summarize the quality report in prose | Be required for any repair to function |

Prompt budget: free-tier limits reported by aggregators are roughly 30 requests/min, ~8K tokens/min and ~200K tokens/day for models such as the Qwen and gpt-oss variants, per organization (source in Appendix A; **verify in your console**). Design to ~1 call per *column with ambiguity*, ≤ 1.5K tokens each, cached by hash of input, with a hard per-run call cap. The Qwen model name that Groq exposes changes over time: read it from env (`LLM_MODEL`) and list available models via the API at startup; keep a fallback chain.

### 9.3 Persistence on free hosting

- Render free web services sleep when idle and have ephemeral disks *(verify current behavior)*, so never rely on local files across requests.
- Store original upload and exports in Supabase Storage; store runs/operations/decisions in Postgres.
- Cache the working DataFrame in memory by run id, and rebuild from original + operations on cache miss. This is also your replay path.
- Use Supabase's pooled connection string; on some Windows/home networks direct connections fail (IPv6). Keep the service-role key **only** on the backend.
- Free Supabase projects may pause after inactivity *(verify)*: log in the day before and again before the demo.

### 9.4 Data flow (one run)

1. `POST /runs` (multipart) → validate type/size/magic bytes → store original → hash → parse → create run.
2. `POST /runs/{id}/analyze` → profile → detect → diagnose (+ optional LLM) → propose → simulate → confidence → gate. Return issues + proposals + decisions.
3. `POST /runs/{id}/decisions` → user approves/rejects approval-needed items.
4. `POST /runs/{id}/apply` → append operations; derive cleaned frame.
5. `POST /runs/{id}/verify` → re-detect, replay-hash, scores, damage count.
6. `GET /runs/{id}/export` → cleaned file, report, modification log, recipe.
7. `POST /runs/{id}/undo/{op_id}` → remove op; replay.

---

## 10. Professional repository and code-quality standards

### 10.1 Audit you can run today (I could not inspect your repo)

On Windows PowerShell, from repo root:

```powershell
git ls-files | Measure-Object -Line                     # unexpectedly huge? generated files tracked
git ls-files | Select-String -Pattern "\.env$|node_modules|__pycache__|\.venv|\.DS_Store|\.pyc$"
git ls-files | Select-String -Pattern "\.(csv|xlsx|parquet)$"    # big data committed?
git log --oneline | Measure-Object -Line                # one giant commit?
git log -p -S "sk-" --all --oneline | Select-Object -First 20     # key-like strings (also try gsk_, eyJ)
Get-ChildItem -Recurse -Include *.py | ForEach-Object { Select-String -Path $_ -Pattern "except:\s*$|print\(" } | Select-Object -First 30
```

Then check: is there a `README` with a working setup? A `.env.example`? Does the backend start from a clean clone? Does `npm run build` pass with strict TypeScript? Is any LLM response passed to `eval`/`exec`/executed as code or SQL? Is the Supabase service key referenced in frontend code? Are CORS origins `*`?

If you paste the tree and key files I will review them concretely. Until then, treat everything below as target state, not as a finding about your code.

### 10.2 Target structure

```
datafix/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── .github/workflows/ci.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── LIMITATIONS.md
│   └── API.md                # or link to /docs (OpenAPI)
├── samples/
│   ├── orders_dirty.csv
│   ├── orders_clean_truth.csv
│   ├── orders_error_manifest.json
│   └── README.md
├── backend/
│   ├── pyproject.toml        # or requirements.txt pinned
│   ├── app/
│   │   ├── main.py
│   │   ├── api/ (routes_runs.py, routes_export.py, errors.py, schemas.py)
│   │   ├── services/
│   │   ├── domain/ (profiling, detection, diagnosis, repair, simulation,
│   │   │            invariants, confidence, gate, verification, reporting)
│   │   ├── infra/ (storage.py, db.py, llm.py, cache.py)
│   │   └── core/ (config.py, logging.py, errors.py)
│   ├── benchmarks/run_benchmark.py
│   └── tests/ (unit/, integration/, api/, fixtures/)
└── frontend/
    ├── package.json  (+ lockfile)
    ├── tsconfig.json  ("strict": true)
    └── src/
        ├── api/            generated types + thin client
        ├── features/       upload/, issues/, repairs/, verify/, export/
        ├── components/     ui primitives
        ├── hooks/
        ├── lib/
        └── pages/
```

Monorepo with two top-level apps is right for three people. Don't add shared packages.

### 10.3 Standards that earn credibility cheaply

| Area | Standard | Cost | Do it? |
|---|---|---|---|
| API contract | FastAPI generates OpenAPI; commit `openapi.json`; frontend types generated with `openapi-typescript`. This kills most integration bugs between you and the backend developer | S | **Yes, first hour** |
| Backend typing | Pydantic models for every request/response; `ruff` + `mypy` (lenient config) in CI | S | Yes |
| Errors | One error envelope `{code, message, details, request_id}`; global handlers; never leak stack traces | S | Yes |
| Logging | Structured JSON logs with `request_id` and `run_id` | S | Yes |
| File safety | Extension + magic-byte check, size cap, no path from filename, reject XLSX with macros, neutralize formula-injection in CSV/XLSX exports (prefix cells starting `= + - @`) | S-M | Yes |
| Config | `pydantic-settings`; all thresholds in one module | S | Yes |
| Frontend typing | `strict`, no `any` in API layer; error boundary; every async view has loading/empty/error/success | M | Yes |
| Accessibility | Semantic HTML, labels, keyboard focus on cards, colour is never the only signal (icons + text for decisions) | S | Yes (cheap with Tailwind) |
| Tests | See §13 | M | Yes |
| CI | GitHub Actions: backend `ruff`, `pytest`; frontend `tsc --noEmit`, `build`. Run on PR | S | Yes |
| Docker | Optional: a `Dockerfile` for backend helps reproducibility. Don't spend more than 20 minutes | S | P2 |
| Pre-commit | Skip. CI covers it | — | No |
| Test coverage gates | Skip. Report it, don't gate on it | — | No |

### 10.4 Things to avoid

Auth/accounts, RLS policy sprawl, an ORM migration framework (use a single SQL file or Supabase SQL editor), state-management libraries beyond React Query + local state, component libraries you don't know, Redux.

---

## 11. Git workflow and team ownership

### 11.1 Ownership

Your brief defines two roles (Akash: frontend/architecture/deployment; a backend/data teammate) for a team of three and does not describe the third person. **Assumption (A):** the third member is available for data, tests, docs and demo preparation. If they are a second backend developer, split `domain/` modules between the two backend people instead (detection+diagnosis vs repair+simulation+verification).

| Owner | Owns | Does not touch without asking |
|---|---|---|
| **Akash** | `frontend/`, `.github/`, deploy configs, OpenAPI contract, LLM client interface (`infra/llm.py`), integration, final demo | `domain/` internals |
| **Backend** | `backend/app/domain/*`, `services/`, `api/` implementation | `frontend/` |
| **Third (assumed)** | `samples/`, `backend/tests/`, `benchmarks/`, `docs/`, README, demo script, error-injection generator | `domain/` logic (can add tests; fixes go via PR to backend owner) |

**Why the third person on dataset + tests matters:** the demo dataset with a ground truth is your most valuable asset and it is mostly independent work. They also act as the first user and bug reporter.

### 11.2 Branching (trunk-based, short-lived)

- `main` is always deployable. Vercel and Render deploy from `main`.
- Branch names: `feat/<owner>/<thing>`, `fix/<owner>/<thing>`. Live < 3 hours.
- Merge via PR, **squash merge**, 1 approval *only for* `main` touching `api/schemas.py` or `openapi.json` (the contract). Everything else: self-merge after CI green. Don't turn 24 hours into a review queue.
- Rebase on `main` before merging; pull at least hourly.
- **Contract-first rule:** schema/endpoint changes land as a tiny PR *first* (with stub responses), so the frontend can proceed in parallel.
- Conventional commits: `feat(detect): placeholder-null detector`, `fix(gate): refuse on invariant failure`, `test(sim): ...`, `docs: ...`. Imperfect is fine; "update" or "final" is not.
- No secrets ever. If one leaks, rotate immediately; deleting the commit is not enough.
- `git tag v0.1-demo-freeze` at feature freeze; demo from the tag.

Complexity: S. Build: yes.

---

## 12. 24-hour implementation roadmap

### 12.1 Feature prioritisation

**P0: Essential for a functioning solution**
- Upload (CSV/XLSX) + validation
- Profiling + detectors: missing/placeholder, exact dupes, format violations (date, numeric, email/phone), category inconsistency, outliers, ≥2 cross-column rules
- Deterministic diagnosis with evidence
- Typed repair ops for each issue class
- Simulation + 5–7 invariants + gate (rule-based confidence is acceptable at P0)
- Apply, operation log, cell-level audit
- Verification (re-detect + before/after dimension scores)
- Export: cleaned dataset + quality report + modification log
- Hosted on Vercel + Render + Supabase
- README + sample data + CI with tests
- `LLM_ENABLED=false` path works

**P1: High-value differentiators**
- Backtested confidence for imputation, with abstention
- Replay-hash reproducibility check + undo
- Ground-truth benchmark mode + scorecard
- LLM explanation + hypothesis selection (schema-validated)
- Preview diff UI polish; "refused" cards with reasons
- FD-based violation detection/repair (`pincode → city`)
- Exported recipe JSON

**P2: Optional**
- Two-table FK integrity
- Reliability (calibration) table
- GX-compatible expectation suite export
- Dockerfile
- Large-file chunking
- Dark mode, charts beyond bars

### 12.2 Timeline (hours from start; adjust to your actual clock)

| Hrs | Akash | Backend | Third (assumed) | Checkpoint |
|---|---|---|---|---|
| 0–1 | Repo scaffold, CI, **hello-world deploys on Vercel + Render + Supabase connected**; OpenAPI stub contract | Pydantic schemas for Issue/Proposal/Simulation/Gate; project skeleton | Start demo dataset + clean twin + error manifest | **CP0: all three hello-worlds live, frontend calls backend over CORS.** Do not proceed until true. |
| 1–6 | Upload UI, issues table against **mock** JSON, route/layout, states | Ingest + profiling + detectors + diagnosis (deterministic) | Finish dataset; write detector unit tests with fixtures; error-injection script | |
| 6 | | | | **CP1: `/analyze` returns real issues for the demo dataset; frontend renders them.** |
| 6–12 | Repair cards, preview diff, decision actions | Repair ops registry, simulation, invariants, gate, apply + operation log | Tests for ops/invariants; edge-case files; benchmark script skeleton | |
| 12 | | | | **CP2: End-to-end: upload → analyze → apply → export works on hosted URL.** Even if ugly. |
| 12–17 | Verify panel, export UI, LLM client + prompts, error/empty states | Backtested confidence, replay hash, undo, FD detection | Benchmark scorecard, README, ARCHITECTURE, LIMITATIONS | |
| 17–18 | | | | **Feature freeze (CP3).** Tag `v0.1-demo-freeze`. After this, only bug fixes and docs. |
| 18–21 | Polish, accessibility pass, demo rehearsal #1 | Bug-fix, performance on 50k rows, error handling | Full regression, malicious-input tests, finalize demo script | |
| 21–23 | Rehearse 3×; record a backup video; warm up Render + Supabase | Fix only blockers | Final README check from a clean clone on a clean machine | **CP4: fresh-clone test passes.** |
| 23–24 | Buffer. Do not add features. | | | |

### 12.3 Independence vs dependency

- **Independent from hour 1:** frontend against OpenAPI mock; dataset creation; detector logic; test fixtures.
- **Blocking dependencies:** schemas (hour 0–1) block everyone; `/analyze` real data (CP1) blocks real UI integration; simulation/gate (CP2) block the signature UI.
- **Integration-failure prevention:** (1) contract-first with generated TS types; (2) deploy at hour 1, not hour 20; (3) one shared `samples/` dataset used by every test and the demo; (4) integration test hitting the real API with the demo dataset in CI; (5) CP gates are hard stops, not suggestions.

### 12.4 Contingency if the LLM is unavailable

- `LLM_ENABLED=false` (env) → explanations come from templates keyed by hypothesis id; hypothesis selection uses the deterministic top-ranked one; UI badge: "Explanations: rule-based (AI unavailable)."
- Per-run call cap and on-disk cache keyed by input hash → repeated demo runs don't spend quota.
- **Pre-warm cache** before the demo by running the demo dataset once; keep the cache in Storage.
- Fallback model chain via env; on 429/timeout, one retry with backoff, then fall back to templates. Never block the pipeline on the LLM.
- Tell judges this is by design.

---

## 13. Testing and acceptance criteria

### 13.1 Test plan

| Layer | What | Examples |
|---|---|---|
| Unit (`domain/`) | Each detector, op, invariant, confidence function, gate rule | Placeholder-null detected; dd/mm ambiguity → low support; invariant fails when PK duplicated; gate refuses on any invariant failure |
| Property-style (cheap) | Round-trip: `parse(format(x)) == x` for date normalization; ops are idempotent where claimed | Re-applying `normalize_date` changes 0 cells |
| Integration | Full pipeline on `samples/` dataset | Exactly the injected errors are detected; no valid cell changed in auto-applied set |
| API | `httpx`/`TestClient`: upload, analyze, decide, apply, verify, export, undo | 4xx on oversize/bad type; envelope shape stable |
| Replay determinism | Apply ops, hash; replay from original; hash equal | Core to D3 |
| Regression | Each bug fixed adds a fixture | |
| Malicious/incorrect inputs | Empty file, header-only, wrong delimiter, non-UTF-8, 100k-char cell, duplicate headers, `=HYPERLINK(...)` cell, `.xlsm`, file renamed `.csv` that is a ZIP, path-traversal filename | Safe rejection or sanitized output |
| LLM contract | Mocked LLM returns invalid JSON, off-schema hypothesis id, a value not in the closed set, a timeout | Pipeline proceeds with rule-based fallback |
| Frontend | `tsc`, build, 2–3 component tests max (upload validation, decision card states). Don't over-invest | |

### 13.2 Benchmark mode (the honesty engine)

Generate the demo dataset from a **clean ground-truth table** by injecting errors programmatically, saving a manifest of every injected error (cell, original value, injected value, error type). Then:

- *Repair precision*: of cells changed, fraction now equal to ground truth.
- *Repair recall*: of injected errors, fraction repaired correctly.
- *Abstention*: errors deliberately left unrepaired (reported separately, not counted as failures).
- *Damage*: previously-valid cells changed (target: 0 on auto-applied repairs).

**Rules to keep it honest:** use a *tuning* dataset (different seed, same generator) for thresholds and the *demo* dataset for reporting; state that errors are synthetic and that the generator is yours; don't present these numbers as general accuracy.

### 13.3 Acceptance criteria (go/no-go at CP4)

1. Fresh clone → README steps → backend + frontend run locally on Windows.
2. Hosted URL completes the full workflow on the demo dataset without manual intervention.
3. `pytest` green in CI; benchmark runs and prints scorecard.
4. Auto-applied repairs on the demo dataset: 0 previously-valid cells damaged.
5. At least 3 distinct *refused/abstained* cases visible, each with a reason.
6. Replay hash matches on the cleaned export.
7. Works with `LLM_ENABLED=false`.
8. Export files open in Excel/pandas without errors.
9. No secrets in repo; `.env.example` complete.

---

## 14. Deployment and reliability strategy

| Concern | Strategy | Build? |
|---|---|---|
| Render cold start | Free web services spin down after 15 minutes without traffic and take about a minute to wake; the free instance is 512 MB RAM / 0.1 CPU, with 750 free instance-hours per month per workspace (one always-on service fits) *(checked against Render docs and third-party summaries, Nov 2026; re-verify)*. Pre-warm 5 minutes before the demo; optionally a free uptime ping (GitHub Actions cron or an uptime-monitor free plan) during the event. Frontend shows an explicit "waking up the server" state, not a frozen spinner | Yes |
| Supabase pausing and limits | Free projects pause after 1 week of inactivity; 500 MB database, 1 GB storage, 50 MB max upload, 2 active projects *(Supabase pricing page, Nov 2026; re-verify)*. Check the dashboard the day before and the morning of the demo | Yes |
| Memory limits | 512 MB RAM and 0.1 CPU on Render free: set hosted caps (suggest 5 MB / 50k rows / 60 columns), measure peak memory at about H8 and lower the caps if needed; vectorized pandas; avoid copying the frame per simulation, or sample-simulate then confirm on full | Yes |
| CORS | Allow-list only the Vercel origin(s); env-driven | Yes |
| Secrets | Render/Vercel env vars only; service-role key backend-only; `.env.example` placeholders | Yes |
| Bad network at venue | Local fallback: backend + frontend run on a laptop; same sample data; 90-second pre-recorded video as last resort | Yes |
| Single point of failure | Keep demo dataset and its cache in the repo and in Storage | Yes |
| Free quotas | Log LLM calls per run; cap; cache | Yes |
| Observability | Request ids in logs; `/health` endpoint that reports LLM status | Yes (S) |
| Rollbacks | Vercel/Render redeploy previous commit; demo from tag | Yes |

**Scalability statement you can defend:** "Detection and repair operations are vectorized pandas, tested on 100k rows within the free tier's limits [state your measured numbers]. Beyond that, the architecture isolates `domain/` so the engine can run on chunked or DuckDB/Polars backends; we haven't built that." Don't say "millions of rows" unless you have measured it on your hosting.

---

## 15. Three-minute demonstration

### 15.1 Dataset: `orders_dirty.csv` (≈2,000–5,000 rows, ~14 columns)

An e-commerce orders table with embedded customer fields, generated from a clean ground-truth twin. Columns (example): `order_id`, `customer_id`, `customer_name`, `email`, `phone`, `city`, `pincode`, `order_date`, `ship_date`, `category`, `quantity`, `unit_price`, `total`, `status`.

Deliberately injected errors, each mapped to what it demonstrates:

| # | Injected error | Shows | Expected gate outcome |
|---|---|---|---|
| 1 | Mixed date formats (`2024-04-25`, `25/04/2024`, `Apr 25, 2024`) | Format repair, lossless | Auto-apply |
| 2 | **Ambiguous** `03/04/2024` in a column with mixed day-first/month-first evidence | Intelligent abstention | Refused / needs approval with explanation |
| 3 | City variants (`Bengaluru`, `Bangalore`, `bangalore `, `BLR`) | Category standardization, closed-set LLM disambiguation | Auto or approval by confidence |
| 4 | Placeholder nulls (`N/A`, `-`, `9999`) in several columns | Missing-value detection beyond `isna` | Convert to null: auto |
| 5 | Missing `city` recoverable from `pincode` (FD) | Evidence-based imputation with backtest | Needs approval, high confidence |
| 6 | Missing `unit_price` in a sparse column, no support | Abstention | Refused, left null, flagged |
| 7 | Exact duplicate rows | Destructive-but-safe | Approve/auto, shown |
| 8 | Near-duplicate customer (typo in name/email, same phone) | Risk-aware merge | Needs approval |
| 9 | `total != quantity × unit_price` | Cross-column rule, derive | Needs approval (which side is wrong?) |
| 10 | `ship_date < order_date` | Cross-column violation, can't safely auto-fix | Flag; refuse auto |
| 11 | `quantity = 340` where typical is 1–5 | Outlier, plausible typo | Needs approval |
| 12 | A **legitimately large** order that is a statistical outlier but satisfies all rules | **Doesn't corrupt valid data** | Detected, diagnosed as plausible, **preserved** |
| 13 | Whitespace/case inconsistencies, invalid emails | Basic hygiene | Auto where lossless |
| 14 | (P1) Orders with `customer_id` not in a second `customers.csv` | FK integrity | Flag |

Don't include more than this; each row exists to make a point.

### 15.2 Script (timings sum to ~3:00)

| Time | Action | Say |
|---|---|---|
| 0:00–0:20 | Slide-free. Show raw CSV in a viewer for 5 seconds | "Real datasets arrive broken in different ways at once. Tools either find problems or apply fixes on trust. DataFix treats every fix as a proposal that must pass a safety check." |
| 0:20–0:40 | Upload on hosted URL; issues table appears | "It found N issues across six categories, including placeholder nulls that `isnull` misses." |
| 0:40–1:10 | Open one issue: diagnosis + evidence. Mention AI is optional | "Diagnosis is evidence from the data. The LLM only explains and chooses between hypotheses we generated; it can't write values." |
| 1:10–1:50 | **Signature moment:** auto-applied card, then a needs-approval card with preview diff and invariants; approve | "Before anything is applied we simulate it on a copy: cells changed, aggregate drift, integrity rules. Confidence is measured by backtesting, not asserted." |
| 1:50–2:15 | **Refused card** (ambiguous dates or unsupported imputation) and **preserved outlier** | "This is the repair we refuse. This large order is statistically unusual but valid; we leave it." |
| 2:15–2:40 | Verify: issues before/after, damage = 0, replay hash ✓, optionally benchmark scorecard | "We re-ran detection, replayed the log from the untouched original and got an identical file. On our injected-error benchmark: X precision, Y recall, Z abstentions, 0 valid cells damaged." |
| 2:40–3:00 | Export three files; show modification log row | "Cleaned data, quality report, cell-level log. Every change has who, why, evidence, confidence." |

Rehearse three times. Have the dataset pre-uploaded in a second tab as backup. Record a 90-second video of the same flow.

---

## 16. Potential judge questions and answers

**Q1. What is unique about DataFix?**
We don't claim any single feature is new. Audit logs, undo and confidence scores exist elsewhere. What we enforce is a contract: simulate before applying, check integrity invariants, route by measured confidence, refuse when evidence is insufficient, then verify by re-detection and replay. Let us show a refused repair.

**Q2. How is this different from OpenRefine or Power Query?**
Both are strong interactive tools. OpenRefine gives faceting, clustering, reconciliation and replayable undo history; Power Query gives column quality/distribution profiling and transformation steps. In both, the person decides and judges the safety of each fix. DataFix adds automated risk classification and a pre-apply impact simulation, and it can decline a change. They are better than us at breadth, extensibility and scale; we're a focused repair-safety engine.

**Q3. Why use an LLM at all?**
For two things rules do poorly: explaining diagnoses in plain language and disambiguating semantic cases from a closed candidate set. Everything else is deterministic. The system runs with the LLM disabled and says so.

**Q4. How do you prevent the AI from corrupting valid data?**
The LLM never writes values. Repairs are typed operations executed by our code. Each is simulated; an invariant checks that previously-valid cells are untouched unless the operation targets them. We report the count of valid cells changed (target zero for auto-applied repairs) and show a legitimate outlier being preserved.

**Q5. How do you measure confidence?**
Per repair class from evidence: parse round-trip and unambiguity for formats; support among unambiguous rows for ambiguous formats; frequency dominance and similarity for category merges; for imputation, backtesting: mask known values, predict them with the same method, report a conservative accuracy bound. It is a proxy for the missing cells, and we state when there's too little evidence to estimate it.

**Q6. How do you preserve relationships?**
Within a table: key uniqueness, functional dependencies (e.g., pincode → city), cross-column rules and dtypes are invariants checked on every simulation. [If built: foreign-key integrity against a second table.] Anything that would break one is refused.

**Q7. What happens when the AI is uncertain?**
It doesn't decide. The pipeline treats low confidence as a first-class outcome: the item is routed to approval or refused with an explanation, and the cell is left unchanged.

**Q8. How do you know the repair actually worked?**
Three ways: re-running detection on the output (issues resolved vs introduced), replaying the operation log from the original and comparing hashes, and on our benchmark dataset comparing against the known clean ground truth. The benchmark errors are synthetic and ours, so treat it as a regression test, not a general accuracy claim.

**Q9. How is it scalable?**
Operations are vectorized pandas and detection is column-wise. We've measured [N rows in T seconds] on a free-tier host and cap uploads accordingly. The domain layer has no I/O so it can move to chunked, DuckDB or Polars backends; we haven't built that.

**Q10. What happens when the API is unavailable?**
`LLM_ENABLED=false` or a failed call falls back to rule-based explanations with a visible badge. Responses are cached by input hash. No repair depends on the LLM.

**Q11 (likely). Isn't a quality score just a number you made up?**
We show per-dimension counts (completeness, validity, uniqueness, consistency) before and after, plus unresolved and abstained items. The blended score, if shown, uses disclosed weights and never hides what we left unrepaired.

**Q12 (likely). Why not just use Great Expectations?**
GX validates and documents; it doesn't repair. It could be a validation layer, and we borrow its idea of declarative checks, but our gate needs invariants aware of each proposed change.

---

## 17. Technical risks and mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Integration slip between frontend and backend | High | High | Contract-first, OpenAPI types, hello-world deploys at hour 1, hard checkpoints |
| Groq quota/latency (reported ~8K tokens/min, ~200K/day on free tier, verify) | Med | Med | LLM optional, cache, call cap, fallback chain, templates |
| Qwen model not available or renamed | Med | Low | `LLM_MODEL` env, list models at startup, fallback chain |
| Render cold start / memory limit during demo | High | High | Pre-warm, dataset caps, local fallback, recorded video |
| Supabase project paused | Low-Med | High | Check day before and morning of |
| Backtesting takes longer than planned | Med | Med | Fall back to rule-support confidence; imputation refused when evidence is insufficient. Don't fake it |
| Scope creep (the main one) | **High** | High | P0/P1 list is law; feature freeze at hour 18 |
| Overfitting thresholds/demo dataset | Med | Med | Separate tuning seed; state synthetic nature |
| "Confidence" challenged as arbitrary | Med | High | Document formulas in `docs/`; each component visible in the UI |
| Event-sourcing replay bugs | Med | Med | Determinism tests from hour 6; sort/seed explicitly; avoid non-deterministic ops |
| Security: uploaded file abuse, formula injection in exports | Low-Med | Med | Size/type checks, no macros, export sanitization; test cases in §13 |
| PII sent to a third-party LLM | Med | Med | Send summaries and few distinct values only; mask emails/phones in prompts; state in LIMITATIONS |
| Dependency on a dataset you built (possible "toy" perception) | Med | Med | Also test on one public messy CSV (any open dataset with real inconsistency) and show it works without hand-tuning; don't claim results you didn't measure |
| Team fatigue past hour 16 | High | High | Fixed freeze; sleep shifts if rules allow; one person owns the demo flow |

---

## 18. Final recommendations

**Build (in order of value per hour)**

1. Hosted skeleton on hour 1, OpenAPI contract, CI. *(S, must)*
2. Deterministic detect → diagnose → typed repair ops over the 13 injected error classes. *(L, must)*
3. Simulator + invariants + gate with visible decisions. *(M-L, signature, must)*
4. Operation log + replay + verify + export (three artifacts). *(M, must)*
5. Backtested confidence + abstention. *(M, P1: build, degrade gracefully)*
6. Ground-truth benchmark and scorecard. *(M, P1: build)*
7. Thin LLM layer with strict schemas and kill-switch. *(S-M, P1)*
8. README, ARCHITECTURE, DECISIONS, LIMITATIONS, tests in CI. *(M, must; assign to the third member)*

**Do not build**

Autonomous agent loops, chat interface, multi-format ingestion beyond CSV/XLSX, user accounts, learned repair models, microservices/queues, anything you can't test by hour 17.

**Decisions I'd force this hour**

- Confirm the PS PDF's mandatory list against §2.
- Decide the single demo dataset and write its error manifest first; everything is tested against it.
- Agree the gate thresholds and invariant list on paper before coding.
- Run the §10.1 audit on the repo and fix any leaked secret before anything else.
- Verify Groq limits and the available Qwen model name in your console.

**One thing to challenge in your own thinking:** you asked for a feature that sounds impressive and also for reliability. These conflict. The impressive-sounding option (autonomous AI agent) is the less reliable one; the impressive-looking *and* reliable one is a system that visibly refuses to do something it can't justify. Build that.

---

## Appendix A — Sources used

- OpenRefine, main features (faceting, clustering, reconciliation, infinite undo/redo, privacy): https://openrefine.org
- OpenRefine provenance via operation histories and JSON recipes (academic paper): https://www.ideals.illinois.edu/items/110369/bitstreams/361341/data.pdf
- Microsoft Learn, Power Query data profiling tools (column quality, distribution, profile; default profiling over first 1,000 rows): https://learn.microsoft.com/power-query/data-profiling-tools
- Great Expectations: Expectations, Checkpoints, Data Docs, actions on results, not a versioning tool (project README mirrors; canonical docs at https://docs.greatexpectations.io/). ExpectAI (Feb 2025) claim comes from a secondary source (blog.pebblous.ai), so verify before citing.
- HoloClean (Rekatsinas, Chu, Ilyas, Ré): https://arxiv.org/abs/1702.00820. Per-repair marginal probabilities, recall bounded by error detection, reported ~90% precision / >76% recall on its benchmarks.
- Groq free-tier limits and Qwen/gpt-oss availability: secondary aggregators (benchlm.ai, pricepertoken.com, cloudzero.com, voiceflow.com), citing https://console.groq.com/docs/rate-limits. Limits are per-organization, vary by model, and change. **Check your own console.**

## Appendix B — Claims I made from general knowledge (verify before relying)

- Render free disks being ephemeral (the sleep, memory and CPU figures were checked in Nov 2026; the disk point was not).
- Supabase pause-after-inactivity and size limits were checked in Nov 2026 against its pricing page and third-party summaries.
- Power Query records transformations as applied steps.
- Capabilities of ydata-profiling, dedupe-style libraries, Cleanlab, Soda, Trifacta/Alteryx, Informatica, Ataccama and Power Query Copilot were not examined.

## Appendix C — Free-tier figures checked on 19 Nov 2026

- Groq free plan (sample limits for a Qwen 27B-class model, per organisation): about 30 requests/min, 1,000 requests/day, 8,000 tokens/min, 200,000 tokens/day. Source: third-party reading of https://console.groq.com/docs/rate-limits (benchlm.ai, pricepertoken.com). The 8,000 tokens/min figure is the binding constraint: send column-level facts and a handful of sample values, never raw rows. Confirm the exact model id and your limits in your own console.
- Render free web service: https://render.com/docs (spin-down after 15 minutes, about 1 minute to wake, 512 MB / 0.1 CPU, 750 instance-hours per month).
- Supabase free plan: https://supabase.com/pricing (500 MB database, 1 GB storage, 50 MB max file, pause after 1 week idle, 2 active projects).
