# Contributing to DataFix

## Before changing code

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md), and [`TESTING.md`](TESTING.md). Treat `docs/openapi.json` and the Pydantic models as the API contract. Do not add unimplemented features to documentation as if they were complete.

## Development setup

Use Python 3.11 or newer and Node.js/npm versions supported by the checked-in lockfile. Follow the fresh-clone steps in `README.md`. Keep API keys in ignored backend `.env` files or host secret stores; never paste them into code, fixtures, reports, or screenshots. Only public origins and publishable keys belong in frontend variables.

## Engineering conventions

- Keep parsing/export specific to the format adapters in `backend/app/ingestion/` and share the canonical analysis/lifecycle engine.
- Put request/response types in `backend/app/schemas.py`; preserve strict validation and regenerate OpenAPI/types after contract changes.
- Keep detectors deterministic and include evidence. Repair operations must remain allow-listed, typed and safe to replay.
- Do not call external LLMs in unit tests. Mock external services in integration tests; report live service tests separately.
- Preserve original upload bytes. Apply data changes only to the working representation and test atomic failure behavior.
- Use clear error envelopes; do not return stack traces or log cell contents/secrets.
- Add regression tests for bug fixes and expected behavior, not tests that only repeat implementation details.

## Checks before submitting

From `backend/`, run pytest, Ruff lint/format checks, and OpenAPI generation. From `frontend/`, run `npm run build` and dependency audit. MyPy is configured as an available diagnostic; current unresolved errors are tracked in `CODE_QUALITY_AUDIT.md` and must not be hidden with blanket ignores.

Review `git diff --check`, `git status`, and tracked files for credentials/private data before committing. Do not commit `.env`, local databases, uploads, generated runtime artifacts, or customer/student data.
