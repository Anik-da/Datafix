# Advanced backend feature status

| Feature | Status | Existing pipeline integration | Remaining limits |
|---|---|---|---|
| RippleGuard | IMPLEMENTED_AND_TESTED | `simulate` stages the typed proposal, computes direct and evidence-backed indirect metrics, issue signatures, invariant results and a deterministic risk level before the Safety Gate returns. | Dependency checks cover only explicitly coded rules; statistical correlations are intentionally excluded. |
| Trust Passport | IMPLEMENTED_AND_TESTED | Export is assembled from stored run, proposal revisions, decisions, operations, verification, unresolved issues and exact artifact hashes. Values in proposal summaries are redacted. | It is an integrity record, not a cryptographic signature or universal correctness guarantee. |
| Error Pattern Fingerprinting | IMPLEMENTED_AND_TESTED | Every issue returned by analysis receives a deterministic fingerprint based on normalized non-sensitive issue metadata. | Fingerprints do not transfer decisions or safety status between runs. |
| Uncertainty Heatmap | IMPLEMENTED_AND_TESTED | `GET /api/v1/runs/{run_id}/uncertainty` calculates current issue and decision state with bounded record pagination. | Confidence remains null unless a defensible estimator exists. Internal ingestion columns are hidden. |
| Manual repair editing | IMPLEMENTED_AND_TESTED | Proposal edit validates row/value/revision, records the prior revision, re-simulates, recalculates impact and gate, and requires fresh approval. | Applied or refused proposals cannot be edited to bypass safety. |

The five services are integrated into the existing single FastAPI/Pandas pipeline. No separate simulation engine or frontend implementation was added for these features. The currently added structural CSV recovery is represented in the same issue/proposal/simulation/decision/apply/verify path.

See the feature notes in this directory and `../test-evidence/FEATURE_ACCEPTANCE_RESULTS.md` for test scope and verified outputs.
