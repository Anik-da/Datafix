# Backend QA checklist

## Automated

- [ ] `cd backend; python -m pytest -q`
- [ ] `cd backend; python generate_openapi.py`
- [ ] From `frontend/`: regenerate API types with `npx --yes openapi-typescript ../docs/openapi.json --output src/api/generated.ts`.
- [ ] `python samples/generate_dataset.py` then `python samples/benchmark.py`.
- [ ] `python samples/benchmark_limits.py` to record current row/column cap memory and runtime on the local platform.
- [ ] Verify all four exports parse (CSV with pandas; JSON with `json.loads`).

## Manual local/API acceptance

- [ ] Start from a clean local storage directory with `LLM_ENABLED=false`.
- [ ] Health reports API availability and configured request limits.
- [ ] Upload canonical CSV; compare original SHA-256 with the response and confirm exact byte preservation in local storage.
- [ ] Analyze response has measured profile, evidence-backed issues, simulation and gate per proposal.
- [ ] Approve/reject needs-approval proposals; refused proposal cannot be decided.
- [ ] Atomic apply either persists the complete batch or none of it.
- [ ] History survives a process restart when using the same local storage directory.
- [ ] Verification replay hash matches current working data.
- [ ] All exports download and parse; test formula injection values.
- [ ] Test CORS using the configured frontend origin.
- [ ] Before hosted release, verify Render health check, CORS allowlist, persistent/external storage, memory, cold-start and live external credentials.

Do not mark hosted checks complete based on a local test.
