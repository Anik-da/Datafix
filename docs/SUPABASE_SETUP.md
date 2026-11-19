# Supabase setup and integration status

The backend has a Supabase Postgres/Storage adapter and a schema script at `backend/docs/supabase_schema.sql`. Backend environment variables are `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (preferred) or the legacy `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, and `DATAFIX_STORAGE_BACKEND=supabase`. These credentials must never be added to frontend variables.

Before switching the backend from local SQLite:

1. Rotate the Supabase secret key that was shared in this chat, then place its replacement in the ignored `backend/.env` or the hosting secret store.
2. Execute `backend/docs/supabase_schema.sql` in the target project's SQL editor.
3. Create the private bucket named by `SUPABASE_STORAGE_BUCKET` (default `datafix`).
4. Start the backend in Supabase mode and run upload → analysis → review → apply → verify → exports → restart → retrieve. Compare original/artifact hashes.

Existing evidence recorded an authenticated REST response `404 PGRST205` because `public.datafix_runs` was missing from the remote schema cache. The current task did not retry with the exposed key or write user data to the remote project. The adapter's mocked tests are not live proof. Therefore database/storage persistence remains **blocked pending key rotation, schema/bucket provisioning, and a successful full lifecycle test**.
