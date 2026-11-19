# Deployment readiness

## Frontend / Vercel

- Vite production build passed after the final port/size adjustment. Vite reported a non-blocking large-chunk advisory (533 kB minified).
- `VITE_API_BASE_URL` is the only frontend API origin setting. Its development fallback now matches the documented backend `127.0.0.1:8000`.
- `frontend/vercel.json` rewrites SPA routes to `index.html`.
- Set the actual Render service URL in Vercel; none is known yet.

## Backend / Render

- `render.yaml` binds Uvicorn to `0.0.0.0:$PORT` and checks `/health`.
- CORS origins are environment-configurable.
- Do not use ephemeral local disk for deployed runs. Supabase mode must not be enabled until its schema/bucket are ready and a full persistence lifecycle passes.

## Blockers

- Supabase remote schema is not confirmed installed (`PGRST205` in recorded probe); lifecycle persistence is not live-tested.
- The Supabase secret shared in chat must be rotated.
- No Vercel/Render deployment was performed; no public URL is claimed.
- Full graphical browser validation was unavailable in this session; no complete visual click-through is claimed.
