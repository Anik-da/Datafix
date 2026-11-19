# Engineering decisions

1. Keep a single FastAPI monolith and deterministic pandas-based engine.
2. CSV is the only upload type in this release; default caps are 5 MiB, 50,000 data rows, 60 columns and 100,000 characters per cell.
3. Original upload bytes are immutable; a separate working copy and ordered operation log represent repairs.
4. Simulation and gate decisions are part of analysis; there is no separate simulation API.
5. Repair values come only from allow-listed typed operations. Confidence remains null unless a defensible method is measured.
6. Ambiguous dates, unsupported mappings, unsound imputation and cross-column inconsistencies are preserved and flagged/refused.
7. Atomic apply uses staged changes and transaction-backed persistence. Replay starts from original bytes and re-executes the ordered active log.
8. Supabase is an optional backend adapter; the browser must never receive backend service/secret credentials. Groq is optional and disabled by default.
9. The currently implemented undo endpoint is a non-breaking extension that only reverts the newest active operation.
10. XLSX, OpenRouter, multiple-file joins, authentication and deployment are outside the implemented scope.
