import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main
from app.lifecycle import simulate
from app.main import app
from app.schemas import (
    Confidence,
    Evidence,
    EvidenceKind,
    Issue,
    IssueCategory,
    IssueDisposition,
    Operation,
    Proposal,
    ProposalSource,
    RiskClass,
)
from app.services import InputProblem, analyze_frame, parse_csv
from app.storage import ConcurrentWriteError, RunStorage, SupabaseStorage, build_storage

FIX = Path(__file__).parent / "fixtures"
client = TestClient(app)


@pytest.fixture(scope="module")
def generated():
    import runpy

    runpy.run_path(str(FIX / "generate_fixture.py"))
    return (FIX / "datafix_dirty.csv").read_bytes()


def test_fixture_manifest_covers_six_detector_categories(generated):
    data = json.loads((FIX / "datafix_error_manifest.json").read_text())
    assert {x["expected_detector"] for x in data["errors"]} >= {
        "missing",
        "duplicate",
        "invalid_format",
        "inconsistent",
        "anomaly",
        "relationship",
    }


def test_ingestion_valid_utf8_and_bom():
    df, _ = parse_csv(b"a,b\n1,2\n")
    assert df.shape == (1, 2)
    assert parse_csv(b"\xef\xbb\xbfa,b\n1,2\n")[0].shape == (1, 2)


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"", "empty_file"),
        (b"a,a\n1,2\n", "duplicate_headers"),
        (b"a\n\x81\n", "unsupported_encoding"),
    ],
)
def test_ingestion_rejects_bad_csv(raw, code):
    with pytest.raises(InputProblem) as exc:
        parse_csv(raw)
    assert exc.value.code == code


def test_recoverable_row_widths_preserve_extras_and_pad_missing_fields():
    raw = (
        b"id,name,status,phone\n1016,Alice,Active,555\n"
        b"1017,Bob,Active,556,EXTRA_COL_DATA\n1018,Carol\n1019,Dana,Active\n"
    )
    frame, headers = parse_csv(raw)
    assert headers == ["id", "name", "status", "phone"]
    assert frame.shape[0] == 4
    assert frame.iloc[1]["__datafix_extra_1"] == "EXTRA_COL_DATA"
    assert frame.iloc[2]["status"] == "" and frame.iloc[2]["phone"] == ""
    assert frame.iloc[3]["phone"] == ""
    assert frame.iloc[1]["__datafix_physical_line"] == "3"
    assert frame.iloc[1]["__datafix_actual_fields"] == "5"
    assert json.loads(frame.iloc[1]["__datafix_raw_row"])[-1] == "EXTRA_COL_DATA"
    prof, issues, proposals = analyze_frame("widths", frame, len(raw))
    structural = next(x for x in issues if x.category == IssueCategory.row_structure_mismatch)
    assert structural.affected_rows == 3
    assert any(
        "EXTRA_COL_DATA" in example
        for evidence in structural.evidence
        for example in evidence.examples
    )
    assert any(x.category == IssueCategory.missing and x.column == "status" for x in issues)
    assert any(x.category == IssueCategory.missing and x.column == "phone" for x in issues)
    assert sum(p.op == Operation.manual_edit for p in proposals) == 1
    assert prof.row_count == 4 and prof.column_count == 4


def test_unparseable_quoting_still_rejected():
    with pytest.raises(InputProblem) as exc:
        parse_csv(b'a,b\n1,"unterminated\n')
    assert exc.value.code == "malformed_csv"


@pytest.mark.parametrize(
    "raw", [b"%PDF-1.7\n", b"PK\x03\x04zip payload", b"\xff\xfe\x00\x00binary"]
)
def test_ingestion_rejects_disguised_binary_files(raw):
    with pytest.raises(InputProblem) as exc:
        parse_csv(raw)
    assert exc.value.status in {415, 422}


def test_header_only_is_valid_empty_dataset_and_cell_limit_is_enforced(monkeypatch):
    from types import SimpleNamespace

    import app.services as services

    frame, _ = parse_csv(b"a,b\n")
    assert frame.shape == (0, 2)
    monkeypatch.setattr(
        services, "settings", SimpleNamespace(max_rows=5, max_columns=5, max_cell_chars=3)
    )
    with pytest.raises(InputProblem) as exc:
        parse_csv(b"a\nbig-value\n")
    assert exc.value.code == "cell_too_long"


def test_upload_validation_and_original_preservation(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    response = client.post("/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")})
    assert response.status_code == 201
    meta = response.json()["run"]
    saved = store.get(meta["id"])
    assert saved["original"] == generated
    assert store.get_working(meta["id"])
    assert meta["file_sha256"] == hashlib.sha256(generated).hexdigest()
    restarted = RunStorage(tmp_path)
    assert restarted.get(meta["id"])["original"] == generated
    assert restarted.get_working(meta["id"]) == store.get_working(meta["id"])


def test_structural_repair_approval_apply_verify_undo_reapply_and_export(monkeypatch, tmp_path):
    raw = (
        b"id,name,status,phone\n1016,Alice,Active,555\n"
        b"1017,Bob,Active,556,EXTRA_COL_DATA\n1018,Carol\n"
    )
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post("/api/v1/runs", files={"file": ("widths.csv", raw, "text/csv")})
    assert uploaded.status_code == 201
    assert uploaded.json()["warnings"]
    rid = uploaded.json()["run"]["id"]
    assert store.get(rid)["original"] == raw
    analysis = client.post(f"/api/v1/runs/{rid}/analyze").json()
    structural = next(x for x in analysis["issues"] if x["category"] == "row_structure_mismatch")
    assert structural["affected_rows"] == 2
    assert any(
        "EXTRA_COL_DATA" in e for evidence in structural["evidence"] for e in evidence["examples"]
    )
    heatmap = client.get(f"/api/v1/runs/{rid}/uncertainty?offset=0&limit=5").json()
    assert {x["column"] for x in heatmap["columns"]} == {"id", "name", "status", "phone"}
    proposal = next(x for x in analysis["proposals"] if x["op"] == "manual_edit")
    assert proposal["gate"]["decision"] == "needs_approval"
    unresolved_export = client.get(f"/api/v1/runs/{rid}/export/cleaned")
    assert (
        "EXTRA_COL_DATA" in unresolved_export.text
        and "__unexpected_extra_1" in unresolved_export.text.splitlines()[0]
    )
    reviewed = client.post(
        f"/api/v1/runs/{rid}/decisions",
        json={"decisions": [{"proposal_id": proposal["id"], "action": "approve"}]},
    )
    assert reviewed.status_code == 200
    applied = client.post(f"/api/v1/runs/{rid}/apply")
    assert applied.status_code == 200 and len(applied.json()["applied_operations"]) == 1
    assert client.post(f"/api/v1/runs/{rid}/verify").json()["replay"]["match"] is True
    log = client.get(f"/api/v1/runs/{rid}/export/log").json()
    assert any(
        x.get("before") == "EXTRA_COL_DATA" and x.get("extra_field_position") == 5 for x in log
    )
    assert client.get(f"/api/v1/runs/{rid}/operations").status_code == 200
    cleaned = client.get(f"/api/v1/runs/{rid}/export/cleaned")
    assert cleaned.status_code == 200 and "EXTRA_COL_DATA" not in cleaned.text
    assert len(cleaned.text.splitlines()[0].split(",")) == 4
    for artifact in ("report", "recipe"):
        response = client.get(f"/api/v1/runs/{rid}/export/{artifact}")
        assert response.status_code == 200 and json.loads(response.text)
    passport = client.get(f"/api/v1/runs/{rid}/export/passport")
    assert passport.status_code == 200 and json.loads(passport.text)["output_column_count"] == 4
    op_id = applied.json()["applied_operations"][0]["op_id"]
    assert client.post(f"/api/v1/runs/{rid}/undo/{op_id}").status_code == 200
    assert client.post(f"/api/v1/runs/{rid}/verify").json()["replay"]["match"] is True
    remaining = client.post(f"/api/v1/runs/{rid}/analyze").json()
    assert any(
        x["category"] == "missing" and x["column"] in {"status", "phone"}
        for x in remaining["issues"]
    )
    assert client.post(f"/api/v1/runs/{rid}/apply").json()["status"] == "applied"
    assert client.post(f"/api/v1/runs/{rid}/verify").json()["replay"]["match"] is True
    assert store.get(rid)["original"] == raw


def test_upload_strips_path_components_and_cors_preflight():
    response = client.post(
        "/api/v1/runs", files={"file": ("..\\..\\private.csv", b"a\n1\n", "text/csv")}
    )
    assert response.status_code == 201 and response.json()["run"]["filename"] == "private.csv"
    preflight = client.options(
        "/api/v1/runs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_upload_rejects_extension():
    response = client.post("/api/v1/runs", files={"file": ("x.txt", b"a\n1\n")})
    assert response.status_code == 415
    assert set(response.json()) == {"code", "message", "details", "request_id"}


def test_upload_rejects_oversized_file():
    response = client.post(
        "/api/v1/runs", files={"file": ("large.csv", b"x" * (5 * 1024 * 1024 + 1), "text/csv")}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"


def test_row_and_column_limits(monkeypatch):
    from types import SimpleNamespace

    import app.services as services

    monkeypatch.setattr(
        services,
        "settings",
        SimpleNamespace(max_rows=1, max_columns=1, max_upload_bytes=1000, engine_version="0.1.0"),
    )
    with pytest.raises(InputProblem) as row_error:
        parse_csv(b"a\n1\n2\n")
    assert row_error.value.code == "row_limit_exceeded"
    with pytest.raises(InputProblem) as col_error:
        parse_csv(b"a,b\n1,2\n")
    assert col_error.value.code == "column_limit_exceeded"


def test_profile_and_real_detectors(generated):
    frame, _ = parse_csv(generated)
    profile, issues, proposals = analyze_frame("r1", frame, len(generated))
    cats = {i.category for i in issues}
    assert profile.row_count == 31 and profile.column_count == 10
    assert {
        IssueCategory.missing,
        IssueCategory.duplicate,
        IssueCategory.invalid_format,
        IssueCategory.inconsistent,
        IssueCategory.anomaly,
        IssueCategory.relationship,
    } <= cats
    assert all(i.evidence for i in issues)
    assert all(p.simulation is None and p.gate is None for p in proposals)
    assert all(p.confidence.value is None for p in proposals)
    assert any(p.op == Operation.drop_exact_dupes for p in proposals)
    assert any(p.op == Operation.normalize_date and p.column == "ship_date" for p in proposals)
    mixed = next(i for i in issues if i.title == "Mixed date representations")
    refs = next(e for e in mixed.evidence if e.label == "Affected row references")
    assert mixed.affected_rows > 0 and "row_12" in refs.examples
    assert any(i.title == "Invalid numeric representations" for i in issues)
    assert any(i.category == IssueCategory.missing and i.column == "note" for i in issues)
    assert not any(p.op == Operation.trim_text and p.column == "note" for p in proposals)
    anomaly = next(i for i in issues if i.category == IssueCategory.anomaly)
    assert not any(anomaly.id in p.issue_ids for p in proposals)
    assert any(i.title == "End date precedes start date" for i in issues)


def test_detector_avoids_merge_of_near_category_and_ambiguous_dates(generated):
    frame, _ = parse_csv(generated)
    _, issues, proposals = analyze_frame("r2", frame, len(generated))
    near = next(i for i in issues if i.title == "Similar but distinct category values")
    assert near.disposition.value == "flagged_only"
    amb = next(i for i in issues if "ambiguous" in i.title.lower())
    abstention = next(
        p for p in proposals if p.op == Operation.normalize_date and amb.id in p.issue_ids
    )
    assert abstention.params.row_values == {}


def test_ambiguous_date_is_an_explicit_refused_proposal(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("ambiguous.csv", generated, "text/csv")}
    ).json()["run"]
    analysis = client.post(f"/api/v1/runs/{uploaded['id']}/analyze").json()
    ambiguous = next(i for i in analysis["issues"] if "ambiguous" in i["title"].lower())
    proposal = next(p for p in analysis["proposals"] if ambiguous["id"] in p["issue_ids"])
    assert proposal["gate"]["decision"] == "refused"
    assert proposal["gate"]["refusal_kind"] == "insufficient_evidence"
    rejected = client.post(
        f"/api/v1/runs/{uploaded['id']}/decisions",
        json={"decisions": [{"proposal_id": proposal["id"], "action": "approve"}]},
    )
    assert rejected.status_code == 409


def test_profile_statistics_are_measured(generated):
    frame, _ = parse_csv(generated)
    profile, _, _ = analyze_frame("stats", frame, len(generated))
    price = next(c for c in profile.columns if c.name == "unit_price")
    assert price.minimum == 100 and price.maximum == 999999
    assert (
        price.mean is not None and price.median is not None and price.standard_deviation is not None
    )
    assert profile.duplicate_record_count == 1
    assert profile.total_missing_cells == 2


def test_analysis_endpoint_actual_and_repeatable(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("datafix_dirty.csv", generated, "text/csv")}
    ).json()["run"]
    one = client.post(f"/api/v1/runs/{uploaded['id']}/analyze")
    two = client.post(f"/api/v1/runs/{uploaded['id']}/analyze")
    assert one.status_code == two.status_code == 200
    assert one.json() == two.json()
    assert one.json()["profile"]["row_count"] == 31
    assert one.json()["summary"]["issue_count"] > 0
    assert one.json()["summary"]["auto_apply_count"] > 0
    assert (
        sum(
            one.json()["summary"][key]
            for key in ("auto_apply_count", "needs_approval_count", "refused_count")
        )
        == one.json()["summary"]["proposal_count"]
    )
    assert all(
        p["simulation"] is not None and p["gate"] is not None for p in one.json()["proposals"]
    )


def test_unknown_run_error_envelope():
    r = client.post("/api/v1/runs/unknown/analyze")
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "details", "request_id"}


def test_openapi_documents_endpoints():
    spec = app.openapi()
    assert "/api/v1/runs" in spec["paths"]
    assert "/api/v1/runs/{run_id}/analyze" in spec["paths"]
    upload = spec["paths"]["/api/v1/runs"]["post"]
    assert "multipart/form-data" in upload["requestBody"]["content"]
    assert "201" in upload["responses"] and "413" in upload["responses"]
    proposal = spec["components"]["schemas"]["Proposal"]
    assert "simulation" in proposal["properties"] and "gate" in proposal["properties"]


def test_rippleguard_fingerprints_and_simulation_preserve_original(
    monkeypatch, tmp_path, generated
):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")}
    ).json()["run"]
    response = client.post(f"/api/v1/runs/{uploaded['id']}/analyze")
    assert response.status_code == 200
    body = response.json()
    city = next(
        p
        for p in body["proposals"]
        if p["column"] == "city"
        and any(
            m["metric"] == "distinct_count" and m["before"] != m["after"]
            for m in p["simulation"]["impact"]["direct_metrics"]
        )
    )
    impact = city["simulation"]["impact"]
    assert impact["direct_cells"] == 1 and impact["direct_row_ids"] == ["row_5"]
    assert any(
        m["metric"] == "distinct_count" and m["before"] != m["after"]
        for m in impact["direct_metrics"]
    )
    assert impact["invariants"] and all(
        x["status"] in {"pass", "fail", "skipped"} for x in impact["invariants"]
    )
    duplicate = next(p for p in body["proposals"] if p["op"] == "drop_exact_dupes")
    assert duplicate["simulation"]["impact"]["direct_row_ids"] == ["row_31"]
    assert duplicate["simulation"]["rows_removed"] == 1
    date_proposal = next(p for p in body["proposals"] if p["column"] == "ship_date")
    assert any(
        m["metric"] == "business_rule_violations"
        for m in date_proposal["simulation"]["impact"]["indirect_metrics"]
    )
    assert date_proposal["simulation"]["impact"]["affected_dependency_checks"]
    assert store.get(uploaded["id"])["original"] == generated
    issue = body["issues"][0]
    assert issue["pattern"]["fingerprint_id"].startswith("fp_")
    assert "user1@example.test" not in json.dumps(issue["pattern"])


def test_rippleguard_reports_aggregate_drift_and_refuses_threshold_breach():
    frame = pd.DataFrame({"id": ["a", "b", "c"], "amount": ["10", "20", "30"]}, dtype="string")
    issue = Issue(
        id="i1",
        category=IssueCategory.anomaly,
        title="Amount requires review",
        column="amount",
        description="Measured synthetic issue",
        affected_rows=1,
        affected_cells=1,
        affected_row_ids=["row_2"],
        evidence=[
            Evidence(kind=EvidenceKind.statistic, label="synthetic", detail="controlled unit test")
        ],
        disposition=IssueDisposition.flagged_only,
    )
    proposal = Proposal(
        id="p1",
        issue_ids=["i1"],
        op=Operation.manual_edit,
        column="amount",
        risk_class=RiskClass.value_substitution,
        source=ProposalSource.rule,
        title="Manual amount correction",
        explanation="test",
        params={
            "op": "manual_edit",
            "row_id": "row_2",
            "expected_value": "20",
            "value": "25",
            "reason": "synthetic test",
        },
        evidence=[],
        confidence=Confidence(),
        simulation=None,
        gate=None,
    )
    simulation, gate = simulate(frame, proposal, [issue], 64)
    metric = next(x for x in simulation.impact.direct_metrics if x.metric == "sum")
    assert metric.before == 60 and metric.after == 65
    assert gate.decision == "refused"
    assert frame.iloc[1]["amount"] == "20"


def test_manual_edit_rechecks_gate_and_enforces_range_and_stale_value(
    monkeypatch, tmp_path, generated
):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")}
    ).json()["run"]
    rid = uploaded["id"]
    analysis = client.post(f"/api/v1/runs/{rid}/analyze").json()
    proposal = next(
        p
        for p in analysis["proposals"]
        if p["column"] == "city" and p["gate"]["decision"] == "needs_approval"
    )
    data = {
        "row_id": "row_5",
        "column": "city",
        "original_value": "BENGALURU ",
        "edited_value": "Bengaluru",
        "reason": "Use existing canonical category",
    }
    edited = client.post(f"/api/v1/runs/{rid}/proposals/{proposal['id']}/edit", json=data)
    assert edited.status_code == 200
    payload = edited.json()["proposal"]
    assert payload["version"] == 2 and payload["status"] == "edited_pending_reapproval"
    assert payload["gate"]["decision"] == "needs_approval"
    assert payload["simulation"]["impact"]["direct_cells"] == 1
    stale = client.post(
        f"/api/v1/runs/{rid}/proposals/{proposal['id']}/edit",
        json={**data, "original_value": "wrong"},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "stale_original_value"
    invalid = client.post(
        f"/api/v1/runs/{rid}/proposals/{proposal['id']}/edit",
        json={**data, "edited_value": "not-an-existing-category"},
    )
    assert invalid.status_code == 422
    refused = next(p for p in analysis["proposals"] if p["gate"]["decision"] == "refused")
    blocked = client.post(f"/api/v1/runs/{rid}/proposals/{refused['id']}/edit", json=data)
    assert blocked.status_code == 409
    decision = client.post(
        f"/api/v1/runs/{rid}/decisions",
        json={"decisions": [{"proposal_id": proposal["id"], "action": "approve"}]},
    )
    assert decision.status_code == 200
    applied = client.post(f"/api/v1/runs/{rid}/apply")
    assert applied.status_code == 200 and applied.json()["status"] == "applied"
    assert any(x["proposal_id"] == proposal["id"] for x in applied.json()["applied_operations"])
    verification = client.post(f"/api/v1/runs/{rid}/verify")
    assert verification.status_code == 200 and verification.json()["replay"]["match"] is True
    assert store.list_verifications(rid)[-1]["result"]["replay"]["match"] is True
    passport = client.get(f"/api/v1/runs/{rid}/export/passport")
    assert passport.status_code == 200
    passport_data = passport.json()
    assert passport_data["verification_status"] == "verified"
    assert passport_data["replay_hash"] == verification.json()["replay"]["replay_hash"]
    assert passport_data["proposal_decisions"]
    assert any(x["decision_history"] for x in passport_data["proposal_decisions"])
    for artifact, digest in passport_data["exported_artifact_sha256"].items():
        exported = client.get(f"/api/v1/runs/{rid}/export/{artifact}")
        assert (
            exported.status_code == 200 and hashlib.sha256(exported.content).hexdigest() == digest
        )
    assert store.get(rid)["original"] == generated
    history = store.get_analysis(rid)["proposals"]
    changed = next(p for p in history if p["id"] == proposal["id"])
    assert [e["action"] for e in changed["decision_history"]] == ["edit", "approve", "apply"]
    assert changed["decision_history"][0]["prior_proposal"]["version"] == 1


def test_manual_numeric_edit_rejects_out_of_range_value(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")}
    ).json()["run"]
    rid = uploaded["id"]
    analysis = client.post(f"/api/v1/runs/{rid}/analyze").json()
    proposal = next(
        p
        for p in analysis["proposals"]
        if p["column"] == "city" and p["gate"]["decision"] == "needs_approval"
    )
    # Exercise numeric-range validation on a proposal tied to the same affected row.
    stored = store.get_analysis(rid)
    target = next(p for p in stored["proposals"] if p["id"] == proposal["id"])
    target["column"] = "unit_price"
    store.mark_analyzed(rid, stored)
    raw_frame, _ = parse_csv(generated)
    value = str(raw_frame.iloc[4]["unit_price"])
    response = client.post(
        f"/api/v1/runs/{rid}/proposals/{proposal['id']}/edit",
        json={
            "row_id": "row_5",
            "column": "unit_price",
            "original_value": value,
            "edited_value": "999999999",
            "reason": "out of range test",
        },
    )
    assert response.status_code == 422 and response.json()["code"] == "edit_out_of_range"


def test_bulk_review_uncertainty_pagination_and_trust_passport(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")}
    ).json()["run"]
    rid = uploaded["id"]
    analysis = client.post(f"/api/v1/runs/{rid}/analyze").json()
    pending = [p for p in analysis["proposals"] if p["gate"]["decision"] == "needs_approval"]
    bulk = client.post(
        f"/api/v1/runs/{rid}/bulk-decisions",
        json={"proposal_ids": [pending[0]["id"]], "action": "approve"},
    )
    assert bulk.status_code == 200 and bulk.json()["results"][0]["state"] == "approved"
    refused = next(p for p in analysis["proposals"] if p["gate"]["decision"] == "refused")
    rejected = client.post(
        f"/api/v1/runs/{rid}/bulk-decisions",
        json={"proposal_ids": [refused["id"]], "action": "approve"},
    )
    assert rejected.status_code == 409
    heat = client.get(f"/api/v1/runs/{rid}/uncertainty?offset=2&limit=1")
    assert (
        heat.status_code == 200 and heat.json()["offset"] == 2 and len(heat.json()["records"]) == 1
    )
    assert heat.json()["records"][0]["confidence"] is None
    assert len(heat.json()["columns"]) == 10
    passport1 = client.get(f"/api/v1/runs/{rid}/export/passport")
    passport2 = client.get(f"/api/v1/runs/{rid}/export/passport")
    assert passport1.status_code == passport2.status_code == 200
    one, two = passport1.json(), passport2.json()
    assert one == two
    assert one["original_sha256"] == hashlib.sha256(generated).hexdigest()
    cleaned_response = client.get(f"/api/v1/runs/{rid}/export/cleaned")
    assert cleaned_response.status_code == 200
    assert one["cleaned_sha256"] == hashlib.sha256(cleaned_response.content).hexdigest()
    cleaned_frame, _ = parse_csv(cleaned_response.content)
    assert cleaned_frame.shape[1] == one["output_column_count"]
    assert {x["name"] for x in store.list_artifacts(rid)} >= {"cleaned", "passport"}
    assert one["passport_sha256"] and one["proposal_count"] == len(analysis["proposals"])
    canonical = json.dumps(
        {k: v for k, v in one.items() if k != "passport_sha256"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert one["passport_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert one["final_unresolved_issues"]


def test_fingerprints_are_stable_but_decisions_do_not_cross_runs(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    runs = []
    for _ in range(2):
        uploaded = client.post(
            "/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")}
        ).json()["run"]
        runs.append((uploaded["id"], client.post(f"/api/v1/runs/{uploaded['id']}/analyze").json()))
    first_id, first = runs[0]
    second_id, second = runs[1]

    def key(issue):
        return (issue["title"], issue["column"])

    patterns = {key(i): i["pattern"]["fingerprint_id"] for i in first["issues"]}
    assert patterns == {key(i): i["pattern"]["fingerprint_id"] for i in second["issues"]}
    assert all("user1@example.test" not in json.dumps(i["pattern"]) for i in first["issues"])
    proposal = next(p for p in first["proposals"] if p["gate"]["decision"] == "needs_approval")
    assert (
        client.post(
            f"/api/v1/runs/{first_id}/decisions",
            json={"decisions": [{"proposal_id": proposal["id"], "action": "approve"}]},
        ).status_code
        == 200
    )
    second_proposal = next(
        p
        for p in second["proposals"]
        if p["op"] == proposal["op"] and p["column"] == proposal["column"]
    )
    assert second_proposal["status"] == "pending" and second_proposal["decision_history"] == []


def test_full_feature_pipeline_is_connected_through_run_api(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    raw_hash = hashlib.sha256(generated).hexdigest()
    upload = client.post("/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")})
    assert upload.status_code == 201
    rid = upload.json()["run"]["id"]
    assert upload.json()["run"]["file_sha256"] == raw_hash

    analyzed = client.post(f"/api/v1/runs/{rid}/analyze")
    assert analyzed.status_code == 200
    body = analyzed.json()
    assert body["issues"] and all(
        x["evidence"] and x["pattern"]["fingerprint_id"].startswith("fp_") for x in body["issues"]
    )
    assert body["proposals"] and all(
        x["simulation"]["impact"] and x["gate"] for x in body["proposals"]
    )
    assert all(
        p["simulation"]["impact"]["risk_level"] in {"low", "moderate", "high", "unknown"}
        for p in body["proposals"]
    )
    reviewable = [p for p in body["proposals"] if p["gate"]["decision"] == "needs_approval"]
    city = next(p for p in reviewable if p["column"] == "city")
    rejected = next((p for p in reviewable if p["id"] != city["id"]), None)
    refused = next(p for p in body["proposals"] if p["gate"]["decision"] == "refused")

    heat = client.get(f"/api/v1/runs/{rid}/uncertainty?offset=0&limit=5")
    assert heat.status_code == 200 and heat.json()["columns"]
    city_heat = next(x for x in heat.json()["columns"] if x["column"] == "city")
    assert city_heat["total_records"] == body["profile"]["row_count"]
    assert city_heat["pending_proposals"] > 0
    assert any(r["evidence_references"] for r in heat.json()["records"] if r["issue_density"] > 0)

    edit = client.post(
        f"/api/v1/runs/{rid}/proposals/{city['id']}/edit",
        json={
            "row_id": "row_5",
            "column": "city",
            "original_value": "BENGALURU ",
            "edited_value": "Bengaluru",
            "reason": "Use an existing canonical category",
        },
    )
    assert edit.status_code == 200
    edited = edit.json()["proposal"]
    assert edited["version"] == 2 and edited["gate"]["decision"] == "needs_approval"
    assert edited["simulation"]["impact"]["direct_cells"] == 1
    assert edited["decision_history"][0]["prior_proposal"]["version"] == 1
    assert store.get(rid)["original"] == generated

    assert (
        client.post(
            f"/api/v1/runs/{rid}/decisions",
            json={"decisions": [{"proposal_id": city["id"], "action": "approve"}]},
        ).status_code
        == 200
    )
    if rejected:
        assert (
            client.post(
                f"/api/v1/runs/{rid}/decisions",
                json={"decisions": [{"proposal_id": rejected["id"], "action": "reject"}]},
            ).status_code
            == 200
        )
    override = client.post(
        f"/api/v1/runs/{rid}/decisions",
        json={"decisions": [{"proposal_id": refused["id"], "action": "approve"}]},
    )
    assert override.status_code == 409
    applied = client.post(f"/api/v1/runs/{rid}/apply")
    assert applied.status_code == 200 and applied.json()["status"] == "applied"
    verified = client.post(f"/api/v1/runs/{rid}/verify")
    assert verified.status_code == 200 and verified.json()["replay"]["match"] is True
    assert store.list_verifications(rid)[-1]["result"]["replay"]["match"] is True
    history = client.get(f"/api/v1/runs/{rid}/operations")
    assert history.status_code == 200 and history.json()["operations"]

    passport_response = client.get(f"/api/v1/runs/{rid}/export/passport")
    assert passport_response.status_code == 200
    passport = passport_response.json()
    assert passport["verification_status"] == "verified"
    assert (
        passport["passport_id"].startswith("pass_")
        and len(passport["original_column_schema"]) == 10
    )
    assert len(passport["proposals"]) == len(body["proposals"])
    assert passport["replay_hash"] == verified.json()["replay"]["replay_hash"]
    assert passport["proposal_decisions"] and passport["applied_operations"]
    for name, digest in passport["exported_artifact_sha256"].items():
        artifact = client.get(f"/api/v1/runs/{rid}/export/{name}")
        assert (
            artifact.status_code == 200 and hashlib.sha256(artifact.content).hexdigest() == digest
        )
    assert passport["cleaned_sha256"] == passport["exported_artifact_sha256"]["cleaned"]
    assert {x["name"] for x in store.list_artifacts(rid)} >= {
        "cleaned",
        "report",
        "log",
        "recipe",
        "passport",
    }


def test_supabase_adapter_uses_mocked_http_only():
    from datetime import datetime, timezone

    adapter = SupabaseStorage("https://example.supabase.co", "not-a-real-key", "datafix")
    calls = []
    dbrow = {
        "id": "00000000-0000-0000-0000-000000000001",
        "filename": "a.csv",
        "sha256": "abc",
        "size_bytes": 8,
        "row_count": 1,
        "column_count": 1,
        "status": "uploaded",
        "created_at": "2026-01-01T00:00:00+00:00",
        "original_path": "runs/00000000-0000-0000-0000-000000000001/original.csv",
        "working_json": '{"columns":["a"]}',
        "analysis": None,
    }

    def mock_request(path, method="GET", body=None, content_type="application/json", prefer=None):
        calls.append((path, method, body, content_type, prefer))
        if "select=analysis" in path:
            return json.dumps([{"analysis": {"issues": []}}]).encode()
        if path.startswith("/rest/v1/datafix_decisions?"):
            return json.dumps(
                [
                    {
                        "proposal_id": "p1",
                        "action": "approve",
                        "decided_at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            ).encode()
        if path.startswith("/rest/v1/datafix_operations?"):
            return json.dumps(
                [
                    {
                        "run_id": dbrow["id"],
                        "seq": 1,
                        "op_id": "op1",
                        "proposal_id": "p1",
                        "op": "trim_text",
                        "column_name": "a",
                        "cells_changed": 1,
                        "rows_removed": 0,
                        "decided_by": "auto",
                        "applied_at": "2026-01-01T00:00:00+00:00",
                        "confidence": None,
                        "active": True,
                        "params": {"op": "trim_text"},
                        "cell_log": [],
                    }
                ]
            ).encode()
        if path.startswith("/rest/v1/datafix_artifacts?"):
            return b"[]"
        if path.startswith("/rest/v1/datafix_verifications?"):
            return b"[]"
        if path.endswith("datafix_undo_latest"):
            return b"true"
        if path.startswith("/rest/v1/datafix_runs?") and "working_json" in path:
            return json.dumps([{"working_json": dbrow["working_json"]}]).encode()
        if path.startswith("/rest/v1/datafix_runs?"):
            return json.dumps([dbrow]).encode()
        if path.startswith("/storage/v1/object/") and method == "GET":
            return b"a\n1\n"
        return b""

    adapter._request = mock_request
    meta = {
        "id": dbrow["id"],
        "filename": "a.csv",
        "file_sha256": "abc",
        "file_size_bytes": 4,
        "row_count": 1,
        "column_count": 1,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    adapter.create(meta, b"a\n1\n", dbrow["working_json"])
    assert len(calls) == 2 and calls[0][0].startswith("/storage/v1/object/datafix/")
    assert adapter.get(dbrow["id"])["original"] == b"a\n1\n"
    assert adapter.get_working(dbrow["id"]) == dbrow["working_json"]
    adapter.mark_analyzed(dbrow["id"], {"issue_ids": []})
    assert calls[-1][1] == "POST" and calls[-1][0].endswith("datafix_mark_analyzed")
    assert adapter.get_analysis(dbrow["id"]) == {"issues": []}
    assert adapter.get_decisions(dbrow["id"])["p1"]["action"] == "approve"
    adapter.save_decisions(
        dbrow["id"],
        [{"proposal_id": "p2", "action": "reject", "decided_at": "2026-01-01T00:00:00+00:00"}],
    )
    adapter.apply_batch(dbrow["id"], [], dbrow["working_json"], dbrow["working_json"])
    assert adapter.list_operations(dbrow["id"])[0]["op_id"] == "op1"
    assert adapter.undo_latest(dbrow["id"], "op1") is True
    adapter.save_artifact(dbrow["id"], "report", b"{}", "application/json")
    assert any(
        c[0].startswith("/storage/v1/object/datafix/runs/") and "/artifacts/report-" in c[0]
        for c in calls
    )
    assert adapter.list_artifacts(dbrow["id"]) == []
    adapter.save_verification(dbrow["id"], {"replay": {"match": True}})
    assert adapter.list_verifications(dbrow["id"]) == []


def test_supabase_backend_requires_backend_credentials():
    from types import SimpleNamespace

    config = SimpleNamespace(storage_backend="supabase", supabase_configured=False)
    with pytest.raises(RuntimeError, match="credentials are incomplete"):
        build_storage(config)


def test_supabase_secret_key_uses_apikey_without_jwt_bearer(monkeypatch):
    import io

    import app.storage as storage_module

    seen = []

    class MockResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def mock_urlopen(request, timeout):
        seen.append((request.get_header("Apikey"), request.get_header("Authorization")))
        return MockResponse(b"ok")

    monkeypatch.setattr(storage_module.urllib.request, "urlopen", mock_urlopen)
    modern = SupabaseStorage(
        "https://example.supabase.co", "test-secret-key", "datafix", bearer_auth=False
    )
    modern._request("/rest/v1/datafix_runs")
    assert seen == [("test-secret-key", None)]


def test_optional_groq_disabled_and_mocked_constrained_output(monkeypatch, generated):
    import io
    from types import SimpleNamespace

    import app.llm as llm

    frame, _ = parse_csv(generated)
    _, issues, _ = analyze_frame("llm-test", frame, len(generated))
    issue = next(x for x in issues if x.diagnosis)
    calls = []
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda *a, **k: calls.append(a) or io.BytesIO(b"{}")
    )
    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            llm_enabled=False,
            llm_available=False,
            llm_model="",
            groq_api_key="",
            llm_timeout_seconds=1,
            llm_max_retries=0,
            llm_requests_per_run=1,
        ),
    )
    assert llm.explain_issue(issue, "disabled-run") == issue.description and calls == []
    monkeypatch.setattr(llm, "_run_counts", {})
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            llm_enabled=True,
            llm_available=True,
            llm_model="mock-model",
            groq_api_key="mock-key",
            llm_timeout_seconds=1,
            llm_max_retries=0,
            llm_requests_per_run=1,
        ),
    )
    hypothesis = issue.diagnosis[0].id
    content = json.dumps(
        {
            "hypothesis_id": hypothesis,
            "explanation": "The evidence proves the cause and rules out every alternative.",
        }
    )
    response = {"choices": [{"message": {"content": content}}]}

    class MockResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda *a, **k: MockResponse(json.dumps(response).encode())
    )
    result = llm.explain_issue(issue, "mock-run")
    assert result.startswith("Possible explanation:")
    assert issue.diagnosis[0].statement.rstrip(".") in result
    assert "not confirmed" in result
    assert "rules out every alternative" not in result


def test_groq_403_is_not_retried_and_uses_deterministic_fallback(monkeypatch, generated):
    import io
    from types import SimpleNamespace

    import app.llm as llm

    frame, _ = parse_csv(generated)
    _, issues, _ = analyze_frame("llm-403-test", frame, len(generated))
    issue = next(x for x in issues if x.diagnosis)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise llm.urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            403,
            "Forbidden",
            {},
            io.BytesIO(b"error code: 1010"),
        )

    monkeypatch.setattr(llm.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(llm, "_run_counts", {})
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            llm_enabled=True,
            llm_available=True,
            llm_model="mock-model",
            groq_api_key="mock-key",
            llm_timeout_seconds=1,
            llm_max_retries=2,
            llm_requests_per_run=1,
        ),
    )
    assert llm.explain_issue(issue, "403-run") == issue.description
    assert len(calls) == 1
    assert llm._cache == {}


def test_generated_analysis_artifact_matches_schema():
    from app.schemas import AnalysisResponse

    artifact = json.loads((Path(__file__).parents[1] / "actual_analysis_response.json").read_text())
    parsed = AnalysisResponse.model_validate(artifact)
    assert parsed.summary.issue_count == len(parsed.issues) > 0
    assert parsed.summary.proposal_count == len(parsed.proposals) > 0
    assert all(
        issue.evidence and issue.affected_row_ids and issue.diagnosis for issue in parsed.issues
    )


def test_csv_detects_delimiters_and_common_encodings():
    semicolon, headers = parse_csv("name;city\nAna;Málaga\n".encode("cp1252"))
    assert headers == ["name", "city"] and semicolon.iloc[0]["city"] == "Málaga"
    utf16, headers = parse_csv("name\tcity\nAna\t東京\n".encode("utf-16"))
    assert headers == ["name", "city"] and utf16.iloc[0]["city"] == "東京"


def test_xlsx_worksheet_selection_and_full_repair_export_preserves_workbook(
    monkeypatch, tmp_path, generated
):
    from io import BytesIO

    from openpyxl import Workbook, load_workbook

    from app.services import parse_csv

    source, _ = parse_csv(generated)
    book = Workbook()
    sheet = book.active
    sheet.title = "Orders"
    for row in [list(source.columns), *source.astype(str).values.tolist()]:
        sheet.append(row)
    sheet["C6"].fill = __import__("openpyxl").styles.PatternFill(
        fill_type="solid", fgColor="FFFF00"
    )
    summary = book.create_sheet("Summary")
    summary["A1"] = "=SUM(1,2)"
    summary["A1"].font = __import__("openpyxl").styles.Font(bold=True)
    stream = BytesIO()
    book.save(stream)
    raw = stream.getvalue()
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    sheet_list = client.post(
        "/api/v1/datasets/worksheets",
        files={
            "file": (
                "orders.xlsx",
                raw,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert sheet_list.status_code == 200 and sheet_list.json() == {
        "worksheets": ["Orders", "Summary"],
        "active_worksheet": "Orders",
    }
    upload = client.post(
        "/api/v1/runs",
        files={
            "file": (
                "orders.xlsx",
                raw,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"worksheet": "Orders"},
    )
    assert (
        upload.status_code == 201
        and upload.json()["run"]["file_sha256"] == hashlib.sha256(raw).hexdigest()
    )
    run_id = upload.json()["run"]["id"]
    assert upload.json()["run"]["format_metadata"]["selected_worksheet"] == "Orders"
    analysis = client.post(f"/api/v1/runs/{run_id}/analyze")
    assert analysis.status_code == 200
    city = next(
        p
        for p in analysis.json()["proposals"]
        if p["column"] == "city" and p["gate"]["decision"] == "needs_approval"
    )
    edit = client.post(
        f"/api/v1/runs/{run_id}/proposals/{city['id']}/edit",
        json={
            "row_id": "row_5",
            "column": "city",
            "original_value": "BENGALURU ",
            "edited_value": "Bengaluru",
            "reason": "Use the existing canonical category",
        },
    )
    assert edit.status_code == 200 and edit.json()["proposal"]["version"] == 2
    decision = client.post(
        f"/api/v1/runs/{run_id}/decisions",
        json={"decisions": [{"proposal_id": city["id"], "action": "approve"}]},
    )
    assert decision.status_code == 200
    applied = client.post(f"/api/v1/runs/{run_id}/apply")
    assert applied.status_code == 200 and applied.json()["status"] == "applied"
    verified = client.post(f"/api/v1/runs/{run_id}/verify")
    assert verified.status_code == 200 and verified.json()["replay"]["match"]
    export = client.get(f"/api/v1/runs/{run_id}/export/cleaned")
    assert export.status_code == 200 and "spreadsheetml.sheet" in export.headers["content-type"]
    result = load_workbook(BytesIO(export.content), data_only=False)
    assert result.sheetnames == ["Orders", "Summary"]
    assert result["Orders"]["E6"].value == "Bengaluru"
    assert result["Orders"]["C6"].fill.fgColor.rgb == "00FFFF00"
    assert result["Summary"]["A1"].value == "=SUM(1,2)" and result["Summary"]["A1"].font.bold
    assert store.get(run_id)["original"] == raw


def test_xlsx_export_refuses_to_overwrite_formula_cells():
    from io import BytesIO

    from openpyxl import Workbook

    from app.ingestion.xlsx_adapter import XlsxAdapter
    from app.services import InputProblem

    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(["value"])
    sheet.append(["=1+1"])
    stream = BytesIO()
    book.save(stream)
    raw = stream.getvalue()
    parsed = XlsxAdapter().parse(raw, "formula.xlsx")
    parsed.frame.iloc[0, 0] = "manual replacement"
    with pytest.raises(InputProblem) as exc:
        XlsxAdapter().export_cleaned(raw, parsed.frame, parsed.metadata)
    assert exc.value.code == "xlsx_formula_edit_unsupported"


def test_1000_row_synthetic_error_manifest_matches_real_detectors():
    import runpy

    runpy.run_path(str(FIX / "generate_scale_fixture.py"))
    raw = (FIX / "datafix_1000_dirty.csv").read_bytes()
    manifest = json.loads((FIX / "datafix_1000_error_manifest.json").read_text())
    frame, _ = parse_csv(raw)
    prof, issues, proposals = analyze_frame("scale-fixture", frame, len(raw))
    categories = {x.category.value for x in issues}
    assert prof.row_count == 1001 and prof.column_count == 10
    assert {x["expected_detector"] for x in manifest["errors"]} <= categories
    assert all(issue.evidence and issue.affected_rows > 0 for issue in issues)
    assert proposals


def test_canonical_sample_real_analysis_has_evidence_and_expected_refusal():
    sample = Path(__file__).parents[2] / "samples" / "orders_dirty.csv"
    raw = sample.read_bytes()
    frame, _ = parse_csv(raw)
    profile, issues, proposals = analyze_frame("canonical", frame, len(raw))
    categories = {x.category.value for x in issues}
    assert frame.shape == (1001, 14)
    assert categories >= {
        "missing",
        "duplicate",
        "invalid_format",
        "inconsistent",
        "anomaly",
        "relationship",
    }
    assert all(x.evidence and x.affected_rows > 0 for x in issues)
    assert any(p.op == Operation.normalize_date and p.params.row_values for p in proposals)
    assert any(p.op == Operation.normalize_date and not p.params.row_values for p in proposals)
    assert next(c for c in profile.columns if c.name == "pincode").inferred_type == "category"
    assert not any(i.category == IssueCategory.anomaly and i.column == "pincode" for i in issues)


def test_local_repair_decision_apply_verify_undo_lifecycle(monkeypatch, tmp_path, generated):
    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("dirty.csv", generated, "text/csv")}
    ).json()["run"]
    run_id = uploaded["id"]
    expected = store.get_working(run_id)
    with pytest.raises(ConcurrentWriteError):
        store.apply_batch(run_id, [], "stale write", "different snapshot")
    assert store.get_working(run_id) == expected
    analysis = client.post(f"/api/v1/runs/{run_id}/analyze").json()
    pending = [p for p in analysis["proposals"] if p["gate"]["decision"] == "needs_approval"]
    request_body = {"decisions": [{"proposal_id": p["id"], "action": "approve"} for p in pending]}
    decision = client.post(f"/api/v1/runs/{run_id}/decisions", json=request_body)
    assert decision.status_code == 200 and all(
        x["state"] == "approved" for x in decision.json()["decisions"]
    )
    repeated = client.post(f"/api/v1/runs/{run_id}/decisions", json=request_body)
    assert repeated.status_code == 200 and repeated.json() == decision.json()
    conflicting = [{"proposal_id": p["id"], "action": "reject"} for p in pending]
    assert (
        client.post(f"/api/v1/runs/{run_id}/decisions", json={"decisions": conflicting}).status_code
        == 409
    )
    applied = client.post(f"/api/v1/runs/{run_id}/apply")
    assert applied.status_code == 200 and applied.json()["status"] == "applied"
    repeated_apply = client.post(f"/api/v1/runs/{run_id}/apply")
    assert repeated_apply.status_code == 200 and repeated_apply.json()["status"] == "applied"
    assert repeated_apply.json()["applied_operations"] == []
    operations = client.get(f"/api/v1/runs/{run_id}/operations").json()["operations"]
    assert operations and all(x["active"] for x in operations)
    restarted = RunStorage(tmp_path)
    assert [x["op_id"] for x in restarted.list_operations(run_id)] == [
        x["op_id"] for x in operations
    ]
    assert restarted.get_analysis(run_id) is not None
    exported_log = client.get(f"/api/v1/runs/{run_id}/export/log")
    assert exported_log.status_code == 200
    assert any(x.get("action") == "row_removed" for x in exported_log.json())
    verified = client.post(f"/api/v1/runs/{run_id}/verify")
    assert verified.status_code == 200 and verified.json()["replay"]["match"] is True
    last = operations[-1]["op_id"]
    undone = client.post(f"/api/v1/runs/{run_id}/undo/{last}")
    assert undone.status_code == 200 and undone.json()["status"] == "undone"
    current = client.get(f"/api/v1/runs/{run_id}/operations").json()["operations"]
    assert not next(x for x in current if x["op_id"] == last)["active"]
    assert client.post(f"/api/v1/runs/{run_id}/verify").json()["replay"]["match"] is True
    reapplied = client.post(f"/api/v1/runs/{run_id}/apply")
    assert reapplied.status_code == 200 and reapplied.json()["status"] == "applied"
    assert any(
        x["proposal_id"] == next(x for x in operations if x["op_id"] == last)["proposal_id"]
        for x in reapplied.json()["applied_operations"]
    )
    assert client.post(f"/api/v1/runs/{run_id}/verify").json()["replay"]["match"] is True


def test_failed_combined_invariant_aborts_entire_batch(monkeypatch, tmp_path, generated):
    from app.schemas import Invariant

    store = RunStorage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    uploaded = client.post(
        "/api/v1/runs", files={"file": ("atomic.csv", generated, "text/csv")}
    ).json()["run"]
    rid = uploaded["id"]
    analysis = client.post(f"/api/v1/runs/{rid}/analyze").json()
    pending = [p for p in analysis["proposals"] if p["gate"]["decision"] == "needs_approval"]
    if pending:
        client.post(
            f"/api/v1/runs/{rid}/decisions",
            json={"decisions": [{"proposal_id": p["id"], "action": "approve"} for p in pending]},
        )
    before = store.get_working(rid)

    def fail_batch(*args, **kwargs):
        return (
            [
                Invariant(
                    name="injected_atomic_failure", status="fail", detail="Test fault injection."
                )
            ],
            {},
            0,
        )

    monkeypatch.setattr(main, "invariant_results", fail_batch)
    result = client.post(f"/api/v1/runs/{rid}/apply")
    assert result.status_code == 200 and result.json()["status"] == "aborted"
    assert result.json()["applied_operations"] == []
    assert store.get_working(rid) == before
    assert store.list_operations(rid, active_only=False) == []


def test_export_formula_prefix_is_sanitized():
    from app.lifecycle import csv_safe

    assert csv_safe("=1+1") == "'=1+1"
    assert csv_safe("ordinary") == "ordinary"
    assert csv_safe("+91-9876543210", "phone") == "+91-9876543210"
    assert csv_safe("-4.0", "age") == "-4.0"


def test_xlsx_friendly_export_keeps_phones_as_text_and_dates_visible():
    from io import BytesIO

    import pandas as pd
    from openpyxl import load_workbook

    from app.ingestion.xlsx_adapter import XlsxAdapter

    raw = XlsxAdapter().export_frame(pd.DataFrame({
        "record_id": ["DF001"], "phone": ["+91-9876543210"], "signup_date": ["2025-01-12"]
    }))
    sheet = load_workbook(BytesIO(raw), data_only=False).active
    assert sheet["B2"].value == "+91-9876543210" and sheet["B2"].data_type == "s"
    assert sheet["C2"].value == "2025-01-12" and sheet.column_dimensions["C"].width >= 17
    assert not [cell for row in sheet.iter_rows() for cell in row if cell.data_type == "f"]


def test_simulator_reports_all_seven_integrity_invariants():
    import pandas as pd

    from app.lifecycle import invariant_results

    frame = pd.DataFrame(
        {
            "order_id": ["O1", "O2"],
            "quantity": ["1", "2"],
            "unit_price": ["10", "20"],
            "total": ["10", "40"],
            "pincode": ["100", "100"],
            "city": ["A", "A"],
        },
        dtype="string",
    )
    invariants, drift, damaged = invariant_results(frame, frame.copy(), issues=[], changes=[])
    assert {x.name for x in invariants} == {
        "schema_and_types_preserved",
        "row_count_policy",
        "candidate_keys_unique_non_null",
        "previously_valid_cells_preserved",
        "business_rules_not_worsened",
        "functional_dependencies_not_worsened",
        "aggregate_drift_within_risk_limit",
    }
    assert all(x.status == "pass" for x in invariants)
    assert "quantity.sum_relative" in drift and damaged == 0


def test_simulator_fails_candidate_key_and_business_rule_invariants():
    import pandas as pd

    from app.lifecycle import invariant_results

    before = pd.DataFrame(
        {
            "order_id": ["O1", "O2"],
            "quantity": ["1", "2"],
            "unit_price": ["10", "20"],
            "total": ["10", "40"],
        },
        dtype="string",
    )
    after = pd.DataFrame(
        {
            "order_id": ["O1", "O1"],
            "quantity": ["1", "2"],
            "unit_price": ["10", "20"],
            "total": ["20", "40"],
        },
        dtype="string",
    )
    invariants, _, _ = invariant_results(
        before, after, issues=[], changes=[{"row_id": "row_1", "column": "total"}]
    )
    failed = {x.name for x in invariants if x.status == "fail"}
    assert "candidate_keys_unique_non_null" in failed
    assert "business_rules_not_worsened" in failed
    assert "aggregate_drift_within_risk_limit" in failed


def test_simulator_fails_functional_dependency_invariant():
    import pandas as pd

    from app.lifecycle import invariant_results

    before = pd.DataFrame({"pincode": ["100", "100"], "city": ["A", "A"]}, dtype="string")
    after = pd.DataFrame({"pincode": ["100", "100"], "city": ["A", "B"]}, dtype="string")
    invariants, _, _ = invariant_results(before, after, issues=[], changes=[])
    assert (
        next(x for x in invariants if x.name == "functional_dependencies_not_worsened").status
        == "fail"
    )
