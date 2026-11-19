# Ground-Truth Validation Report

## Dataset

- Generated via `samples/generate_walkthrough_fixture.py` from the repository’s synthetic `orders_dirty.csv`; the canonical source was not modified.
- Fixture: `samples/walkthrough_dirty.csv` and served copy `frontend/public/demo/walkthrough_dirty.csv`.
- Manifest: `samples/walkthrough_error_manifest.json`.
- 1,001 records, 14 declared fields; one injected extra field on `row_150` creates the structural mismatch.
- SHA-256: `ef629d7b8330522397c35d66191d6de6dac74360a956c9b08d4b730311281a4b` for source and public copy; uploaded run reports the same hash.

## Detection comparison

All 15/15 injected manifest cases matched an issue with the expected detector and row reference: missing customer name, placeholder email/phone, invalid email/quantity, mixed and ambiguous dates, city/category inconsistencies, similar-but-distinct city, arithmetic/date-order relationships, missing price, exact duplicate, and extra-field row structure.

This is positive-case recall for this synthetic fixture, not a general precision estimate. Some detector findings group multiple cases or split a case into multiple issues; therefore 15 planted cases and 18 issue groups are not expected to be equal.

## Preservation and repair result

- One `city` mapping was approved and applied; one date normalization auto-applied.
- The exact duplicate proposal was rejected, so the duplicate remained.
- The ambiguous date proposal was refused and a later approval attempt returned 409.
- Structural mismatch was preserved as overflow metadata and remained unresolved; export writes it in `__unexpected_extra_1`.
- The similar-looking city spelling at `row_101` remained distinct.
- Legitimate `row_131` quantity/total outliers remained unchanged.
- Replay hash matched; 0 previously valid cells were damaged.

## Clean truth check

`orders_clean_truth.csv` uploaded as 1,000 rows and analyzed to 2 anomaly findings, 0 proposals. Both are documented clean-truth outliers at `row_131`; the detector labels unusual observations but makes no repair recommendation. Original upload SHA matched local bytes. This behavior is disclosed instead of calling the data perfectly issue-free.
