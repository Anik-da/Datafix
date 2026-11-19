# Supabase integration status

## Implemented

- A server-side Supabase Postgres/Storage adapter is present in `backend/app/storage.py`.
- SQL schema/functions are in `backend/docs/supabase_schema.sql`; RLS is enabled and no anonymous/authenticated access policies are granted.
- Backend configuration reads only backend environment variables. The service credential is not used by frontend code.
- The local backend remains usable with SQLite. Adapter behavior has mock-based tests.

## Not live-verified

The checked-in probe record reports that an authenticated read reached PostgREST but returned HTTP 404 `PGRST205` because `public.datafix_runs` was not available in the schema cache. The active storage mode is local. No successful remote create/retrieve, artifact upload/download, or restart-persistence lifecycle is established. Mock tests do not prove hosted persistence.

The secret supplied in chat is exposed and should be rotated. This pass did not use it to send or persist dataset data to Supabase. Before live verification: rotate the key, apply the schema, create the private `datafix` bucket, select Supabase backend mode, then exercise a complete synthetic lifecycle and verify run/artifact retrieval after a backend restart.

Setup steps: `docs/SUPABASE_SETUP.md` and `backend/ENVIRONMENT.md`.
