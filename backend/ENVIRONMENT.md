# Backend environment configuration

Copy `backend/.env.example` to `backend/.env`. The application reads this file
without replacing variables already set in the process environment. Never commit
`backend/.env`; `.env` is Git-ignored. Keep secrets out of logs, API payloads, and
issue reports.

## Local deterministic mode

The defaults use local SQLite and need no external credentials:

```text
DATAFIX_STORAGE_BACKEND=local
LLM_ENABLED=false
```

## Optional Supabase storage

The backend adapter requires `SUPABASE_URL`, a backend-only secret/service-role
key, and an existing private `SUPABASE_STORAGE_BUCKET` (create it in Supabase
Storage; the default bucket name is `datafix`). Prefer the current
`SUPABASE_SECRET_KEY`; `SUPABASE_SERVICE_ROLE_KEY` is supported for existing
projects. Set the backend storage mode only after running
`backend/docs/supabase_schema.sql` in the project's SQL editor:

```text
DATAFIX_STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SECRET_KEY=your-backend-only-secret-key
SUPABASE_STORAGE_BUCKET=datafix
```

The Supabase publishable/anon key belongs in a client application, if one needs
it. It is not a backend service credential, and this backend never sends it to
Supabase or exposes a service-role key to clients. Missing service-role
credentials are intentionally not replaced with fabricated values. Supabase
mode is not considered live until an authenticated request succeeds.

The schema creates the private `datafix_artifacts` table. Export endpoints store
content-addressed objects and metadata there; the bucket remains private and
all access is mediated by the backend. Apply the SQL before setting
`DATAFIX_STORAGE_BACKEND=supabase`; the backend does not fall back to SQLite if
the hosted schema or storage service fails.

After the migration, verify `public` is enabled under the project's **Integrations
> Data API > Exposed schemas** setting. Current Supabase projects may not expose
new public tables automatically. Keep RLS enabled and preserve the migration's
service-role-only table grants; do not grant `anon` or `authenticated` access.
The backend's new `sb_secret_...` key is sent only in the `apikey` header, as
required for current Supabase secret keys.

## Optional Groq explanations

Deterministic analysis works when `LLM_ENABLED=false` and does not make network
requests. To enable optional explanations, configure a real Groq API key in the
backend environment and a model supported by the account:

```text
LLM_ENABLED=true
GROQ_API_KEY=your-groq-api-key
LLM_MODEL=your-groq-model-id
```

The project/model name in `.env.example` is a configurable hint only; it does not
verify that the model is available to an account. Do not enable this integration
until a valid credential is configured. Deterministic explanation fallbacks are
the expected behavior when it is disabled or unavailable.

## Limits and browser access

Upload bytes, row count, column count, cell length, and CORS origins are
configurable through the `DATAFIX_*` values in `.env.example`. Keep upload limits
aligned with the server or hosting platform's request-body limit.

## Simulation aggregate drift

Risk-class relative numeric aggregate limits are configurable. Defaults are 5%
for format-only, 5% for value substitutions, 1% for imputation, and 10% for
destructive operations. A simulation fails its gate if any numeric sum or mean
drifts beyond the applicable ceiling. These are conservative policy thresholds,
not calibrated confidence estimates.

## Create the synthetic demo data

From repository root:

```powershell
python samples/generate_dataset.py
python samples/benchmark.py
```

The benchmark runs the backend API in an isolated temporary SQLite store and
prints detection and repair precision/recall, abstentions, invariant status,
valid-cell damage, replay status, dataset dimensions and runtime. Results apply
only to this generated sample.

See `docs/BACKEND_AUDIT.md` for the initial checklist and unavailable source
files, and `backend/RENDER.md` for deployment preparation.

