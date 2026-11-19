# DataFix synthetic e-commerce sample

Generated with synthetic data only. Fixed demo seed `20261119`; 1,000 clean orders, 1,001 dirty rows after one exact duplicate, 14 columns. The manifest records row/cell references, original and injected values, categories, expected handling, and preservation cases. Names and emails are fictional; emails use `example.test`.

Run `python samples/generate_dataset.py` from repository root to reproduce the dirty CSV, clean truth and manifest. The 1,000-row detector tuning/regression fixture uses a separate seed under `backend/tests/fixtures/`.

Run `python samples/benchmark.py` to execute upload, analyze, decisions, atomic apply, history, verify and all four exports with `LLM_ENABLED=false`, then compare results to clean truth. The scorecard is stored in `benchmark_results.json`.

Run `python samples/benchmark_limits.py` to measure the configured row/column boundary cases. The result is stored in `benchmark_limits_results.json`.

Latest Windows lifecycle run (Python 3.14, local TestClient/SQLite): 22.33 seconds and 129.00 MiB peak process working set; detection precision 93.75%, detection recall 100%; exact-truth repair precision 66.67%, actionable-case repair recall 100%; previously-valid-cell damage 0; replay matched. Placeholder-to-null operations count as cell changes but do not restore the original clean-truth values, lowering exact-truth repair precision. The separate configured-limit run analyzed 50,000 × 40 columns at 4,250,157 bytes in 15.71 seconds, peaking at 233.30 MiB; a 60-column, one-row upload also succeeded. These are local Windows measurements, not Render performance or general accuracy claims. 50,000 rows × 60 populated columns exceeds the 5 MiB request cap, so the limits do not apply simultaneously.



