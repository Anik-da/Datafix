# DataFix frontend

React, TypeScript and Vite client for the FastAPI DataFix backend.

## Local development

1. Start the backend from `backend/`:

   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. In `frontend/`, install dependencies and start Vite:

   ```powershell
   npm install
   Copy-Item .env.example .env
   npm run dev
   ```

3. Open `http://localhost:5173`.

Set `VITE_API_BASE_URL` to the FastAPI origin if it differs from the default
`http://127.0.0.1:8000`. Frontend calls use the generated contract in
`src/api/generated.ts`. No Supabase client is required for this API workflow.
