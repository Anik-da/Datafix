# Uncertainty Heatmap

`GET /api/v1/runs/{run_id}/uncertainty?offset=0&limit=100` computes column rates from current run data, current detector results and proposal/decision state. Record results include issue density, issue references and review/refusal/verification state. Pagination is bounded (`limit` 1–500). Confidence is `null` where no calibrated estimator exists. Structural parser bookkeeping columns are excluded from user-facing column metrics.
