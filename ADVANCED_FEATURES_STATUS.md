# Advanced features status

| Feature | Status | Evidence / limit |
|---|---|---|
| RippleGuard | Implemented and tested | Proposal simulation measures direct changes, supported dependency effects, invariants and deterministic risk. It does not infer arbitrary statistical dependencies. |
| Trust Passport | Implemented and tested | Generated from stored run, decisions, operations, verification and exported artifact hashes. It is an integrity record, not a digital signature. |
| Error Pattern Fingerprinting | Implemented and tested | Analysis attaches deterministic value-free patterns to actual issues; signatures do not carry approvals across runs. |
| Uncertainty Heatmap | Implemented and tested | API derives issue/decision counts from the analyzed run; unsupported confidence values remain null. |
| Manual repair editing | Implemented and tested | Validates the edit, records a revision, re-simulates and requires a fresh approval; refused proposals cannot be edited to bypass the gate. |
| Smart schema discovery | Partially implemented | Deterministic type/missingness/uniqueness profiling exists. Complete semantic roles, constraint discovery and a confirmation workflow are not verified. |
| Relationship Guardian | Partially implemented | Explicit same-dataset rules (e.g. arithmetic/date ordering) are detected. General multi-table FK/orphan discovery and interactive relationship graph are not verified. |
| Context-aware anomalies | Partially implemented | IQR and supported explicit rules are reported as evidence; statistical outliers are not auto-corrected. Broad contextual/domain-configured analysis is not implemented. |
| Recipe reuse/import | Not implemented | Recipe export exists. Import, schema compatibility review, and fresh simulation for a different dataset are unavailable. |
| Visualizations | Partially implemented | Overview, studio, proof, heatmap, pattern, relationship/anomaly panels and export screens exist. A full browser interaction/console audit could not be performed in this session. |

Existing backend automated tests: 48 passed with `LLM_ENABLED=false`. Existing recorded live HTTP evidence exercises the implemented pipeline features; it is not proof that the partial features above are complete.
