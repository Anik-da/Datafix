"""Generate a deterministic compact benchmark dataset and injection manifest."""

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).parent
random.seed(7319)
headers = [
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
clean = []
cities = ["Bengaluru", "Kolkata", "Delhi", "Pune"]
for i in range(1, 31):
    qty = (i % 5) + 1
    price = 100 + (i % 7) * 10
    clean.append(
        {
            "order_id": f"O{i:03d}",
            "quantity": str(qty),
            "unit_price": str(price),
            "total": str(qty * price),
            "city": cities[i % 4],
            "email": f"user{i}@example.test",
            "order_date": f"2026-01-{(i % 28) + 1:02d}",
            "ship_date": f"2026-01-{min((i % 28) + 3, 28):02d}",
            "category": "Books" if i % 2 else "Games",
            "note": "priority" if i % 3 == 0 else "standard",
        }
    )


def save(name, rows):
    with (ROOT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


save("datafix_clean.csv", clean)
dirty = [x.copy() for x in clean]
manifest = []


def inject(err, row, col, val, detector, behavior="detect"):
    old = dirty[row][col]
    dirty[row][col] = val
    manifest.append(
        {
            "error_id": err,
            "category": detector,
            "row_locator": f"row_{row + 1}",
            "column": col,
            "original_value": old,
            "injected_value": val,
            "expected_detector": detector,
            "expected_behavior": behavior,
        }
    )


inject("missing-1", 1, "note", "N/A", "missing")
inject("missing-empty-1", 13, "note", "   ", "missing")
inject("format-1", 2, "email", "not-an-email", "invalid_format")
inject("numeric-1", 10, "quantity", "2x", "invalid_format")
inject("date-1", 3, "order_date", "2026-19-45", "invalid_format")
inject("mixed-date-1", 11, "ship_date", "Jan 14, 2026", "invalid_format", "normalize_unambiguously")
inject("date-order-1", 12, "ship_date", "2026-01-13", "relationship", "flag_and_preserve")
inject("category-1", 4, "city", "BENGALURU ", "inconsistent")
inject("relationship-1", 5, "total", "999", "relationship")
inject("outlier-1", 6, "unit_price", "999999", "anomaly", "flag_and_preserve")
inject(
    "date-ambiguous",
    7,
    "order_date",
    "03/04/2026",
    "invalid_format",
    "flag_ambiguous_no_normalization",
)
inject("near-distinct", 8, "city", "Bangaluru", "inconsistent", "flag_candidate_no_merge")
dirty.append(dirty[9].copy())
manifest.append(
    {
        "error_id": "duplicate-1",
        "category": "duplicate",
        "row_locator": "row_31",
        "column": None,
        "original_value": None,
        "injected_value": "exact duplicate of row_10",
        "expected_detector": "duplicate",
        "expected_behavior": "propose_only",
    }
)
save("datafix_dirty.csv", dirty)
(ROOT / "datafix_error_manifest.json").write_text(
    json.dumps({"seed": 7319, "errors": manifest}, indent=2) + "\n", encoding="utf-8"
)
