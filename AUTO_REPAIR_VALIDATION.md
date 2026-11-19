# Auto-repair validation

## Pipeline behavior

The backend analyzes a stored working copy, emits typed proposals, simulates each against the current data, checks invariants through the Safety Gate, records user decisions, applies eligible operations atomically, and verifies the resulting dataset by replay. The uploaded original bytes are stored separately and are not the mutation target.

## Observed synthetic run

Existing HTTP acceptance evidence for the canonical fixture reports:

- Upload: HTTP 201; 1,001 rows × 10 columns. The 1,001st record is a planted duplicate.
- Analysis: HTTP 200; 12 findings, 6 proposals (2 auto-apply, 3 need approval, 1 refused).
- Apply: HTTP 200; 4 operations: date normalization (automatic), category mapping, placeholder-to-null, and exact duplicate removal (the latter three user-approved).
- Verification: HTTP 200; findings 12 → 8, four resolved, zero introduced, zero previously-valid cells damaged; replay matched.
- Cleaned CSV: HTTP 200; 1,000 rows × 10 columns and uniform row widths.

The original SHA-256 recorded by upload was `3d00c55b6f5540a1b97a318c73bc4acd87a46902f28a91408cb1ff85845b6fff`. The acceptance report records that it matched the fixture bytes and that the canonical fixture remained unchanged.

## Safety classification

Whitespace/case and unambiguous formatting corrections may auto-apply when the simulation and invariants pass. Category mapping, placeholder substitutions, and destructive duplicate removal require approval in the observed run. Ambiguous or refused proposals are not made applicable by user approval. The existing evidence does not establish that every valid domain-specific value is always preserved; the measured fixture result is zero valid-cell damage for this run only.

Evidence: `backend/test-evidence/END_TO_END_ACCEPTANCE_RESULTS.md`, `backend/test-evidence/api-responses/final_audit_1000_*.json`, and `backend/test-evidence/exports/final_audit_1000_*`.
