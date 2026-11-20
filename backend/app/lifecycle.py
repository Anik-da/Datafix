"""Deterministic allow-listed repair execution, simulation, replay and reporting."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import pandas as pd

from .config import settings
from .schemas import (
    Gate,
    ImpactMetric,
    Invariant,
    Issue,
    IssueCategory,
    Operation,
    Proposal,
    QualityDimensions,
    RippleImpact,
    RiskClass,
    SampleDiff,
    Simulation,
)
from .services import analyze_frame, infer_column, parse_date, profile, row_id

SUPPORTED = {
    Operation.trim_text,
    Operation.normalize_date,
    Operation.map_values,
    Operation.set_null,
    Operation.drop_exact_dupes,
    Operation.cast_numeric,
    Operation.manual_edit,
}

# Conservative maximum relative sum drift by risk. These limits are part of the
# gate policy and are reported in every simulation, rather than hidden in code.
AGGREGATE_DRIFT_LIMITS = {
    RiskClass.format_only: settings.aggregate_drift_format_max_pct / 100,
    RiskClass.value_substitution: settings.aggregate_drift_substitution_max_pct / 100,
    RiskClass.imputation: settings.aggregate_drift_imputation_max_pct / 100,
    RiskClass.destructive: settings.aggregate_drift_destructive_max_pct / 100,
}


def _numeric_aggregates(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    result = {}
    for column in frame.columns:
        if str(column).startswith("__datafix_"):
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if len(values):
            result[str(column)] = {
                "sum": float(values.sum()),
                "mean": float(values.mean()),
                "count": int(len(values)),
            }
    return result


def _functional_dependency_violations(frame: pd.DataFrame) -> dict[str, int]:
    """Count violations only for explicit, conventional single-table FDs."""
    names = {str(c).casefold(): c for c in frame.columns}
    pairs = []
    for determinant in ("pincode", "postal_code", "postcode", "zip"):
        if determinant in names and "city" in names:
            pairs.append((names[determinant], names["city"]))
    if "customer_id" in names:
        for dependent in ("customer_name", "email", "phone"):
            if dependent in names:
                pairs.append((names["customer_id"], names[dependent]))
    violations = {}
    for determinant, dependent in pairs:
        pairs_df = frame[[determinant, dependent]].fillna("").astype(str)
        pairs_df = pairs_df[
            (pairs_df[determinant].str.strip() != "") & (pairs_df[dependent].str.strip() != "")
        ]
        per_key = pairs_df.groupby(determinant, sort=False)[dependent].nunique()
        violations[f"{determinant}->{dependent}"] = int((per_key > 1).sum())
    return violations


def _business_rule_violations(frame: pd.DataFrame) -> int:
    names = {str(c).casefold(): c for c in frame.columns}
    violations = 0
    if {"quantity", "unit_price", "total"}.issubset(names):
        q, price, total = (names[x] for x in ("quantity", "unit_price", "total"))
        for row in frame.itertuples(index=False, name=None):
            record = dict(zip(frame.columns, row))
            values = []
            for col in (q, price, total):
                try:
                    values.append(float(str(record[col]).replace(",", "")))
                except (ValueError, TypeError):
                    values.append(None)
            if None not in values and not math.isclose(
                values[0] * values[1], values[2], rel_tol=1e-6, abs_tol=1e-6
            ):
                violations += 1
    start = next(
        (c for c in frame.columns if str(c).casefold() in {"start_date", "order_date"}), None
    )
    end = next((c for c in frame.columns if str(c).casefold() in {"end_date", "ship_date"}), None)
    if start and end:
        for a, b in zip(frame[start].astype(str), frame[end].astype(str)):
            left, left_ambiguous = parse_date(a)
            right, right_ambiguous = parse_date(b)
            if left and right and not left_ambiguous and not right_ambiguous and right < left:
                violations += 1
    return violations


def invariant_results(
    before: pd.DataFrame,
    after: pd.DataFrame,
    proposal: Proposal | None = None,
    issues: list[Issue] | None = None,
    changes: list[dict] | None = None,
    removed: int = 0,
    risk_class: RiskClass | None = None,
) -> tuple[list[Invariant], dict[str, float | int | None], int]:
    """Evaluate the seven documented invariants on original and staged frames."""
    changes = changes or []
    permitted_type_change = proposal is not None and proposal.op == Operation.cast_numeric
    before_types = {
        str(c): infer_column(before[c].fillna("").astype(str), str(c))[0]
        for c in before.columns
        if not str(c).startswith("__datafix_")
    }
    after_types = {
        str(c): infer_column(after[c].fillna("").astype(str), str(c))[0]
        for c in after.columns
        if not str(c).startswith("__datafix_")
    }
    schema_ok = list(before.columns) == list(after.columns) and (
        permitted_type_change or before_types == after_types
    )
    row_removal_allowed = bool(
        (proposal and proposal.op == Operation.drop_exact_dupes) or removed > 0
    )
    row_ok = (
        len(after) == len(before) - removed if row_removal_allowed else len(after) == len(before)
    )

    key_columns = [c.name for c in profile(before, 0).columns if c.is_key_candidate]
    key_violations = 0
    for column in key_columns:
        values = after[column].fillna("").astype(str)
        key_violations += int(values.str.strip().eq("").sum()) + int(values.duplicated().sum())

    issue_cells = set()
    for issue in issues or []:
        affected_columns = [issue.column] if issue.column else list(before.columns)
        for row_ref in issue.affected_row_ids:
            for column in affected_columns:
                issue_cells.add((row_ref, str(column)))
    valid_damaged = sum((x.get("row_id"), x.get("column")) not in issue_cells for x in changes)

    business_before, business_after = (
        _business_rule_violations(before),
        _business_rule_violations(after),
    )

    fd_before = _functional_dependency_violations(before)
    fd_after = _functional_dependency_violations(after)
    fd_increase = sum(max(0, fd_after.get(k, 0) - count) for k, count in fd_before.items()) + sum(
        v for k, v in fd_after.items() if k not in fd_before
    )

    before_agg, after_agg = _numeric_aggregates(before), _numeric_aggregates(after)
    drifts = {}
    for col in sorted(set(before_agg) | set(after_agg)):
        old = before_agg.get(col, {"sum": 0.0, "mean": 0.0, "count": 0})
        new = after_agg.get(col, {"sum": 0.0, "mean": 0.0, "count": 0})
        drifts[f"{col}.sum_relative"] = abs(new["sum"] - old["sum"]) / max(abs(old["sum"]), 1.0)
        drifts[f"{col}.mean_relative"] = abs(new["mean"] - old["mean"]) / max(abs(old["mean"]), 1.0)
        drifts[f"{col}.count_change"] = new["count"] - old["count"]
    risk = risk_class or (proposal.risk_class if proposal else RiskClass.format_only)
    limit = AGGREGATE_DRIFT_LIMITS[risk]
    max_drift = max(
        (
            v
            for k, v in drifts.items()
            if k.endswith(".sum_relative") or k.endswith(".mean_relative")
        ),
        default=0.0,
    )

    result = [
        Invariant(
            name="schema_and_types_preserved",
            status="pass" if schema_ok else "fail",
            detail="Column names, order, and inferred types are preserved except for an explicitly typed conversion.",
            observed="preserved" if schema_ok else "changed",
            threshold="preserved",
        ),
        Invariant(
            name="row_count_policy",
            status="pass" if row_ok else "fail",
            detail="Row count is preserved except for explicitly simulated exact-duplicate removal.",
            observed=len(after),
            threshold=len(before) - (removed if row_removal_allowed else 0),
            unit="rows",
        ),
        Invariant(
            name="candidate_keys_unique_non_null",
            status="pass" if key_violations == 0 else "fail",
            detail="Previously unique, non-null candidate keys remain unique and non-null.",
            observed=key_violations,
            threshold=0,
            unit="violations",
        ),
        Invariant(
            name="previously_valid_cells_preserved",
            status="pass" if valid_damaged == 0 else "fail",
            detail="Cells not flagged by the original detector set remain unchanged.",
            observed=valid_damaged,
            threshold=0,
            unit="cells",
        ),
        Invariant(
            name="business_rules_not_worsened",
            status="pass" if business_after <= business_before else "fail",
            detail="Explicit cross-column business-rule violations do not increase.",
            observed=business_after,
            threshold=business_before,
            unit="violations",
        ),
        Invariant(
            name="functional_dependencies_not_worsened",
            status="pass" if fd_increase == 0 else "fail",
            detail="Supported postcode-to-city and customer-id-to-contact dependencies do not gain violations.",
            observed=fd_increase,
            threshold=0,
            unit="violations",
        ),
        Invariant(
            name="aggregate_drift_within_risk_limit",
            status="pass" if max_drift <= limit else "fail",
            detail=f"Maximum relative numeric sum/mean drift is checked against the {risk.value} limit.",
            observed=max_drift,
            threshold=limit,
            unit="relative fraction",
        ),
    ]
    return result, drifts, valid_damaged


def execute(
    frame: pd.DataFrame, proposal: Proposal
) -> tuple[pd.DataFrame, list[dict], int, list[dict]]:
    """Execute typed parameters; return copy, changed cells, removed count, audit log."""
    result = frame.copy(deep=True)
    changes = []
    audit_log = []
    removed = []
    p = proposal.params
    col = proposal.column

    def set_cell(index: int, column: str, value: Any):
        before = str(result.iloc[index][column])
        after = "" if value is None else str(value)
        if before != after:
            result.iat[index, result.columns.get_loc(column)] = after
            item = {
                "row_id": row_id(index),
                "column": column,
                "before": before,
                "after": after,
                "action": "cell_changed",
            }
            if column.startswith("__datafix_extra_"):
                item["extra_field_position"] = sum(
                    not str(c).startswith("__datafix_") for c in result.columns
                ) + int(column.rsplit("_", 1)[1])
            changes.append(item)
            audit_log.append(item)

    if proposal.op in {Operation.trim_text, Operation.normalize_date, Operation.cast_numeric}:
        for rid, value in p.row_values.items():
            index = int(rid.split("_")[-1]) - 1
            if not (0 <= index < len(result) and col in result.columns):
                continue
            current = str(result.iloc[index][col])
            if proposal.op == Operation.trim_text:
                # Apply only while the current value still differs solely by its
                # boundary whitespace; this avoids overwriting a prior mapping.
                if current.strip() == value:
                    set_cell(index, col, value)
            elif proposal.op == Operation.normalize_date:
                current_date, current_ambiguous = parse_date(current)
                target_date, target_ambiguous = parse_date(value)
                if (
                    current_date
                    and target_date
                    and not current_ambiguous
                    and not target_ambiguous
                    and current_date.date() == target_date.date()
                ):
                    set_cell(index, col, value)
            elif proposal.op == Operation.cast_numeric:
                try:
                    current_number = float(current.replace(",", ""))
                    target_number = float(value.replace(",", ""))
                    if current_number == target_number:
                        set_cell(index, col, value)
                except (ValueError, AttributeError):
                    continue
    elif proposal.op == Operation.manual_edit and col in result.columns:
        index = int(p.row_id.split("_")[-1]) - 1
        if not (0 <= index < len(result)):
            raise ValueError("Manual edit row reference is out of range")
        if str(result.iloc[index][col]) != p.expected_value:
            raise ValueError("Manual edit original value is stale")
        set_cell(index, col, p.value)
        if (
            col.startswith("__datafix_extra_")
            and "__datafix_actual_fields" in result.columns
            and not p.value
        ):
            remaining = [
                c
                for c in result.columns
                if str(c).startswith("__datafix_extra_")
                and str(result.iloc[index][c]) not in {"", "<NA>"}
            ]
            if not remaining:
                expected = sum(not str(c).startswith("__datafix_") for c in result.columns)
                result.iat[index, result.columns.get_loc("__datafix_actual_fields")] = str(expected)
    elif proposal.op == Operation.map_values and col in result.columns:
        for index, value in enumerate(result[col].astype(str)):
            if value in p.mapping:
                set_cell(index, col, p.mapping[value])
    elif proposal.op == Operation.set_null and col in result.columns:
        tokens = {x.casefold() for x in p.placeholder_values}
        targets = {int(x.split("_")[-1]) - 1 for x in p.row_ids}
        for index, value in enumerate(result[col].astype(str)):
            if index in targets and value.strip().casefold() in tokens:
                set_cell(index, col, None)
    elif proposal.op == Operation.drop_exact_dupes:
        for group in p.duplicate_row_groups:
            for rid in group[1:]:
                index = int(rid.split("_")[-1]) - 1
                if 0 <= index < len(result):
                    removed.append(index)
        for index in sorted(set(removed)):
            audit_log.append(
                {
                    "row_id": row_id(index),
                    "column": None,
                    "before": None,
                    "after": None,
                    "action": "row_removed",
                }
            )
        if removed:
            result = result.drop(result.index[sorted(set(removed))]).reset_index(drop=True)
    else:
        raise ValueError("Operation is not supported by the deterministic registry")
    return result, changes, len(set(removed)), audit_log


def frame_hash(frame: pd.DataFrame) -> str:
    content = frame.to_json(orient="split", force_ascii=False).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _ripple_impact(
    frame: pd.DataFrame,
    after: pd.DataFrame,
    proposal: Proposal,
    issues: list[Issue],
    post_issues: list[Issue],
    changes: list[dict],
    audit_log: list[dict],
    invariants: list[Invariant],
) -> RippleImpact:
    rows = sorted({x["row_id"] for x in audit_log})
    direct = sorted({str(x["column"]) for x in changes if x.get("column")})
    if any(x.get("action") == "row_removed" for x in audit_log):
        direct = sorted(set(direct) | set(frame.columns.astype(str)))
    dependents = {}
    for source in direct:
        key = source.casefold()
        if any(t in key for t in ("postal", "pincode", "postcode", "zip")):
            dependents[source] = [
                c for c in frame.columns if str(c).casefold() in {"city", "state", "region"}
            ]
        elif key == "customer_id" or key.endswith("_customer_id"):
            dependents[source] = [
                c
                for c in frame.columns
                if any(t in str(c).casefold() for t in ("customer_name", "email", "phone"))
            ]
        elif key in {
            "quantity",
            "unit_price",
            "price",
            "total",
            "amount",
            "order_date",
            "start_date",
            "ship_date",
            "end_date",
        }:
            dependents[source] = [
                c
                for c in frame.columns
                if str(c).casefold()
                in {
                    "quantity",
                    "unit_price",
                    "price",
                    "total",
                    "amount",
                    "order_date",
                    "start_date",
                    "ship_date",
                    "end_date",
                }
                and str(c) != source
            ]
    relationships = {c: "direct" for c in direct}
    checks = []
    for source, targets in dependents.items():
        for target in targets:
            relationships[str(target)] = "measured_dependency"
            checks.append(f"{source} -> {target}: explicit supported relationship")
    metrics = []
    candidate_keys = {x.name for x in profile(frame, 0).columns if x.is_key_candidate}
    for col, relation in sorted(relationships.items()):
        if col not in frame.columns or col not in after.columns:
            continue

        def measure(data):
            values = data[col].fillna("").astype(str)
            nonblank = values[values.str.strip().ne("")]
            numeric = pd.to_numeric(
                nonblank.str.replace(",", "", regex=False), errors="coerce"
            ).dropna()
            return {
                "missing_count": int(values.str.strip().eq("").sum()),
                "null_pct": float(values.str.strip().eq("").mean()) if len(values) else 0.0,
                "distinct_count": int(nonblank.nunique()),
                "minimum": float(numeric.min()) if len(numeric) else None,
                "maximum": float(numeric.max()) if len(numeric) else None,
                "mean": float(numeric.mean()) if len(numeric) else None,
                "sum": float(numeric.sum()) if len(numeric) else None,
            }

        b, a = measure(frame), measure(after)
        for name in ("minimum", "maximum", "mean", "sum"):
            if b[name] is None and a[name] is None:
                b.pop(name)
                a.pop(name)
        candidate = col in candidate_keys
        if candidate:

            def key_violations(data):
                values = data[col].fillna("").astype(str)
                return int(values.str.strip().eq("").sum() + values.duplicated().sum())

            b["candidate_key_violations"] = key_violations(frame)
            a["candidate_key_violations"] = key_violations(after)
        for name in b:
            if relation == "direct" or b[name] != a[name]:
                metrics.append(
                    ImpactMetric(
                        metric=name,
                        column=col,
                        before=b[name],
                        after=a[name],
                        change=a[name] - b[name]
                        if isinstance(a[name], (int, float)) and isinstance(b[name], (int, float))
                        else None,
                        relationship=relation,
                        support=["measured on original and temporary simulated data"]
                        if relation == "direct"
                        else ["explicit supported dependency; no correlation-based inference"],
                    )
                )
    relevant_business_columns = {
        "quantity",
        "unit_price",
        "price",
        "total",
        "amount",
        "order_date",
        "start_date",
        "ship_date",
        "end_date",
    }
    if any(c.casefold() in relevant_business_columns for c in direct):
        old = _business_rule_violations(frame)
        new = _business_rule_violations(after)
        metrics.append(
            ImpactMetric(
                metric="business_rule_violations",
                column="dataset",
                before=old,
                after=new,
                change=new - old,
                relationship="measured_dependency",
                support=[
                    "existing deterministic cross-column business rules evaluated on both frames"
                ],
            )
        )
        checks.append("configured cross-column business rules")
    if any(
        any(t in c.casefold() for t in ("postal", "pincode", "postcode", "zip", "customer_id"))
        for c in direct
    ):
        old = _functional_dependency_violations(frame)
        new = _functional_dependency_violations(after)
        for key in sorted(set(old) | set(new)):
            metrics.append(
                ImpactMetric(
                    metric=f"functional_dependency_violations:{key}",
                    column="dataset",
                    before=old.get(key, 0),
                    after=new.get(key, 0),
                    change=new.get(key, 0) - old.get(key, 0),
                    relationship="measured_dependency",
                    support=[
                        "existing deterministic functional dependency evaluated on both frames"
                    ],
                )
            )
        checks.append(
            "configured postcode-to-city and customer-id-to-contact functional dependencies"
        )
    before_map = {(x.category, x.title, x.column): x.id for x in issues}
    after_map = {(x.category, x.title, x.column): x.id for x in post_issues}
    resolved_keys = before_map.keys() - after_map.keys()
    remaining_keys = before_map.keys() & after_map.keys()
    introduced_keys = after_map.keys() - before_map.keys()
    if not changes and not audit_log:
        risk_level = "unknown"
    elif (
        any(item.status == "fail" for item in invariants)
        or proposal.risk_class == RiskClass.destructive
    ):
        risk_level = "high"
    elif proposal.risk_class in {RiskClass.value_substitution, RiskClass.imputation}:
        risk_level = "moderate"
    else:
        risk_level = "low"
    risk_reason = f"Risk level {risk_level} follows deterministic proposal class {proposal.risk_class.value} and simulated invariant results."
    return RippleImpact(
        proposal_id=proposal.id,
        direct_row_ids=rows[:200],
        direct_cells=len(changes),
        direct_columns=direct,
        direct_metrics=[x for x in metrics if x.relationship == "direct"],
        indirect_metrics=[x for x in metrics if x.relationship == "measured_dependency"],
        affected_dependency_checks=checks,
        potentially_resolved_issue_ids=[before_map[k] for k in sorted(resolved_keys)],
        remaining_issue_ids=[before_map[k] for k in sorted(remaining_keys)],
        introduced_issue_ids=[after_map[k] for k in sorted(introduced_keys)],
        risk_level=risk_level,
        invariants=invariants,
        risk_explanations=[
            risk_reason,
            "Safety Gate remains the final authority and evaluates the same invariant results.",
        ],
        limitations=[
            "Only directly changed columns and explicit supported dependencies are included.",
            "Statistical correlations are not treated as dependencies.",
            "Numeric summaries do not establish semantic correctness.",
        ],
    )


def simulate(
    frame: pd.DataFrame, proposal: Proposal, issues: list[Issue], original_size: int
) -> tuple[Simulation, Gate]:
    if proposal.op not in SUPPORTED:
        inv = [
            Invariant(
                name="operation_allow_list",
                status="fail",
                detail="Operation is not implemented by the deterministic registry.",
            )
        ]
        return Simulation(
            cells_changed=0,
            rows_affected=0,
            rows_removed=0,
            previously_valid_cells_changed=0,
            aggregate_drift={},
            new_issues_introduced=0,
            sample_diff=[],
            invariants=inv,
        ), Gate(
            decision="refused",
            reasons=["Operation is not implemented."],
            refusal_kind="insufficient_evidence",
        )
    try:
        after, changes, removed, audit_log = execute(frame, proposal)
        before_issues = {(x.category, x.title, x.column) for x in issues}
        _, post_issues, _ = analyze_frame("simulation", after, original_size)
        introduced = sum((x.category, x.title, x.column) not in before_issues for x in post_issues)
        invariants, drift, valid_damaged = invariant_results(
            frame, after, proposal, issues, changes, removed
        )
        if introduced:
            invariants.append(
                Invariant(
                    name="no_new_issue_signatures",
                    status="fail",
                    detail="The detector found previously absent issue signatures after simulation.",
                    observed=introduced,
                    threshold=0,
                    unit="issue signatures",
                )
            )
        issue_cells = {
            (rid, col)
            for issue in issues
            if issue.id in proposal.issue_ids
            for rid in issue.affected_row_ids
            for col in ([issue.column] if issue.column else frame.columns)
        }
        diffs = [
            SampleDiff(
                row_id=x["row_id"],
                column=x["column"],
                before=x["before"],
                after=x["after"],
                was_valid=(x["row_id"], x["column"]) not in issue_cells,
            )
            for x in changes[:20]
        ]
        impact = _ripple_impact(
            frame, after, proposal, issues, post_issues, changes, audit_log, invariants
        )
        sim = Simulation(
            cells_changed=len(changes),
            rows_affected=len({x["row_id"] for x in audit_log}),
            rows_removed=removed,
            previously_valid_cells_changed=valid_damaged,
            aggregate_drift={**drift, "row_count_change": len(after) - len(frame)},
            new_issues_introduced=introduced,
            sample_diff=diffs,
            invariants=invariants,
            impact=impact,
        )
        failed = any(x.status == "fail" for x in invariants)
        if failed:
            gate = Gate(
                decision="refused",
                reasons=[x.name for x in invariants if x.status == "fail"],
                refusal_kind="invariant_failed",
            )
        elif not changes and not removed:
            gate = Gate(
                decision="refused",
                reasons=["Simulation found no applicable changes."],
                refusal_kind="insufficient_evidence",
            )
        elif proposal.risk_class == RiskClass.format_only:
            gate = Gate(
                decision="auto_apply",
                reasons=["Typed format-only change passed deterministic simulation."],
                refusal_kind=None,
            )
        else:
            gate = Gate(
                decision="needs_approval",
                reasons=["Value substitutions and destructive changes require explicit approval."],
                refusal_kind=None,
            )
        return sim, gate
    except Exception:
        inv = [
            Invariant(
                name="simulation_completed",
                status="fail",
                detail="The typed proposal could not be simulated safely.",
            )
        ]
        return Simulation(
            cells_changed=0,
            rows_affected=0,
            rows_removed=0,
            previously_valid_cells_changed=0,
            aggregate_drift={},
            new_issues_introduced=0,
            sample_diff=[],
            invariants=inv,
        ), Gate(decision="refused", reasons=["Simulation failed."], refusal_kind="invariant_failed")


def quality(frame: pd.DataFrame, issues: list[Issue]) -> QualityDimensions:
    frame = frame.loc[:, [c for c in frame.columns if not str(c).startswith("__datafix_")]]
    cells = max(1, frame.shape[0] * frame.shape[1])
    missing = sum(1 for v in frame.to_numpy().flat if not str(v).strip())
    duplicates = int(frame.duplicated().sum()) if len(frame) else 0
    validity_issues = sum(
        i.affected_cells for i in issues if i.category == IssueCategory.invalid_format
    )
    consistency_issues = sum(
        i.affected_cells
        for i in issues
        if i.category in {IssueCategory.inconsistent, IssueCategory.relationship}
    )
    return QualityDimensions(
        completeness=max(0, 1 - missing / cells),
        validity=max(0, 1 - validity_issues / cells),
        uniqueness=max(0, 1 - duplicates / max(1, len(frame))),
        consistency=max(0, 1 - consistency_issues / cells),
        formulas={
            "completeness": "1 - blank_cells / total_cells",
            "validity": "1 - detected_invalid_cells / total_cells",
            "uniqueness": "1 - exact_duplicate_rows / row_count",
            "consistency": "1 - inconsistent_or_relationship_affected_cells / total_cells",
        },
    )


def csv_safe(value: Any, column_name: str = "") -> str:
    text = "" if value is None else str(value)
    # Preserve ordinary telephone identifiers and signed numeric values. They
    # are data, not formulas; prefixing them changes the exported value.
    if "phone" in column_name.casefold() and re.fullmatch(r"\+?\d[\d\s().-]*", text):
        return text
    if re.fullmatch(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
        return text
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text
