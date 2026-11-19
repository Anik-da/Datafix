"""Generate a deterministic 1,000-row synthetic dataset and known-error manifest."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
HEADERS = [
    "order_id",
    "quantity",
    "unit_price",
    "total",
    "city",
    "email",
    "order_date",
    "ship_date",
    "category",
    "note",
]
CITIES = ["Bengaluru", "Kolkata", "Delhi", "Pune"]
clean = []
for i in range(1, 1001):
    quantity = i % 7 + 1
    price = 100 + (i % 9) * 20
    day = (i % 27) + 1
    clean.append(
        {
            "order_id": f"O{i:04d}",
            "quantity": str(quantity),
            "unit_price": str(price),
            "total": str(quantity * price),
            "city": CITIES[i % len(CITIES)],
            "email": f"customer{i}@example.test",
            "order_date": f"2026-01-{day:02d}",
            "ship_date": f"2026-01-{min(day + 2, 28):02d}",
            "category": "Books" if i % 2 else "Games",
            "note": "priority" if i % 3 == 0 else "standard",
        }
    )

dirty = [row.copy() for row in clean]
errors = []


def inject(error_id, row, column, value, detector, behavior="detect"):
    old = dirty[row][column]
    dirty[row][column] = value
    errors.append(
        {
            "error_id": error_id,
            "expected_detector": detector,
            "expected_behavior": behavior,
            "row_locator": f"row_{row + 1}",
            "column": column,
            "original_value": old,
            "injected_value": value,
        }
    )


inject("missing-placeholder", 9, "note", "N/A", "missing")
inject("missing-blank", 19, "note", "   ", "missing")
inject("invalid-email", 29, "email", "not-an-email", "invalid_format", "flag_only")
inject("invalid-number", 39, "quantity", "2x", "invalid_format", "flag_only")
inject("invalid-date", 49, "order_date", "2026-19-45", "invalid_format", "flag_only")
inject("ambiguous-date", 59, "order_date", "03/04/2026", "invalid_format", "no_locale_guess")
inject(
    "mixed-date",
    69,
    "ship_date",
    "Jan 14, 2026",
    "invalid_format",
    "unambiguous_normalization_candidate",
)
inject("date-order", 79, "ship_date", "2026-01-01", "relationship", "flag_only")
inject("equivalent-category", 89, "city", "BENGALURU ", "inconsistent", "map_requires_approval")
inject("near-category", 99, "city", "Bangaluru", "inconsistent", "flag_only")
inject("numeric-outlier", 109, "unit_price", "999999", "anomaly", "flag_only")
inject("arithmetic-mismatch", 119, "total", "999", "relationship", "flag_only")
dirty.append(dirty[0].copy())
errors.append(
    {
        "error_id": "exact-duplicate",
        "expected_detector": "duplicate",
        "expected_behavior": "drop_requires_approval",
        "row_locator": "row_1001",
        "column": None,
        "original_value": None,
        "injected_value": "exact copy of row_1",
    }
)


def save(name, rows):
    with (ROOT / name).open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


save("datafix_1000_clean.csv", clean)
save("datafix_1000_dirty.csv", dirty)
(ROOT / "datafix_1000_error_manifest.json").write_text(
    json.dumps({"seed": "deterministic-formula-v1", "base_rows": 1000, "errors": errors}, indent=2)
    + "\n",
    encoding="utf-8",
)
