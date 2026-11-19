# Limitations

- The official `1_2_3_4_merged.pdf` was not present in the workspace or supplied attachment during this assignment, so Problem Statement 01 could not be inspected. The local handoff Markdown files were available and reviewed. The referenced specifically named `DataFix_Three_MD_Handoff(1).zip` was also not present in the current workspace; repository copies under `handoff/` were used.
- No hosted Render deployment has been performed or tested. Render preparation is configuration/documentation only.
- Supabase has not been tested against live credentials and remains mock-tested. Groq was live-tested locally on 2026-11-19: the account model list included `qwen/qwen3.8-27b`, and a synthetic DataFix analysis received a validated constrained explanation. The initial Python default User-Agent triggered Cloudflare 1010; using a transparent `DataFix-Backend/0.1.0` User-Agent resolved that edge block. Groq remains optional and defaults to disabled in `.env.example`.
- Current functional-dependency rules are explicit conventional single-table pairs, not arbitrary user-declared constraints. No multi-file joins or foreign-key checks exist.
- The detector set is deterministic and intentionally conservative. Near-duplicate detection proposes candidates for review only; it does not merge them. Statistical outliers are flagged and preserved.
- Confidence is null where the engine has no calibrated evidence method. Imputation is not currently executed.
- Benchmarks in `samples/` and `backend/tests/fixtures/` use generated data. They measure regression behavior on these cases, not general data-cleaning accuracy.
- The Windows local benchmark measured 22.33 seconds and 129.00 MiB peak process working set for the 1,001-row end-to-end test-client workflow. This includes Python/Pandas imports and local test infrastructure; it is not a Render measurement. Measure on the target service before increasing limits or claiming hosted scale.
- The configured-limit benchmark analyzed 50,000 rows × 40 populated columns (4,250,157-byte CSV) in 15.71 seconds at 233.30 MiB peak process working set on Windows. A separate 60-column, one-row upload passed. A 50,000 × 60 fully populated CSV exceeds the 5 MiB upload cap; those independent limits are not jointly attainable for this shape. Render memory/runtime remain unmeasured.
- Export report/log/recipe are JSON, and cleaned is CSV. CSV formula prefixes are escaped; original uploaded bytes are kept unchanged.


