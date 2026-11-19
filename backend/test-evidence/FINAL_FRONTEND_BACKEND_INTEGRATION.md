# DataFix frontend/backend integration smoke run

Date: 2026-11-20 (local time)

## Local app links

- Frontend: http://127.0.0.1:5174
- FastAPI: http://127.0.0.1:8014
- Swagger UI: http://127.0.0.1:8014/docs
- Health: http://127.0.0.1:8014/health

The frontend API base is configured in the ignored `frontend/.env` as `http://127.0.0.1:8014`. LLM is disabled for deterministic testing.

## Real HTTP workflow

Input: `C:\Users\anikd\Downloads\messy_customer_data.csv` (the original fixture was not modified).

| Stage | Result |
|---|---|
| Upload `POST /api/v1/runs` | HTTP 200; run `fcab2137-6515-4df1-ba48-b2532ea8f5a3`; SHA-256 `18f140931d9fdd80f77962b6e0751596ba1bca6696148b7c00d8e9813bd63964`; one structural warning |
| Analysis `POST /analyze` | HTTP 200; 25 rows, 9 columns, 13 issues, 6 proposals |
| Pattern fingerprints | 13/13 detected issues carried a fingerprint |
| RippleGuard simulation | 6/6 proposals included impact simulation and risk assessment |
| Uncertainty `GET /uncertainty` | HTTP 200; 25 records assessed |
| Manual revision | HTTP 200; proposal `prp_1795b053bc3f` revised and returned `edited_pending_reapproval`; the edited proposal was re-simulated and gated again |
| Approval | HTTP 200; revised proposal approved |
| Rejection | HTTP 200; proposal `prp_e3e95a0af1bc` rejected |
| Refused proposal override attempt | HTTP 409, correctly refused |
| Apply | HTTP 200; `applied`; 2 operations applied atomically |
| Operation history | HTTP 200; 2 operations returned |
| Verify/replay | HTTP 200; replay match `true`; issues 13 → 12; Passport replay hash matched verification replay hash |
| Original preservation | Local original SHA-256 matched the uploaded SHA-256 |
| Trust Passport | HTTP 200; verification status `verified`; cleaned SHA-256 matched downloaded cleaned CSV bytes |

Export responses all returned HTTP 200 and were parsed/validated in memory: cleaned CSV (2,193 bytes; parsed successfully), quality report JSON (143,559 bytes), modification log JSON (1,884 bytes), recipe JSON (893 bytes), and Passport JSON (175,849 bytes). Export bytes were not written to the repository; use the UI download controls to save them locally.

## Verification commands

```powershell
cd C:\Users\anikd\OneDrive\Documents\ChatGPT\Datafix\frontend
npx openapi-typescript ../docs/openapi.json -o src/lib/generated-types.ts
npm run build

cd ..\backend
py -m pytest tests -q
```

Results: OpenAPI TypeScript generation succeeded; frontend production build succeeded; backend suite **45 passed**. One initial test invocation using a nonexistent `backend/.venv/Scripts/python.exe` failed because that virtual environment is absent; rerunning with the installed Python launcher (`py -m pytest tests -q`) succeeded.

CORS preflight from `http://127.0.0.1:5174` to the API returned HTTP 200 with the matching allowed origin. Frontend document and backend Swagger returned HTTP 200.

## Implementation notes

The friend-provided visual source was retained. The live UI now uses the actual run upload/analyze response, backend decisions/apply/verify, operation history, uncertainty, fingerprints, proposal revision endpoint, and backend-generated exports/Passport. The walkthrough/demo fixture remains a separate explicitly marked fixture mode. Supabase and Groq are not required for this local workflow; LLM is disabled.

The manual revision smoke call resubmitted the backend's suggested sample value to verify the revision/re-simulation/re-approval path. The UI permits a reviewer to enter a different value, which the backend validates before simulation; that distinct-value path was not used in this smoke run.
