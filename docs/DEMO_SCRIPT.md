# Three-minute backend demo

1. Start the API with `LLM_ENABLED=false`; confirm `GET /health` returns `status: ok`.
2. Upload `samples/orders_dirty.csv` as multipart field `file`. Save the returned run ID and verify row count, column count and SHA-256.
3. Call analyze. Show measured profile and evidence for missing/placeholder, duplicate, invalid-format, inconsistent, anomaly and relationship issue categories. Point out the ambiguous date and legitimate high quantity outlier.
4. Inspect proposal simulations and seven invariants. Show auto-apply and needs-approval lanes, then the explicitly refused ambiguous-date proposal and its empty change set.
5. Approve eligible review proposals and call apply. Confirm atomic status and operation count.
6. Retrieve operations, call verify, and show replay hash match plus before/after issue counts and valid-cell damage.
7. Download cleaned CSV, report JSON, log JSON and recipe JSON. Verify content types and compare output to `samples/orders_clean_truth.csv` using `python samples/benchmark.py`.

The benchmark is a synthetic regression demonstration, not an accuracy claim for arbitrary customer data.
