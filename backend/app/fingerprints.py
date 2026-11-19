"""Stable, non-sensitive fingerprints for deterministic issue patterns."""
from __future__ import annotations

import hashlib
import json
import re
from .schemas import Issue, PatternMatch


def fingerprint_issue(issue: Issue, inferred_type: str) -> PatternMatch:
    # Only normalized issue metadata is hashed. Raw values and row identifiers
    # are intentionally excluded so signatures are reproducible and privacy-safe.
    title = re.sub(r"\b\d+\b", "<n>", issue.title.casefold())
    if issue.category.value=="missing": error_type,value_shape,format_pattern="missing_value","empty_or_placeholder","placeholder_token_or_blank"
    elif issue.category.value=="duplicate": error_type,value_shape,format_pattern="exact_duplicate","identical_row_shape",None
    elif issue.category.value=="invalid_format" and "date" in title: error_type,value_shape,format_pattern="date_format","mixed_or_unparseable_date","date_format_family_mismatch"
    elif issue.category.value=="invalid_format" and "numeric" in title: error_type,value_shape,format_pattern="numeric_format","unparseable_numeric_token","numeric_parse_failure"
    elif issue.category.value=="invalid_format": error_type,value_shape,format_pattern="invalid_format","field_format_mismatch",None
    elif issue.category.value=="inconsistent" and "similar" in title: error_type,value_shape,format_pattern="category_variant","case_or_whitespace_variant","category_case_or_boundary_space"
    elif issue.category.value=="inconsistent": error_type,value_shape,format_pattern="category_inconsistency","multiple_category_shapes",None
    elif issue.category.value=="anomaly": error_type,value_shape,format_pattern="statistical_or_rule_anomaly","numeric_or_rule_outlier",None
    elif issue.category.value=="row_structure_mismatch": error_type,value_shape,format_pattern="csv_row_width","short_or_overflow_record","header_field_count_mismatch"
    else: error_type,value_shape,format_pattern="cross_column_rule","relationship_violation",None
    signature = {
        "category": issue.category.value,
        "type": inferred_type,
        "error": title,
        "value_shape": value_shape,
        "format_pattern": format_pattern,
        "column_role": "identifier" if issue.column and issue.column.casefold().endswith(("_id", "_code")) else "field",
    }
    encoded = json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()
    fid = "fp_" + hashlib.sha256(encoded).hexdigest()[:16]
    strategy = {
        "missing": "review placeholders; use nulling or imputation only when justified",
        "duplicate": "inspect exact duplicate groups before removal",
        "invalid_format": "normalize only values with an unambiguous typed interpretation",
        "inconsistent": "review canonical mapping candidates against current dataset evidence",
        "anomaly": "review as an outlier; do not assume it is invalid",
        "row_structure_mismatch": "review the original row width; preserve overflow values and leave padded fields unresolved",
        "relationship": "inspect the supported cross-column rule and its affected rows",
    }.get(issue.category.value)
    evidence = [f"{e.label}: {e.metrics.get('count', issue.affected_rows)} affected observations" for e in issue.evidence[:3]]
    rule_ids=sorted({"detector:"+issue.category.value+":"+re.sub(r"[^a-z0-9]+","_",e.label.casefold()).strip("_") for e in issue.evidence})
    return PatternMatch(
        fingerprint_id=fid,
        title=f"{issue.category.value.replace('_', ' ').title()} pattern",
        explanation="This signature groups issues by detector category, inferred column type and normalized issue shape; it does not establish that a repair is correct.",
        support_count=max(1, issue.affected_rows),
        column_type=inferred_type,
        error_type=error_type,
        value_shape=value_shape,
        format_pattern=format_pattern,
        frequency_count=max(1, issue.affected_rows),
        supporting_rule_ids=rule_ids,
        evidence=evidence,
        suggested_strategy=strategy,
        limitations=["Signature contains no raw cell values.", "Matches are scoped to this issue shape, not prior user approvals.", "Current-run simulation and Safety Gate remain required."],
    )
