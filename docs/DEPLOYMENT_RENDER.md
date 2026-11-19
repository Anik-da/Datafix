# Deploy the DataFix backend to Render

The root `render.yaml` defines a Python web service. Configure the repository root as the service root and use its build/start/health settings. Render supplies `$PORT`; Uvicorn binds to `0.0.0.0` and `/health` is the health check.

Before selecting `DATAFIX_STORAGE_BACKEND=supabase`, apply `backend/docs/supabase_schema.sql`, create a private Storage bucket, and add `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `SUPABASE_STORAGE_BUCKET` as Render secret/environment variables. The supplied project has not passed a full Supabase lifecycle persistence test, so deploying with Supabase mode before the schema is installed can leave uploads unavailable. Never use ephemeral disk as persistent run storage.

Set `DATAFIX_CORS_ORIGINS` to exact frontend production/preview origins. Leave `LLM_ENABLED=false` unless the backend Groq key and account-supported model are deliberately configured. Do not set backend secrets in Vercel.

No Render service has been deployed or tested from this workspace.
