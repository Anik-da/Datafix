# Architecture

DataFix is a modular FastAPI monolith. CSV ingestion, profiling, deterministic issue detection, diagnosis and proposal generation live in `backend/app/services.py`; typed execution, proposal simulation, invariant checks, replay and reporting live in `backend/app/lifecycle.py`. `backend/app/schemas.py` defines request/response models. API orchestration and error envelopes are in `backend/app/main.py`.

The upload bytes are saved immutably with SHA-256. A separate working representation is updated only after an atomic, staged plan passes checks. `backend/app/storage.py` supplies a local SQLite adapter and an optional Supabase Postgres/Storage adapter. No client-side Supabase credential is needed for the API workflow.

The optional Groq explanation client is constrained to a deterministic hypothesis ID and short explanation. The core engine runs with `LLM_ENABLED=false`; an LLM cannot provide repair values or execute code.

## Safety simulation

For each typed proposal, the backend executes against a copy, computes a bounded cell diff and aggregate changes, and reports these invariant checks: schema/types, row-count policy, candidate-key preservation, originally valid-cell preservation, explicit cross-column rules, supported functional dependencies, and numeric aggregate drift. The current gate uses risk-class drift ceilings (format 5%, value substitution 5%, imputation 1%, destructive 10%) as conservative relative sum/mean limits. These are policy thresholds, not learned confidence estimates. Any failed invariant refuses the proposal. Apply stages the full selected batch on a copy and rechecks the batch before persistence.

Functional dependencies currently checked are conventional single-table rules when matching columns exist: postal-code-to-city and customer-id-to-name/email/phone. They are not user-configurable declarations. Cross-column rules are the recognized quantity × unit_price = total and ship_date >= order_date rules.

## Storage boundaries

Local runs persist in SQLite under `DATAFIX_STORAGE_DIR`. Supabase requests use backend-only credentials and the private Storage bucket configured by environment. Live Supabase has not been authenticated in this workspace; adapter behavior is covered by mocked HTTP tests.
