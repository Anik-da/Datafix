"""CSV ingestion, profiling and deterministic evidence-backed analysis."""

from __future__ import annotations

import csv
from functools import lru_cache
import hashlib
import io
import json
import logging
import math
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import numpy as np
import pandas as pd

from .config import settings
from .errors import InputProblem
from .ingestion import parse_dataset
from .schemas import (
    ColumnProfile,
    Confidence,
    DatasetProfile,
    DiagnosisHypothesis,
    DropExactDupesParams,
    Evidence,
    EvidenceKind,
    Issue,
    IssueCategory,
    IssueDisposition,
    ManualEditParams,
    MapValuesParams,
    MostFrequent,
    NormalizeDateParams,
    Operation,
    OperationParams,
    Proposal,
    ProposalSource,
    RiskClass,
    RunMetadata,
    RunStatus,
    SetNullParams,
    TrimTextParams,
)

log = logging.getLogger("datafix.analysis")
PLACEHOLDERS = {"n/a", "na", "null", "none", "-", "unknown"}
EMAIL = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z]{2,})+$", re.I
)
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def parse_csv_details(raw: bytes) -> tuple[pd.DataFrame, list[str], str, str]:
    if not raw:
        raise InputProblem(400, "empty_file", "The uploaded CSV is empty.")
    signatures = (
        (b"%PDF-", "pdf"),
        (b"PK\x03\x04", "zip"),
        (b"PK\x05\x06", "zip"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"),
        (b"\x1f\x8b", "gzip"),
    )
    for signature, label in signatures:
        if raw.startswith(signature):
            raise InputProblem(
                415,
                "unsupported_content",
                f"The file content has a {label} signature; upload a plain-text CSV.",
            )
    is_unicode_wide = raw.startswith(
        (b"\xff\xfe", b"\xfe\xff", b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")
    )
    if b"\x00" in raw and not is_unicode_wide:
        raise InputProblem(415, "unsupported_content", "Binary content is not accepted as CSV.")
    text = None
    encoding = ""
    for signature, candidate in (
        (b"\xff\xfe\x00\x00", "utf-32"),
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"", "utf-8"),
    ):
        if not raw.startswith(signature):
            continue
        try:
            text = raw.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        try:
            text = raw.decode("cp1252")
            encoding = "cp1252"
        except UnicodeDecodeError:
            raise InputProblem(
                422,
                "unsupported_encoding",
                "CSV encoding could not be detected safely; use UTF-8, UTF-16, or Windows-1252.",
            )
    if any((ord(ch) < 32 and ch not in "\r\n\t\f") for ch in text):
        raise InputProblem(
            415,
            "unsupported_content",
            "The file contains binary control characters and is not a supported CSV.",
        )
    try:
        sample = text[:65536]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        reader = csv.reader(io.StringIO(text, newline=""), strict=True, delimiter=delimiter)
        rows = []
        for row in reader:
            rows.append((row, reader.line_num))
    except csv.Error as exc:
        raise InputProblem(400, "malformed_csv", f"Malformed CSV: {exc}") from exc
    if not rows or not rows[0][0] or all(not x.strip() for x in rows[0][0]):
        raise InputProblem(400, "missing_header", "CSV must contain a non-empty header row.")
    headers = rows[0][0]
    max_cell_chars = getattr(settings, "max_cell_chars", 100000)
    if any(len(cell) > max_cell_chars for row, _line in rows for cell in row):
        raise InputProblem(
            422,
            "cell_too_long",
            "A CSV cell exceeds the configured maximum length.",
            {"limit_characters": max_cell_chars},
        )
    if any(not h.strip() for h in headers):
        raise InputProblem(422, "empty_header", "Column headers cannot be empty.")
    dup = [h for h, n in Counter(headers).items() if n > 1]
    if dup:
        raise InputProblem(
            422, "duplicate_headers", "CSV contains duplicate column headers.", {"headers": dup}
        )
    if len(headers) > settings.max_columns:
        raise InputProblem(
            422,
            "column_limit_exceeded",
            "CSV exceeds the configured column limit.",
            {"limit": settings.max_columns},
        )
    data = []
    physical_lines = []
    raw_rows = []
    max_extra = 0
    for row, physical_line in rows[1:]:
        if not row:
            continue
        physical_lines.append(physical_line)
        raw_rows.append(row)
        max_extra = max(max_extra, max(0, len(row) - len(headers)))
        data.append((row[: len(headers)] + [""] * max(0, len(headers) - len(row))))
        if len(data) > settings.max_rows:
            raise InputProblem(
                422,
                "row_limit_exceeded",
                "CSV exceeds the configured row limit.",
                {"limit": settings.max_rows},
            )
    if len(headers) + max_extra > settings.max_columns:
        raise InputProblem(
            422,
            "column_limit_exceeded",
            "CSV contains too many extra fields to recover safely.",
            {"limit": settings.max_columns},
        )
    # Store overflow values in explicit, reserved metadata columns so they are
    # never discarded. Short rows are padded with nulls, without inference.
    has_mismatch = any(len(row) != len(headers) for row in raw_rows)
    columns = headers + (
        [f"__datafix_extra_{i + 1}" for i in range(max_extra)]
        + ["__datafix_physical_line", "__datafix_actual_fields", "__datafix_raw_row"]
        if has_mismatch
        else []
    )
    normalized = []
    for row, line in zip(data, physical_lines):
        original = raw_rows[len(normalized)]
        extras = original[len(headers) :]
        extras = extras + [""] * (max_extra - len(extras))
        normalized.append(
            row
            + (
                extras + [str(line), str(len(original)), json.dumps(original, ensure_ascii=False)]
                if has_mismatch
                else []
            )
        )
    frame = pd.DataFrame(normalized, columns=columns, dtype="string")
    frame.attrs["source_headers"] = headers
    return frame, headers, encoding, delimiter


def parse_csv(raw: bytes) -> tuple[pd.DataFrame, list[str]]:
    """Backward-compatible CSV parser API; delimiter and BOM encoding are detected."""
    frame, headers, _encoding, _delimiter = parse_csv_details(raw)
    return frame, headers


def row_id(index: int) -> str:
    return f"row_{index + 1}"


def _is_missing(value: Any) -> bool:
    return value is None or pd.isna(value) or (isinstance(value, str) and not value.strip())


def _float(value: str) -> float | None:
    try:
        number = float(value.replace(",", ""))
        return number if math.isfinite(number) else None
    except (ValueError, AttributeError):
        return None


def _safe_example(column: str, value: Any) -> str:
    lowered = column.casefold()
    if (
        any(token in lowered for token in ("email", "phone", "name", "address", "ssn", "postal"))
        or lowered.endswith("_id")
        or lowered == "id"
    ):
        return "[redacted]"
    return str(value)[:80]


def infer_column(series: pd.Series, name: str) -> tuple[str, list[float], float | None]:
    vals = [str(v) for v in series if not _is_missing(v)]
    if not vals:
        return "string", [], None
    lowered = name.casefold()
    # Identifier-like numeric strings (postal codes and phone numbers in
    # particular) are labels, not quantities. Do not compute numeric outliers
    # or flag formatting variation as a numeric parse error for these fields.
    identifier_like = any(
        token in lowered for token in ("postal", "pincode", "postcode", "zip", "phone", "ssn")
    ) or lowered.endswith(("_id", "id", "_code", "code"))
    if identifier_like:
        uniques = len(set(vals))
        return (
            ("category" if uniques <= min(50, max(10, int(len(vals) * 0.2))) else "string"),
            [],
            1.0,
        )
    nums = [_float(v) for v in vals]
    numeric_ratio = sum(v is not None for v in nums) / len(vals)
    leading_zero = any(re.fullmatch(r"0\d+", v.strip()) for v in vals)
    if numeric_ratio >= 0.8 and not leading_zero:
        return "number", [v for v in nums if v is not None], numeric_ratio
    if "date" in name.lower() or name.lower().endswith(("_at", "_on")):
        parsed = [parse_date(v)[0] for v in vals]
        ratio = sum(v is not None for v in parsed) / len(vals)
        if ratio >= 0.8:
            return "date", [], ratio
    uniques = len(set(vals))
    return ("category" if uniques <= min(50, max(10, int(len(vals) * 0.2))) else "string"), [], 1.0


@lru_cache(maxsize=65536)
def parse_date(value: str) -> tuple[datetime | None, bool]:
    matches = []
    for fmt in DATE_FORMATS:
        try:
            matches.append(datetime.strptime(value.strip(), fmt))
        except ValueError:
            pass
    if not matches:
        return None, False
    unique = {x.date() for x in matches}
    ambiguous = len(unique) > 1
    return matches[0], ambiguous


def profile(frame: pd.DataFrame, original_size: int) -> DatasetProfile:
    frame = frame.loc[:, [c for c in frame.columns if not str(c).startswith("__datafix_")]]
    n, m = frame.shape
    cols = []
    total_distinct = 0
    for name in frame.columns:
        s = frame[name].fillna("").astype(str)
        missing_mask = s.map(lambda x: not x.strip() or x.strip().casefold() in PLACEHOLDERS)
        nonmissing = s[~missing_mask]
        null_count = int(missing_mask.sum())
        distinct = int(nonmissing.nunique())
        total_distinct += distinct
        dtype, numbers, consistency = infer_column(s, name)
        freq = Counter(nonmissing.tolist()).most_common(5)
        mn = mx = mean = median = std = None
        if dtype == "number" and numbers:
            mn, mx = min(numbers), max(numbers)
            mean = float(np.mean(numbers))
            median = float(np.median(numbers))
            std = float(np.std(numbers, ddof=1)) if len(numbers) > 1 else 0.0
        elif dtype == "date" and nonmissing.size:
            dates = [parse_date(v)[0] for v in nonmissing if parse_date(v)[0] is not None]
            if dates:
                mn, mx = min(dates).isoformat(), max(dates).isoformat()
        distribution = (
            [MostFrequent(value=str(v), count=int(c)) for v, c in freq]
            if dtype == "category"
            else []
        )
        lowered = name.casefold()
        sensitive = (
            any(
                token in lowered for token in ("email", "phone", "name", "address", "ssn", "postal")
            )
            or lowered.endswith("_id")
            or lowered == "id"
        )
        top_values = (
            [] if sensitive else [MostFrequent(value=str(v), count=int(c)) for v, c in freq]
        )
        cols.append(
            ColumnProfile(
                name=name,
                inferred_type=dtype,
                null_count=null_count,
                null_pct=(100 * null_count / n if n else 0.0),
                distinct_count=distinct,
                is_key_candidate=(n > 0 and distinct == n and null_count == 0),
                most_frequent=top_values,
                minimum=mn,
                maximum=mx,
                mean=mean,
                median=median,
                standard_deviation=std,
                category_distribution=distribution,
                format_consistency=consistency,
            )
        )
    # Duplicate count is number of rows after each first exact occurrence.
    dup_count = int(frame.duplicated(keep="first").sum()) if n else 0
    return DatasetProfile(
        row_count=n,
        column_count=m,
        dataset_size_bytes=original_size,
        duplicate_record_count=dup_count,
        total_missing_cells=sum(c.null_count for c in cols),
        total_distinct_values=total_distinct,
        columns=cols,
    )


def _issue(
    run_id: str,
    category: IssueCategory,
    title: str,
    column: str | None,
    description: str,
    indices: list[int],
    cells: int,
    evidence: list[Evidence],
    diagnosis: list[str],
    disposition: IssueDisposition,
) -> Issue:
    signature = f"{category.value}|{title}|{column}|{','.join(map(str, indices))}"
    iid = "iss_" + hashlib.sha256((run_id + signature).encode()).hexdigest()[:12]
    refs = Evidence(
        kind="example",
        label="Affected row references",
        detail="Stable row locators for up to eight affected rows; affected_rows contains the full measured count.",
        metrics={"affected_rows": len(indices)},
        examples=[row_id(i) for i in indices[:8]],
    )
    if "possible cause" not in description.casefold():
        description += " Possible causes (unconfirmed hypotheses): " + " ".join(diagnosis)
    hypotheses = []
    for number, statement in enumerate(diagnosis, 1):
        hid = "hyp_" + hashlib.sha256(f"{iid}|{number}|{statement}".encode()).hexdigest()[:10]
        hypotheses.append(
            DiagnosisHypothesis(
                id=hid,
                statement=statement.removeprefix("Possible "),
                evidence_labels=[e.label for e in evidence],
            )
        )
    return Issue(
        id=iid,
        category=category,
        title=title,
        column=column,
        description=description,
        affected_rows=len(indices),
        affected_cells=cells,
        affected_row_ids=[row_id(i) for i in indices],
        evidence=[*evidence, refs],
        disposition=disposition,
        diagnosis=hypotheses,
    )


def _proposal(
    run_id: str,
    issue: Issue,
    op: Operation,
    column: str | None,
    risk: RiskClass,
    title: str,
    explanation: str,
    params: OperationParams,
    source: ProposalSource = ProposalSource.rule,
) -> Proposal:
    pid = "prp_" + hashlib.sha256((run_id + issue.id + op.value).encode()).hexdigest()[:12]
    return Proposal(
        id=pid,
        issue_ids=[issue.id],
        op=op,
        column=column,
        risk_class=risk,
        source=source,
        title=title,
        explanation=explanation,
        params=params,
        evidence=issue.evidence,
        confidence=Confidence(
            value=None, caveat="No calibrated confidence method is implemented in this milestone."
        ),
        simulation=None,
        gate=None,
    )


def analyze_frame(
    run_id: str, frame: pd.DataFrame, original_size: int
) -> tuple[DatasetProfile, list[Issue], list[Proposal]]:
    prof = profile(frame, original_size)
    issues: list[Issue] = []
    proposals: list[Proposal] = []
    structural_cols = [c for c in frame.columns if str(c).startswith("__datafix_extra_")]
    physical = (
        frame["__datafix_physical_line"].astype(str).tolist()
        if "__datafix_physical_line" in frame.columns
        else [str(i + 2) for i in range(len(frame))]
    )
    structure_rows = []
    extra_columns = {column: frame[column].tolist() for column in structural_cols}
    actual_fields = (
        frame["__datafix_actual_fields"].tolist()
        if "__datafix_actual_fields" in frame.columns
        else [len(prof.columns)] * len(frame)
    )
    raw_rows = (
        frame["__datafix_raw_row"].tolist()
        if "__datafix_raw_row" in frame.columns
        else ["[]"] * len(frame)
    )
    for i, actual_value in enumerate(actual_fields):
        extra_values = [
            str(extra_columns[c][i])
            for c in structural_cols
            if not _is_missing(extra_columns[c][i]) and str(extra_columns[c][i]) != ""
        ]
        actual = int(actual_value)
        if actual != len(prof.columns):
            structure_rows.append((i, extra_values, actual))
    if structure_rows:
        indices = [i for i, _, _ in structure_rows]
        examples = []
        expected = len(prof.columns)
        for i, values, actual in structure_rows[:5]:
            raw_row = str(raw_rows[i])
            missing = max(0, expected - actual)
            extra = max(0, actual - expected)
            missing_cols = [c.name for c in prof.columns[-missing:]] if missing else []
            examples.append(
                f"line {physical[i]} ({row_id(i)}): expected={expected}, actual={actual}, missing={missing}, extra={extra}, missing_columns={missing_cols!r}, extra_values={values!r}, original_row={raw_row}"
            )
        issue = _issue(
            run_id,
            IssueCategory.row_structure_mismatch,
            "CSV rows have inconsistent field counts",
            None,
            "Records differ from the header width. Short records were padded with nulls and extra values were preserved in structural metadata; no values were inferred or discarded.",
            indices,
            sum(abs(actual - expected) for _, _, actual in structure_rows),
            [
                Evidence(
                    kind="rule",
                    label="CSV row width",
                    detail="Each physical record was parsed and compared with the declared header width.",
                    metrics={"expected_fields": expected, "affected_rows": len(indices)},
                    examples=examples,
                )
            ],
            ["Possible malformed export or truncated source record."],
            IssueDisposition.repair_proposed,
        )
        issues.append(issue)
        # One human-approved typed edit per overflow record. Never discard
        # overflow silently and never map it to a guessed business column.
        for i, values, actual in structure_rows:
            for col in structural_cols:
                value = str(extra_columns[col][i])
                if value and value != "<NA>":
                    params = ManualEditParams(
                        op="manual_edit",
                        row_id=row_id(i),
                        expected_value=value,
                        value="",
                        reason="Remove an unexpected CSV field after human review",
                    )
                    proposal = _proposal(
                        run_id,
                        issue,
                        Operation.manual_edit,
                        col,
                        RiskClass.destructive,
                        "Remove unexpected CSV field after review",
                        "This value has no justified destination. Removal requires human approval and is recorded in the operation log.",
                        params,
                        ProposalSource.human,
                    )
                    proposal = proposal.model_copy(
                        update={
                            "id": "prp_"
                            + hashlib.sha256(
                                f"{run_id}|{issue.id}|{row_id(i)}|{col}".encode()
                            ).hexdigest()[:12]
                        }
                    )
                    proposals.append(proposal)
    # Missing values and placeholders are grouped by placeholder token per column.
    analysis_columns = [c for c in frame.columns if not str(c).startswith("__datafix_")]
    frame = frame.loc[:, analysis_columns]
    for col in frame.columns:
        s = frame[col].fillna("").astype(str)
        missing: list[int] = []
        placeholders: dict[str, list[int]] = defaultdict(list)
        for i, v in enumerate(s):
            stripped = v.strip()
            key = stripped.casefold()
            if not stripped:
                missing.append(i)
            elif key in PLACEHOLDERS:
                missing.append(i)
                placeholders[key].append(i)
        if missing:
            ev = [
                Evidence(
                    kind=EvidenceKind.record_count,
                    label="Missing or placeholder cells",
                    detail="Measured blank and configured placeholder values in this column.",
                    metrics={
                        "count": len(missing),
                        "percentage": 100 * len(missing) / max(1, len(frame)),
                    },
                    examples=[str(s.iloc[i])[:80] for i in missing[:5]],
                )
            ]
            ev += [
                Evidence(
                    kind="example",
                    label="Placeholder tokens",
                    detail="Observed candidate missing-value markers; mapping these to null remains a proposal.",
                    metrics={"count": len(ids)},
                    examples=[str(s.iloc[ids[0]])[:80]],
                )
                for token, ids in list(placeholders.items())[:5]
            ]
            issue = _issue(
                run_id,
                IssueCategory.missing,
                "Missing or placeholder values",
                col,
                f"Observed {len(missing)} blank or configured placeholder values. Possible causes include incomplete source records or upstream import conventions; optionality is unknown.",
                missing,
                len(missing),
                ev,
                [
                    "Possible incomplete source records.",
                    "Possible upstream export or import conventions.",
                ],
                IssueDisposition.repair_proposed if placeholders else IssueDisposition.flagged_only,
            )
            issues.append(issue)
            if placeholders:
                ids = [row_id(i) for i in missing if s.iloc[i].strip().casefold() in PLACEHOLDERS]
                proposals.append(
                    _proposal(
                        run_id,
                        issue,
                        Operation.set_null,
                        col,
                        RiskClass.value_substitution,
                        "Convert configured placeholders to null",
                        "The values exactly match configured placeholder tokens; no imputation is proposed.",
                        SetNullParams(
                            op="set_null", placeholder_values=sorted(placeholders), row_ids=ids
                        ),
                    )
                )
    # Exact duplicate rows.
    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i, row in enumerate(frame.itertuples(index=False, name=None)):
        groups[tuple(str(x) for x in row)].append(i)
    dgroups = [ids for ids in groups.values() if len(ids) > 1]
    if dgroups:
        indices = [i for g in dgroups for i in g[1:]]
        issue = _issue(
            run_id,
            IssueCategory.duplicate,
            "Exact duplicate records",
            None,
            f"Found {len(indices)} rows matching an earlier complete record. Possible causes include repeated imports or duplicate entry; records are preserved.",
            indices,
            len(indices) * frame.shape[1],
            [
                Evidence(
                    kind=EvidenceKind.record_count,
                    label="Duplicate rows",
                    detail="Exact row equality across all columns.",
                    metrics={"duplicate_rows": len(indices), "groups": len(dgroups)},
                    examples=[row_id(i) for i in indices[:5]],
                )
            ],
            ["Possible repeated import.", "Possible duplicate data entry."],
            IssueDisposition.repair_proposed,
        )
        issues.append(issue)
        proposals.append(
            _proposal(
                run_id,
                issue,
                Operation.drop_exact_dupes,
                None,
                RiskClass.destructive,
                "Review exact duplicate rows",
                "Removing rows is destructive and requires future review; no rows were removed.",
                DropExactDupesParams(
                    op="drop_exact_dupes",
                    duplicate_row_groups=[[row_id(i) for i in g] for g in dgroups],
                ),
            )
        )
    # Invalid formats and safe date normalization candidates.
    for col in frame.columns:
        s = frame[col].fillna("").astype(str)
        cname = col.casefold()
        indices = []
        date_values = {}
        date_formats_by_row = {}
        ambiguous = []
        parsed_formats = set()
        date_candidate = "date" in cname or cname.endswith(("_at", "_on"))
        if date_candidate:
            nonempty = [
                (i, v.strip())
                for i, v in enumerate(s)
                if v.strip() and v.strip().casefold() not in PLACEHOLDERS
            ]
            for i, v in nonempty:
                dt, amb = parse_date(v)
                if dt is None:
                    indices.append(i)
                elif amb:
                    ambiguous.append(i)
                else:
                    date_values[row_id(i)] = dt.strftime("%Y-%m-%d")
                    for fmt in DATE_FORMATS:
                        try:
                            datetime.strptime(v, fmt)
                            parsed_formats.add(fmt)
                            date_formats_by_row[row_id(i)] = fmt
                            break
                        except ValueError:
                            pass
            if indices or ambiguous or len(parsed_formats) > 1:
                changed_format_rows = []
                normalization_values = date_values
                if len(parsed_formats) > 1 and not indices and not ambiguous:
                    format_counts = Counter(date_formats_by_row.values())
                    canonical_format = sorted(
                        format_counts, key=lambda fmt: (-format_counts[fmt], fmt)
                    )[0]
                    changed_format_rows = [
                        int(rid.split("_")[1]) - 1
                        for rid, fmt in date_formats_by_row.items()
                        if fmt != canonical_format
                    ]
                    normalization_values = {
                        rid: value
                        for rid, value in date_values.items()
                        if date_formats_by_row[rid] != canonical_format
                    }
                affected = sorted(set(indices + ambiguous + changed_format_rows))
                title = (
                    "Invalid or ambiguous date values"
                    if indices or ambiguous
                    else "Mixed date representations"
                )
                detail = (
                    "Some date-like values could not be parsed."
                    if indices
                    else (
                        "Some values have more than one valid interpretation; locale is not inferred."
                        if ambiguous
                        else "Multiple date formats represent otherwise parseable values."
                    )
                )
                evidence = [
                    Evidence(
                        kind="rule",
                        label="Date parsing",
                        detail=detail,
                        metrics={
                            "invalid_count": len(indices),
                            "ambiguous_count": len(ambiguous),
                            "recognized_formats": len(parsed_formats),
                        },
                        examples=[_safe_example(col, s.iloc[i]) for i in (indices + ambiguous)[:5]],
                    )
                ]
                issue = _issue(
                    run_id,
                    IssueCategory.invalid_format,
                    title,
                    col,
                    f"{detail} Possible causes include mixed regional formatting; no locale is inferred.",
                    affected,
                    len(affected),
                    evidence,
                    [
                        "Possible regional import differences.",
                        "Possible manual formatting inconsistency.",
                    ],
                    IssueDisposition.repair_proposed
                    if len(parsed_formats) > 1 and not indices and not ambiguous
                    else IssueDisposition.flagged_only,
                )
                issues.append(issue)
                if len(parsed_formats) > 1 and not indices and not ambiguous:
                    proposals.append(
                        _proposal(
                            run_id,
                            issue,
                            Operation.normalize_date,
                            col,
                            RiskClass.format_only,
                            "Normalize unambiguous dates",
                            "All observed values parse to one date without locale ambiguity.",
                            NormalizeDateParams(
                                op="normalize_date",
                                target_format="YYYY-MM-DD",
                                row_values=normalization_values,
                            ),
                        )
                    )
                elif ambiguous:
                    # Return an explicit abstention proposal so clients can show
                    # the refused lane and evidence; an empty allow-listed plan
                    # cannot change the ambiguous values.
                    proposals.append(
                        _proposal(
                            run_id,
                            issue,
                            Operation.normalize_date,
                            col,
                            RiskClass.format_only,
                            "Do not infer ambiguous date formats",
                            "The values have multiple valid interpretations and no locale was supplied; the proposal intentionally contains no changes.",
                            NormalizeDateParams(
                                op="normalize_date", target_format="YYYY-MM-DD", row_values={}
                            ),
                        )
                    )
        elif "email" in cname:
            bad = [
                i
                for i, v in enumerate(s)
                if v.strip()
                and v.strip().casefold() not in PLACEHOLDERS
                and not EMAIL.fullmatch(v.strip())
            ]
            if bad:
                issue = _issue(
                    run_id,
                    IssueCategory.invalid_format,
                    "Invalid email format",
                    col,
                    f"Found {len(bad)} non-empty values that fail a conservative email syntax check.",
                    bad,
                    len(bad),
                    [
                        Evidence(
                            kind="rule",
                            label="Email syntax",
                            detail="Value does not match the conservative email syntax rule.",
                            metrics={"invalid_count": len(bad)},
                            examples=[_safe_example(col, s.iloc[i]) for i in bad[:5]],
                        )
                    ],
                    ["Possible typing error.", "Possible field containing non-email identifiers."],
                    IssueDisposition.flagged_only,
                )
                issues.append(issue)
        else:
            dtype, _, ratio = infer_column(s, col)
            if dtype == "number" and ratio is not None and ratio < 1:
                bad = [i for i, v in enumerate(s) if v.strip() and _float(v) is None]
                if bad:
                    issue = _issue(
                        run_id,
                        IssueCategory.invalid_format,
                        "Invalid numeric representations",
                        col,
                        f"Found {len(bad)} values in a mostly numeric column that cannot be parsed as numbers.",
                        bad,
                        len(bad),
                        [
                            Evidence(
                                kind="rule",
                                label="Numeric parsing",
                                detail="At least 80% of non-empty values parse numerically; listed values do not.",
                                metrics={"parse_ratio": ratio, "invalid_count": len(bad)},
                                examples=[_safe_example(col, s.iloc[i]) for i in bad[:5]],
                            )
                        ],
                        [
                            "Possible non-numeric text in a numeric field.",
                            "Possible column containing mixed meanings.",
                        ],
                        IssueDisposition.flagged_only,
                    )
                    issues.append(issue)
    # Trim-only whitespace normalization.
    for col in frame.columns:
        s = frame[col].fillna("").astype(str)
        bad = [i for i, v in enumerate(s) if v and v.strip() and v != v.strip()]
        if bad:
            vals = {row_id(i): s.iloc[i].strip() for i in bad}
            issue = _issue(
                run_id,
                IssueCategory.inconsistent,
                "Leading or trailing whitespace",
                col,
                f"Found {len(bad)} non-empty values with removable boundary whitespace.",
                bad,
                len(bad),
                [
                    Evidence(
                        kind="example",
                        label="Whitespace examples",
                        detail="Trimmed text preserves the non-whitespace content.",
                        metrics={"affected_count": len(bad)},
                        examples=[_safe_example(col, s.iloc[i]) for i in bad[:5]],
                    )
                ],
                ["Possible inconsistent copy-and-paste or export formatting."],
                IssueDisposition.repair_proposed,
            )
            issues.append(issue)
            proposals.append(
                _proposal(
                    run_id,
                    issue,
                    Operation.trim_text,
                    col,
                    RiskClass.format_only,
                    "Trim boundary whitespace",
                    "Removing leading and trailing whitespace preserves the observed text content.",
                    TrimTextParams(op="trim_text", row_values=vals),
                )
            )
    # Category spelling/case candidates: only exact normalized equivalents proposed.
    for col in frame.columns:
        s = frame[col].fillna("").astype(str)
        values = [v for v in s if v.strip() and v.strip().casefold() not in PLACEHOLDERS]
        inferred, _, _ = infer_column(s, str(col))
        # Similarity is only meaningful for low-cardinality categorical fields;
        # running it on emails, identifiers, dates or free text creates noise.
        if inferred != "category":
            continue
        if len(values) < 2:
            continue
        groups: dict[str, list[str]] = defaultdict(list)
        for v in values:
            groups[re.sub(r"\s+", " ", v.strip()).casefold()].append(v)
        variant_groups = [list(dict.fromkeys(g)) for g in groups.values() if len(set(g)) > 1]
        for vg in variant_groups:
            freq = Counter(values)
            canonical = sorted(set(vg), key=lambda v: (-freq[v], v.casefold(), v))[0]
            mapping = {v: canonical for v in vg if v != canonical}
            indices = [i for i, v in enumerate(s) if v in mapping]
            issue = _issue(
                run_id,
                IssueCategory.inconsistent,
                "Equivalent category formatting variants",
                col,
                "Observed values differ only by case or whitespace; mapping to the most frequent observed spelling is a candidate, not applied.",
                indices,
                len(indices),
                [
                    Evidence(
                        kind="example",
                        label="Observed variants",
                        detail="Variants normalize to the same case-folded, whitespace-collapsed value.",
                        metrics={"variant_count": len(vg), "canonical_frequency": freq[canonical]},
                        examples=[_safe_example(col, v) for v in vg[:5]],
                    )
                ],
                ["Possible inconsistent naming or whitespace conventions."],
                IssueDisposition.repair_proposed,
            )
            issues.append(issue)
            proposals.append(
                _proposal(
                    run_id,
                    issue,
                    Operation.map_values,
                    col,
                    RiskClass.value_substitution,
                    "Map equivalent category spellings",
                    "The destination is an existing observed category and variants differ only by case or whitespace.",
                    MapValuesParams(op="map_values", mapping=mapping),
                )
            )
        # Similar but not equivalent values are reported as candidates only.
        distinct = sorted(set(values))
        pairs = []
        for i, a in enumerate(distinct):
            for b in distinct[i + 1 :]:
                if a.strip().casefold() == b.strip().casefold():
                    continue
                sim = SequenceMatcher(None, a.strip().casefold(), b.strip().casefold()).ratio()
                if 0.88 <= sim < 1.0:
                    pairs.append((a, b, sim))
        if pairs:
            example_pairs = pairs[:5]
            # Attribute affected records to the lower-frequency member of each
            # candidate pair. Common canonical values are examples, not damaged
            # rows, and must not inflate the blast radius.
            frequency = Counter(values)
            candidate_values = set()
            for a, b, _ in example_pairs:
                if frequency[a] < frequency[b]:
                    candidate_values.add(a)
                elif frequency[b] < frequency[a]:
                    candidate_values.add(b)
                else:
                    candidate_values.update((a, b))
            indices = [i for i, v in enumerate(s) if v in candidate_values]
            issue = _issue(
                run_id,
                IssueCategory.inconsistent,
                "Similar but distinct category values",
                col,
                "Text similarity identified review candidates; similarity alone does not establish equivalence, so no mapping is proposed.",
                indices,
                len(indices),
                [
                    Evidence(
                        kind="statistic",
                        label="String similarity candidates",
                        detail="Sequence similarity is a candidate-generation heuristic, not a probability or identity proof.",
                        metrics={"candidate_pairs": len(pairs)},
                        examples=[
                            f"{_safe_example(col, a)} ↔ {_safe_example(col, b)} ({score:.2f})"
                            for a, b, score in example_pairs
                        ],
                    )
                ],
                ["Possible spelling variation; semantic equivalence is unconfirmed."],
                IssueDisposition.flagged_only,
            )
            issues.append(issue)
    # IQR outliers; retained without replacement proposals.
    for col in frame.columns:
        dtype, nums, _ = infer_column(frame[col].fillna("").astype(str), col)
        if dtype != "number" or len(nums) < 8 or len(set(nums)) < 4:
            continue
        q1, q3 = np.quantile(nums, [0.25, 0.75])
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        vals = frame[col].fillna("").astype(str)
        bad = [
            i
            for i, v in enumerate(vals)
            if _float(v) is not None and (_float(v) < lo or _float(v) > hi)
        ]
        if bad:
            issue = _issue(
                run_id,
                IssueCategory.anomaly,
                "IQR statistical outliers",
                col,
                f"Found {len(bad)} observations outside the Tukey IQR fences. Statistical outliers may be legitimate and are preserved.",
                bad,
                len(bad),
                [
                    Evidence(
                        kind="statistic",
                        label="IQR outlier detection",
                        detail="Bounds are Q1 − 1.5×IQR and Q3 + 1.5×IQR.",
                        metrics={
                            "q1": float(q1),
                            "q3": float(q3),
                            "iqr": float(iqr),
                            "lower_bound": float(lo),
                            "upper_bound": float(hi),
                        },
                        examples=[vals.iloc[i][:80] for i in bad[:5]],
                    )
                ],
                ["Possible unit mismatch or entry error.", "Possible legitimate extreme value."],
                IssueDisposition.flagged_only,
            )
            issues.append(issue)
    # Explicit, structurally recognizable cross-column rules only.
    lower = {str(c).casefold(): c for c in frame.columns}
    if {"quantity", "unit_price", "total"}.issubset(lower):
        q, p, t = (lower[x] for x in ("quantity", "unit_price", "total"))
        bad = []
        facts = []
        for i in range(len(frame)):
            qv, pv, tv = (_float(str(frame.iloc[i][c])) for c in (q, p, t))
            if None not in (qv, pv, tv) and not math.isclose(
                qv * pv, tv, rel_tol=1e-6, abs_tol=1e-6
            ):
                bad.append(i)
                facts.append((qv, pv, tv))
        if bad:
            ev = [
                Evidence(
                    kind="rule",
                    label="total = quantity × unit_price",
                    detail="Explicit arithmetic relationship inferred from exact conventional column names; no correction side is assumed.",
                    metrics={"violations": len(bad)},
                    examples=[
                        f"{frame.iloc[i][q]} × {frame.iloc[i][p]} != {frame.iloc[i][t]}"
                        for i in bad[:5]
                    ],
                )
            ]
            issues.append(
                _issue(
                    run_id,
                    IssueCategory.relationship,
                    "Cross-column arithmetic inconsistency",
                    None,
                    "The explicit quantity × unit_price relationship does not equal total. Which source value is wrong is unknown; values are preserved.",
                    bad,
                    len(bad) * 3,
                    ev,
                    [
                        "Possible quantity, unit price or total entry error.",
                        "Possible tax/discount convention not represented by these columns.",
                    ],
                    IssueDisposition.flagged_only,
                )
            )
    start = next(
        (c for c in frame.columns if str(c).casefold() in {"start_date", "order_date"}), None
    )
    end = next((c for c in frame.columns if str(c).casefold() in {"end_date", "ship_date"}), None)
    if start and end:
        bad = []
        samples = []
        for i in range(len(frame)):
            a, aa = parse_date(str(frame.iloc[i][start]))
            b, bb = parse_date(str(frame.iloc[i][end]))
            if a and b and not aa and not bb and b < a:
                bad.append(i)
                samples.append(f"{frame.iloc[i][end]} < {frame.iloc[i][start]}")
        if bad:
            issues.append(
                _issue(
                    run_id,
                    IssueCategory.relationship,
                    "End date precedes start date",
                    None,
                    "An unambiguous date ordering rule is violated; no date is changed.",
                    bad,
                    len(bad) * 2,
                    [
                        Evidence(
                            kind="rule",
                            label=f"{end} >= {start}",
                            detail="Both dates parse unambiguously, and the end date precedes the start date.",
                            metrics={"violations": len(bad)},
                            examples=samples[:5],
                        )
                    ],
                    [
                        "Possible date entry error.",
                        "Possible exception to the expected chronology.",
                    ],
                    IssueDisposition.flagged_only,
                )
            )
    # Stable ordering helps repeat-analysis equality.
    issues.sort(key=lambda x: x.id)
    proposals.sort(key=lambda x: x.id)
    return prof, issues, proposals


def create_run(
    filename: str, raw: bytes, worksheet: str | None = None
) -> tuple[RunMetadata, pd.DataFrame]:
    if len(raw) > settings.max_upload_bytes:
        raise InputProblem(
            413,
            "upload_too_large",
            "Upload exceeds the configured size limit.",
            {"limit_bytes": settings.max_upload_bytes},
        )
    parsed = parse_dataset(filename, raw, worksheet)
    frame, headers = parsed.frame, parsed.headers
    meta = RunMetadata(
        id=str(uuid.uuid4()),
        filename=filename.replace("\\", "/").split("/")[-1][:255],
        file_sha256=hashlib.sha256(raw).hexdigest(),
        file_size_bytes=len(raw),
        row_count=len(frame),
        column_count=len(headers),
        status=RunStatus.uploaded,
        created_at=datetime.now(timezone.utc),
        engine_version=settings.engine_version,
        format_metadata=parsed.metadata,
    )
    return meta, frame
