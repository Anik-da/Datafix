# Supabase configuration

The maintained setup and live-integration status are in [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md). This file is a root-level entrypoint for repository readers.

Use local SQLite for development by default. Supabase requires a rotated backend-only secret key, the checked-in SQL schema, and a private Storage bucket before the API is switched to Supabase mode. The previous remote probe returned `404/PGRST205` for the missing table, so live lifecycle persistence is not currently verified. Do not put a secret/service-role key in frontend environment variables or commit any key.
