# Button and Interaction Results

Status counts below describe 46 interaction groups, not a claim that every individual animation or control was exhaustively clicked. PASS requires observed correct output or an actual request/response. Items marked partial were not completely exercised in a live browser.

| # | Page / control | Expected and observed result | API / evidence | Status |
|---:|---|---|---|---|
| 1 | Intake: choose file | Selected CSV reached backend and produced a run | `POST /api/v1/runs` 201; browser run IDs in report | PASS |
| 2 | Intake: drag and drop | Drop path is coded; not exercised in browser | Dropzone handler | PARTIALLY_WORKING |
| 3 | Intake: extension rejection | UI and backend guards exist; not exercised end to end | Existing backend suite | PARTIALLY_WORKING |
| 4 | Intake: empty/size rejection | UI and backend limits exist; not exercised end to end | Existing backend suite | PARTIALLY_WORKING |
| 5 | Intake: upload and analyze | Actual file accepted and issues rendered | Upload 201; analyze 200 | PASS |
| 6 | Intake: server error recovery | Friendly API messages exist; forced UI error not tested | `api.ts` mapping | PARTIALLY_WORKING |
| 7 | Intake: retry same file | Input resets after selection; retry not browser-tested | Dropzone `onChange` | PARTIALLY_WORKING |
| 8 | Intake: structural warning display | Backend warning path exists; no warning-producing file used in UI | API/UI path | PARTIALLY_WORKING |
| 9 | Intake navigation | `/app` rendered and uploaded run navigated to Overview | Browser | PASS |
| 10 | Overview: row/column profile | Rendered 31×10 browser run and 1,001×10 canonical API profile | Analyze 200 | PASS |
| 11 | Overview: missing/duplicate metrics | UI matched backend values for the tested run | Missing 2, duplicate 1 on 31-row run | PASS |
| 12 | Overview: issue count | UI showed 12 findings, matching analysis | Analyze response | PASS |
| 13 | Overview: issue explanations | Five questions rendered with simple language, row references and safety label | Browser Overview | PASS |
| 14 | Overview: Advanced details expander | Present but not toggled through all issues | UI | PARTIALLY_WORKING |
| 15 | Overview: column profile | Actual columns, types, missing and distinct counts rendered | DatasetProfile | PASS |
| 16 | Overview: charts/filters/tabs | Not every interaction or chart value compared | UI | PARTIALLY_WORKING |
| 17 | Overview: uncertainty heatmap | Real uncertainty endpoint returned 200; every filter/page state not verified | `GET /uncertainty` | PARTIALLY_WORKING |
| 18 | Overview: fingerprints | Patterns attached to all 12 canonical findings; sample raw values absent from signature payload; panel interaction not fully audited | Analysis JSON | PARTIALLY_WORKING |
| 19 | Smart semantic schema discovery | No connected response/endpoint in the current analysis contract | OpenAPI analysis schema | NOT_CONNECTED |
| 20 | Relationship Guardian | Date-order and arithmetic findings were detected; general orphan/reference discovery not proven | 2 relationship findings | PARTIALLY_WORKING |
| 21 | Anomaly detection | Known `unit_price` outlier flagged and preserved for review | `row_110`, IQR evidence | PASS |
| 22 | RippleGuard impact panel | Proposal simulations and impact metrics were returned; all visual dependencies not inspected | Analysis simulation payload | PARTIALLY_WORKING |
| 23 | Studio lanes/search filters | Controls rendered; each lane/search combination not exhaustively exercised | Studio | PARTIALLY_WORKING |
| 24 | Studio proposal selection | Selected actual placeholder proposal | Browser | PASS |
| 25 | Studio before/after evidence | Issue sample values rendered; every proposal’s evidence not manually checked | Browser + analysis | PARTIALLY_WORKING |
| 26 | Studio manual edit | Changed `N/A` to known fixture ground truth `standard`; revision persisted as version 2 `manual_edit` | Edit 200 | PASS |
| 27 | Studio fresh simulation/gate | Revised proposal carried fresh simulation and `needs_approval` gate | Edit response, approval required | PASS |
| 28 | Studio approval | Explicit approval recorded before apply | Decisions 200; ledger `decided_by=user` | PASS |
| 29 | Studio rejection | Rejection path not exercised in live browser | Existing backend tests only | PARTIALLY_WORKING |
| 30 | Refused repair override | Attempt to approve refused proposal rejected with 409 `invalid_decision_state` | Canonical API run | PASS |
| 31 | Apply plan | Automatic and explicitly approved operations applied | Apply 200, `status=applied` | PASS |
| 32 | Apply error display | Safety-blocked UI path not forced in browser | UI handler | PARTIALLY_WORKING |
| 33 | Proof: verification action | Backend verification completed | Verify 200 | PASS |
| 34 | Proof: replay hash | UI and Passport said replay matched | `replay.match=true` | PASS |
| 35 | Proof: issue/invariant summary | Before/after delta and zero valid-cell damage matched response | 12→10 browser run; 12→8 canonical run | PASS |
| 36 | Passport download and JSON | File downloaded, parsed, and included run hashes/status | Export 200 | PASS |
| 37 | Passport inline loading state | Download worked; inline passport panel was captured before its async render settled once | Browser snapshot | PARTIALLY_WORKING |
| 38 | Copy hash | Control exists; clipboard permission/result not tested | Proof page | PARTIALLY_WORKING |
| 39 | History refresh and ledger | Backend operation rows rendered across separate requests | History GET 200 | PASS |
| 40 | Undo/reapply | Backend suite covers lifecycle; browser undo/reapply not run | 48-test suite | PARTIALLY_WORKING |
| 41 | Applied Operations table | Now uses actual operation records/counts, including active state | Fixed and rebuilt | PASS |
| 42 | Copy operation summary | Label corrected; clipboard click not tested | History | PARTIALLY_WORKING |
| 43 | Export: five downloads | Cleaned data, quality report, log, recipe and Passport downloaded in browser | Five export calls 200 | PASS |
| 44 | Export content integrity | Downloaded files matched API response SHA-256; CSV parsed, JSON parsed | Browser run evidence JSON | PASS |
| 45 | Recipe import/compatibility | No import endpoint or UI is connected | OpenAPI has no recipe import | NOT_CONNECTED |
| 46 | Supabase lifecycle | Current app uses local storage; live persistence/restart not established | Prior PGRST205 schema-cache failure | NOT_CONNECTED |

Totals: 23 PASS · 20 PARTIALLY_WORKING · 3 NOT_CONNECTED · 0 FAIL · 0 BLOCKED.

Browser route cases (9) all rendered: `/`, `/walkthrough`, `/app`, `/intake`, and `/runs/{id}/{overview,studio,proof,history,export}`. Desktop and mobile Intake checks are described in `USER_EXPERIENCE_AUDIT.md`.
