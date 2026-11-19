# DataFix Trust Passport

`GET /api/v1/runs/{run_id}/export/passport` builds a Pydantic-validated certificate from the stored run and current lifecycle records. It includes a stable passport ID, source SHA-256 and schema, profile and issue summaries, proposal versions with redacted parameter summaries, simulations and gates, decision histories, operation history, verification/replay state, unresolved issues, quality dimensions, and hashes of the cleaned CSV, report, log and recipe.

`passport_sha256` hashes canonical JSON with that field omitted. Artifact hashes are computed from the bytes returned by the corresponding export implementation. Raw proposed cell values are not duplicated into the passport summary. The passport is an integrity summary; it is not cryptographically signed and does not establish universal correctness.
