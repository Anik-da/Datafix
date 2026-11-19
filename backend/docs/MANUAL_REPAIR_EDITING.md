# Human-in-the-Loop proposal editing

`POST /api/v1/runs/{run_id}/proposals/{proposal_id}/edit` validates the requested affected row, expected original value, proposal state, target type/range and reason. It stores the prior proposal in decision history, increments the proposal version, clears prior gate/simulation results, runs the deterministic simulation again, refreshes RippleGuard impact and Safety Gate, and requires reapproval for an edited proposal. Stale source values return HTTP 409. Refused and applied proposals cannot be edited to bypass policy.

Apply continues to use the common atomic staged plan; operation history records the applied proposal and its final typed edit. Undo/reapply remain available through the existing lifecycle routes.
