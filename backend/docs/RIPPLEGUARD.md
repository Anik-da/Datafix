# RippleGuard

RippleGuard is the impact calculation inside `app.lifecycle.simulate`, not a second simulation path. Each typed proposal is applied to a deep copy, detectors and invariants are re-evaluated, then `RippleImpact` is attached to that exact proposal simulation before the gate decision is returned.

The impact contains changed row references/cells/columns, measured before/after metrics for directly changed columns, explicit supported dependency metrics, resolved/remaining/introduced issue signatures, invariant results, deterministic risk level (`low`, `moderate`, `high`, `unknown`) and limitations. Risk is supplementary; the Safety Gate remains authoritative.

Supported dependencies are the rules implemented in `lifecycle.py` (including configured conventional arithmetic and postcode/customer-key relationships). No correlation-based causal relationship is inferred. Proposal edits call the same `simulate` function again, so impact and gate are recalculated for the new version.
