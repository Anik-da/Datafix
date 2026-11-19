# Deploy the DataFix frontend to Vercel

1. Import this repository and set the Vercel **Root Directory** to `frontend`.
2. Use the Vite build command `npm run build` and output directory `dist`.
3. Set `VITE_API_BASE_URL` to the actual deployed Render API origin (no trailing slash), for example `https://<your-render-service>.onrender.com`. Do not use a fabricated production URL.
4. Deploy only after the Render API `/health` endpoint is reachable and its CORS allowlist includes the exact Vercel origin.

`frontend/vercel.json` rewrites client-side routes to `index.html`. Only public API origins belong in Vercel variables; Supabase secret/service-role and Groq keys belong in the backend environment only.

No Vercel deployment has been created or tested from this workspace.
