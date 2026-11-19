"""Canonical validated API request and response models."""
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class RunStatus(str, Enum):
    uploaded = "uploaded"
    analyzed = "analyzed"
    applied = "applied"

class EvidenceKind(str, Enum):
    count = "count"
    example = "example"
    rule = "rule"
    statistic = "statistic"

class Evidence(StrictModel):
    kind: EvidenceKind
    label: str
    detail: str
    metrics: dict[str, int | float | None] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list, max_length=8)

class IssueCategory(str, Enum):
    missing = "missing"
    duplicate = "duplicate"
    invalid_format = "invalid_format"
    inconsistent = "inconsistent"
    anomaly = "anomaly"
    relationship = "relationship"
    row_structure_mismatch = "row_structure_mismatch"

class IssueDisposition(str, Enum):
    repair_proposed = "repair_proposed"
    flagged_only = "flagged_only"
    preserved_as_valid = "preserved_as_valid"

class DiagnosisHypothesis(StrictModel):
    id: str
    statement: str
    evidence_labels: list[str] = Field(default_factory=list)

class ConfidenceComponent(StrictModel):
    label: str
    value: float | None = Field(default=None, ge=0, le=1)
    note: str

class Issue(StrictModel):
    id: str
    category: IssueCategory
    title: str
    column: str | None
    description: str
    affected_rows: int
    affected_cells: int
    affected_row_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence]
    disposition: IssueDisposition
    diagnosis: list[DiagnosisHypothesis] = Field(default_factory=list)
    pattern: "PatternMatch | None" = None

class PatternMatch(StrictModel):
    fingerprint_id: str
    title: str
    explanation: str
    support_count: int = Field(ge=1)
    column_type: str
    error_type: str
    value_shape: str
    format_pattern: str | None = None
    frequency_count: int = Field(ge=1)
    supporting_rule_ids: list[str] = Field(default_factory=list)
    match_method: Literal["exact_signature"] = "exact_signature"
    evidence: list[str] = Field(default_factory=list)
    suggested_strategy: str | None = None
    limitations: list[str] = Field(default_factory=list)

class Operation(str, Enum):
    normalize_date = "normalize_date"
    trim_text = "trim_text"
    map_values = "map_values"
    set_null = "set_null"
    impute = "impute"
    drop_exact_dupes = "drop_exact_dupes"
    merge_near_dupes = "merge_near_dupes"
    cast_numeric = "cast_numeric"
    derive_from_rule = "derive_from_rule"
    manual_edit = "manual_edit"

class RiskClass(str, Enum):
    format_only = "format_only"
    value_substitution = "value_substitution"
    imputation = "imputation"
    destructive = "destructive"

class ProposalSource(str, Enum):
    rule = "rule"
    stat = "stat"
    llm_assisted = "llm_assisted"
    human = "human"

class NormalizeDateParams(StrictModel):
    op: Literal["normalize_date"]
    target_format: Literal["YYYY-MM-DD"]
    row_values: dict[str, str]

class TrimTextParams(StrictModel):
    op: Literal["trim_text"]
    row_values: dict[str, str]

class MapValuesParams(StrictModel):
    op: Literal["map_values"]
    mapping: dict[str, str]

class SetNullParams(StrictModel):
    op: Literal["set_null"]
    placeholder_values: list[str]
    row_ids: list[str]

class DropExactDupesParams(StrictModel):
    op: Literal["drop_exact_dupes"]
    duplicate_row_groups: list[list[str]]

class MergeNearDupesParams(StrictModel):
    op: Literal["merge_near_dupes"]
    candidate_pairs: list[list[str]]

class ImputeParams(StrictModel):
    op: Literal["impute"]
    strategy: Literal["constant", "mode", "median"]
    value: str | float | None = None

class CastNumericParams(StrictModel):
    op: Literal["cast_numeric"]
    row_values: dict[str, str]
    target_type: Literal["number"]

class DeriveFromRuleParams(StrictModel):
    op: Literal["derive_from_rule"]
    rule_id: str
    row_values: dict[str, int | float]

class ManualEditParams(StrictModel):
    op: Literal["manual_edit"]
    row_id: str
    expected_value: str
    value: str
    reason: str = Field(min_length=1, max_length=500)

OperationParams = Annotated[NormalizeDateParams | TrimTextParams | MapValuesParams | SetNullParams | DropExactDupesParams | MergeNearDupesParams | ImputeParams | CastNumericParams | DeriveFromRuleParams | ManualEditParams, Field(discriminator="op")]

class Confidence(StrictModel):
    value: float | None = Field(default=None, ge=0, le=1)
    method: Literal["rule_support", "backtest", "similarity", "losslessness"] | None = None
    components: list[ConfidenceComponent] = Field(default_factory=list)
    n_support: int | None = None
    lower_bound: float | None = None
    caveat: str | None = None

class Invariant(StrictModel):
    name: str
    status: Literal["pass", "fail", "skipped"]
    detail: str
    observed: int | float | str | None = None
    threshold: int | float | str | None = None
    unit: str | None = None

class SampleDiff(StrictModel):
    row_id: str
    column: str
    before: str
    after: str
    was_valid: bool

class Simulation(StrictModel):
    cells_changed: int
    rows_affected: int
    rows_removed: int
    previously_valid_cells_changed: int
    aggregate_drift: dict[str, int | float | None]
    new_issues_introduced: int
    sample_diff: list[SampleDiff]
    invariants: list[Invariant]
    impact: "RippleImpact | None" = None

class ImpactMetric(StrictModel):
    metric: str
    column: str
    before: int | float | str | None
    after: int | float | str | None
    change: int | float | None = None
    relationship: Literal["direct", "measured_dependency"]
    support: list[str] = Field(default_factory=list)

class RippleImpact(StrictModel):
    proposal_id: str
    direct_row_ids: list[str] = Field(default_factory=list, max_length=200)
    direct_cells: int
    direct_columns: list[str]
    direct_metrics: list[ImpactMetric]
    indirect_metrics: list[ImpactMetric]
    affected_dependency_checks: list[str]
    potentially_resolved_issue_ids: list[str]
    remaining_issue_ids: list[str] = Field(default_factory=list)
    introduced_issue_ids: list[str]
    risk_level: Literal["low", "moderate", "high", "unknown"] = "unknown"
    invariants: list[Invariant]
    risk_explanations: list[str]
    limitations: list[str]

class Gate(StrictModel):
    decision: Literal["auto_apply", "needs_approval", "refused"]
    reasons: list[str]
    refusal_kind: Literal["invariant_failed", "insufficient_evidence"] | None

class Proposal(StrictModel):
    id: str
    issue_ids: list[str]
    op: Operation
    column: str | None
    risk_class: RiskClass
    source: ProposalSource
    title: str
    explanation: str
    params: OperationParams
    evidence: list[Evidence]
    confidence: Confidence
    # These fields are optional for response compatibility, but the run analysis
    # service populates both with deterministic simulation and gate results.
    simulation: Simulation | None
    gate: Gate | None
    status: Literal["pending", "approved", "rejected", "edited_pending_reapproval", "applied", "failed", "refused"] = "pending"
    version: int = Field(default=1, ge=1)
    decision_history: list["DecisionAuditEntry"] = Field(default_factory=list)

class DecisionAuditEntry(StrictModel):
    previous_state: str
    new_state: str
    action: str
    timestamp: datetime
    proposal_version: int
    reason: str | None = None
    original_value: str | None = None
    edited_value: str | None = None
    suggested_value: str | None = None
    operation_id: str | None = None
    prior_proposal: dict[str, Any] | None = None

class RunMetadata(StrictModel):
    id: str
    filename: str
    file_sha256: str
    file_size_bytes: int
    row_count: int
    column_count: int
    status: RunStatus
    created_at: datetime
    engine_version: str
    format_metadata: dict[str, Any] = Field(default_factory=lambda: {"format": "csv"})

class AnalysisRunMetadata(StrictModel):
    id: str
    filename: str
    row_count: int
    column_count: int
    file_sha256: str
    status: RunStatus
    engine_version: str
    format_metadata: dict[str, Any] = Field(default_factory=lambda: {"format": "csv"})

class UploadResponse(StrictModel):
    run: RunMetadata
    warnings: list[str] = Field(default_factory=list)

class WorksheetListResponse(StrictModel):
    worksheets: list[str]
    active_worksheet: str

class MostFrequent(StrictModel):
    value: str
    count: int

class ColumnProfile(StrictModel):
    name: str
    inferred_type: str
    null_count: int
    null_pct: float
    distinct_count: int
    is_key_candidate: bool
    most_frequent: list[MostFrequent] = Field(default_factory=list)
    minimum: float | str | None = None
    maximum: float | str | None = None
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    category_distribution: list[MostFrequent] = Field(default_factory=list)
    format_consistency: float | None = None

class DatasetProfile(StrictModel):
    row_count: int
    column_count: int
    dataset_size_bytes: int
    duplicate_record_count: int
    total_missing_cells: int
    total_distinct_values: int
    columns: list[ColumnProfile]

class AnalysisSummary(StrictModel):
    issue_count: int
    proposal_count: int
    auto_apply_count: int | None = None
    needs_approval_count: int | None = None
    refused_count: int | None = None

class AnalysisResponse(StrictModel):
    run: AnalysisRunMetadata
    profile: DatasetProfile
    issues: list[Issue]
    proposals: list[Proposal]
    summary: AnalysisSummary

class ErrorEnvelope(StrictModel):
    code: str
    message: str
    details: dict[str, int | str | list[str] | None] = Field(default_factory=dict)
    request_id: str

class LLMHealth(StrictModel):
    enabled: bool
    available: bool
    model: str | None = None

class HealthResponse(StrictModel):
    status: Literal["ok", "degraded"]
    api: Literal["available"]
    llm: LLMHealth
    limits: dict[str, int]

class CompatibilityProfileResponse(StrictModel):
    profile: DatasetProfile

class DecisionAction(str, Enum):
    approve = "approve"
    reject = "reject"

class ProposalDecisionInput(StrictModel):
    proposal_id: str
    action: DecisionAction

class DecisionsRequest(StrictModel):
    decisions: list[ProposalDecisionInput] = Field(min_length=1)

class DecisionState(StrictModel):
    proposal_id: str
    action: DecisionAction
    state: Literal["approved", "rejected"]
    decided_at: datetime
    state: Literal["approved", "rejected", "edited_pending_reapproval"] = "approved"

class ProposalEditRequest(StrictModel):
    row_id: str
    column: str
    original_value: str
    edited_value: str
    reason: str = Field(min_length=1, max_length=500)

class ProposalEditResponse(StrictModel):
    proposal: Proposal
    status: Literal["edited_pending_reapproval", "refused"]

class BulkDecisionRequest(StrictModel):
    proposal_ids: list[str] = Field(min_length=1, max_length=200)
    action: Literal["approve", "reject"]

class BulkDecisionResult(StrictModel):
    proposal_id: str
    state: Literal["approved", "rejected", "refused"]
    reason: str | None = None

class BulkDecisionsResponse(StrictModel):
    results: list[BulkDecisionResult]

class ColumnUncertainty(StrictModel):
    column: str
    total_records: int
    missing_count: int
    missing_rate: float
    invalid_count: int
    invalid_rate: float
    inconsistent_count: int
    inconsistent_rate: float
    anomaly_count: int
    pending_proposals: int
    refused_proposals: int
    unresolved_issues: int
    evidence_available: bool
    confidence_available: bool
    rule_coverage: list[str]

class RecordUncertainty(StrictModel):
    row_id: str
    state: Literal["verified_by_checks", "issue_detected", "pending_human_review", "refused_repair", "unresolved", "not_evaluated"]
    issue_density: int
    columns: list[str]
    reasons: list[str]
    evidence_references: list[str]
    confidence: float | None = Field(default=None, ge=0, le=1)

class UncertaintyResponse(StrictModel):
    run_id: str
    offset: int
    limit: int
    total_records: int
    columns: list[ColumnUncertainty]
    records: list[RecordUncertainty]
    calculation_notes: list[str]

class PassportProposalDecision(StrictModel):
    proposal_id: str
    proposal_version: int
    status: str
    gate_decision: str | None
    decision_history: list[DecisionAuditEntry]

class PassportColumn(StrictModel):
    name: str
    inferred_type: str

class PassportProposal(StrictModel):
    proposal_id: str
    proposal_version: int
    operation: Operation
    column: str | None
    risk_class: RiskClass
    title: str
    explanation: str
    parameter_summary: dict[str, str | int | float | None]
    confidence: Confidence
    simulation: Simulation | None
    gate_decision: str | None
    status: str

class TrustPassport(StrictModel):
    passport_version: str
    passport_id: str
    run_id: str
    original_filename: str
    original_sha256: str
    cleaned_sha256: str
    passport_sha256: str
    original_size_bytes: int
    original_row_count: int
    original_column_count: int
    original_column_schema: list[PassportColumn]
    output_row_count: int
    output_column_count: int
    engine_version: str
    generated_at: datetime
    initial_issue_count: int
    initial_issue_categories: list[IssueCategoryCount]
    final_unresolved_issues: list[Issue]
    previously_valid_cells_changed: int
    quality_before: QualityDimensions
    quality_after: QualityDimensions
    proposal_count: int
    proposals: list[PassportProposal]
    auto_apply_decisions: int
    user_approvals: int
    rejections: int
    edited_proposals: int
    refused_repairs: int
    applied_operations: list[AppliedOperation]
    modification_log_reference: str
    simulation_summary: list[Simulation]
    gate_outcomes: dict[str, str]
    proposal_decisions: list[PassportProposalDecision]
    exported_artifact_sha256: dict[str, str]
    verification_status: Literal["verified", "replay_mismatch", "not_run"]
    replay_hash: str | None = None
    replay_matches: bool | None = None
    benchmark_version: str | None = None
    limitations: list[str]
    unresolved_count: int
    abstained_repairs: int
    llm_enabled: bool

class DecisionsResponse(StrictModel):
    decisions: list[DecisionState]

class AppliedOperation(StrictModel):
    seq: int
    op_id: str
    proposal_id: str
    op: Operation
    column: str | None
    cells_changed: int
    rows_removed: int
    decided_by: Literal["auto", "user"]
    applied_at: datetime
    confidence_at_decision: float | None = None
    active: bool = True

class CellModification(StrictModel):
    row_id: str
    column: str
    before: str | None
    after: str | None
    op_id: str
    proposal_id: str
    reason: str
    evidence_reference: str
    confidence: float | None
    decided_by: Literal["auto", "user"]
    applied_at: datetime

class AppliedOperationResult(StrictModel):
    op_id: str
    proposal_id: str
    op: Operation
    column: str | None
    cells_changed: int
    rows_removed: int
    decided_by: Literal["auto", "user"]
    applied_at: datetime

class SkippedProposal(StrictModel):
    proposal_id: str
    reason: str

class ApplyResponse(StrictModel):
    status: Literal["applied", "aborted"]
    applied_operations: list[AppliedOperationResult]
    skipped: list[SkippedProposal]
    blocking_invariants: list[Invariant]

class OperationHistoryResponse(StrictModel):
    operations: list[AppliedOperation]

class IssueCategoryCount(StrictModel):
    category: IssueCategory
    count: int

class QualityDimensions(StrictModel):
    completeness: float
    validity: float
    uniqueness: float
    consistency: float
    formulas: dict[str, str]

class VerificationIssues(StrictModel):
    before: int
    after: int
    resolved: int
    introduced: int
    by_category: list[IssueCategoryCount]

class ReplayResult(StrictModel):
    operations: int
    input_hash: str
    replay_hash: str
    match: bool

class VerificationResponse(StrictModel):
    replay: ReplayResult
    issues: VerificationIssues
    valid_cells_damaged: int
    quality_dimensions: dict[str, QualityDimensions]
    remaining: list[Issue]

class UndoRequest(StrictModel):
    op_id: str

class UndoResponse(StrictModel):
    status: Literal["undone", "refused"]
    op_id: str
    reason: str | None = None

# Resolve additive feature references after all related schemas are declared.
Issue.model_rebuild()
Simulation.model_rebuild()
