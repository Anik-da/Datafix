# Render deployment preparation

Create a Render Web Service from the repository root with runtime `Python`, build command `python -m pip install -e ./backend`, start command `python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`, and health check path `/health`.

Set `DATAFIX_STORAGE_BACKEND=supabase` for hosted persistence, provide `SUPABASE_URL`, a backend-only `SUPABASE_SECRET_KEY` (or legacy service-role key), configure the private `SUPABASE_STORAGE_BUCKET`, and apply `backend/docs/supabase_schema.sql`. For development/local file persistence, use `DATAFIX_STORAGE_BACKEND=local` and a durable `DATAFIX_STORAGE_DIR`; ephemeral host disks are not suitable for persistent local storage.

Set `DATAFIX_CORS_ORIGINS` to comma-separated exact origins, including the deployed Vercel origin and any preview origin that should be permitted. Do not use `*` with credentials. Keep `LLM_ENABLED=false` unless a Groq key and model are intentionally configured. Never put backend secrets in frontend environment variables.

This is deployment configuration guidance only. No Render service has been deployed or authenticated in this workspace.
