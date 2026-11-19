# Supabase setup and live status

## Probe result

On 2026-11-20 the backend configuration loader found a project URL and a backend key without printing either value. `DATAFIX_STORAGE_BACKEND` resolves to `local`. A minimal authenticated request to `GET /rest/v1/datafix_runs?select=id&limit=0` returned HTTP 404 with PostgREST code `PGRST205`: `public.datafix_runs` is not present in the schema cache.

This is not a successful persistence test. No lifecycle run or Storage object was written to Supabase. The application currently persists locally.

## Configure the project

1. In the Supabase Dashboard, open the DataFix project and copy the Project URL from **Project Settings → API** (or the project's API settings page).
2. In **Project Settings → API Keys**, create/copy a backend-only **Secret key**. Do not use a publishable key for backend persistence. If the project only has legacy keys, use the service-role key as a temporary legacy alternative.
3. Open `backend/.env` locally. Set the values in this format; do not paste secrets into source code or commit the file:

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=<backend-only-secret-key>
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=datafix
DATAFIX_STORAGE_BACKEND=supabase
```

4. In the Supabase SQL Editor, execute `backend/docs/supabase_schema.sql`.
5. Create a **private** Storage bucket named `datafix` in Storage settings.
6. Restart the backend. Startup should fail rather than silently fall back if Supabase is selected but its credentials are incomplete.
7. Re-run upload → analyze → edit/review → apply → verify → export, restart the backend, then retrieve the same run and artifacts and compare bytes/hashes.

The supplied schema enables RLS and creates no anon/authenticated data policies; backend service credentials must remain server-only. Rotate any secret key that was pasted into chat before using this configuration.

## Current status

- Credentials locally present: yes (presence only; values suppressed).
- Live authenticated REST request: reached PostgREST, returned `PGRST205` because the table is missing from schema cache.
- Database lifecycle persistence: not verified.
- Storage lifecycle persistence: not tested.
- Restart persistence: not tested against Supabase.
- Active backend storage mode: local.
