import type { components } from './generated-types';
import type { DatasetProfile, RunState, RepairProposal, DetectedIssue } from './contract-types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
type S = components['schemas'];
export type ApiHealthResponse = S['HealthResponse'];
export type AnalysisResponse = S['AnalysisResponse'];
export type OperationHistoryResponse = S['OperationHistoryResponse'];
export type VerificationResponse = S['VerificationResponse'];
export type UncertaintyResponse = S['UncertaintyResponse'];
export type TrustPassport = S['TrustPassport'];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const friendly: Record<string, string> = {
      empty_file: 'This file is empty. Choose a file that contains a header and at least one row.',
      missing_header: 'DataFix could not find column names in the first row. Add a header row and try again.',
      malformed_csv: 'DataFix could not read the CSV structure. Check the quotation marks and separators, then try again.',
      unsupported_encoding: 'DataFix could not safely read this file’s text encoding. Save it as UTF-8 and try again.',
      unsupported_content: 'This file is not a supported plain CSV or Excel workbook.',
      duplicate_headers: 'Two or more columns have the same name. Rename the columns so each header is unique.',
      row_limit_exceeded: 'This file contains more rows than this local service currently accepts.',
      column_limit_exceeded: 'This file contains more columns than this local service can safely analyze.',
      upload_too_large: 'This file is larger than the upload limit. Choose a smaller file.',
      unknown_run: 'DataFix could not find this run. Upload the file again to start a new run.',
      stale_original_value: 'This cell changed after it was reviewed. Refresh the analysis before editing it.',
      proposal_refused: 'DataFix cannot safely edit a refused suggestion. Correct the source file if you know the intended value, then upload it again.',
      concurrent_run_update: 'The dataset changed while DataFix was applying repairs. Refresh the analysis and try again.',
    };
    const code = typeof body?.code === 'string' ? body.code : '';
    const detail = typeof body?.message === 'string' ? body.message : typeof body?.detail === 'string' ? body.detail : '';
    throw new Error(friendly[code] || detail || `DataFix could not complete this request (HTTP ${response.status}). Please try again or inspect the advanced error details.`);
  }
  return body as T;
}

export async function checkApiHealth(): Promise<{ online: boolean; waking: boolean; data?: ApiHealthResponse }> {
  try { return { online: true, waking: false, data: await api<ApiHealthResponse>('/health') }; }
  catch { return { online: false, waking: false }; }
}

function mapProfile(profile: S['DatasetProfile'], filename: string): DatasetProfile {
  return {
    filename, row_count: profile.row_count, column_count: profile.column_count,
    total_cells: profile.row_count * profile.column_count,
    missing_cells: profile.total_missing_cells, duplicate_rows: profile.duplicate_record_count,
    notes: [],
    columns: profile.columns.map(c => ({ name: c.name, data_type: c.inferred_type,
      missing_count: c.null_count, missing_percent: c.null_pct, distinct_count: c.distinct_count,
      is_key_candidate: c.is_key_candidate })),
  };
}

export function mapProposal(p: S['Proposal']): RepairProposal {
  return {
    id: p.id, op: p.op, column: p.column || '', risk_class: p.risk_class, source: p.source,
    issue_ids: p.issue_ids, title: p.title, explanation: p.explanation,
    decision: (p.gate?.decision || 'refused') as RepairProposal['decision'],
    reasons: p.gate?.reasons || [], refusal_kind: p.gate?.refusal_kind || undefined,
    confidence: { value: p.confidence.value ?? null, method: p.confidence.method || 'rule_support',
      components: (p.confidence.components || []).map(x => ({ label: x.label, value: x.value ?? 0, note: x.note })),
      n_support: p.confidence.n_support ?? 0, lower_bound: p.confidence.lower_bound ?? null,
      caveat: p.confidence.caveat ?? null },
    evidence: p.evidence.map(e => ({ kind: e.kind, label: e.label, detail: e.detail })),
    simulation: p.simulation ? {
      cells_changed: p.simulation.cells_changed, rows_affected: p.simulation.rows_affected,
      rows_removed: p.simulation.rows_removed, previously_valid_cells_changed: p.simulation.previously_valid_cells_changed,
      aggregate_drift: Object.fromEntries(Object.entries(p.simulation.aggregate_drift).map(([k,v]) => [k, typeof v === 'number' ? v : 0])),
      new_issues_introduced: p.simulation.new_issues_introduced,
      invariants: p.simulation.invariants.map(x => ({ ...x, label: x.name })),
      sample_diff: p.simulation.sample_diff.map(x => ({ ...x })), impact: p.simulation.impact,
    } : undefined,
    user_action: p.status === 'approved' ? 'approved' : p.status === 'rejected' ? 'rejected' : 'pending',
    applied: p.status === 'applied',
  };
}

function mapAnalysis(a: AnalysisResponse, createdAt: string, warnings: string[]): RunState {
  const issues: DetectedIssue[] = a.issues.map(i => ({
    id: i.id, category: i.category as DetectedIssue['category'], column: i.column || '',
    likely_cause: i.diagnosis?.[0]?.statement || i.description,
    affected_cells: i.affected_cells, affected_rows: i.affected_rows, affected_row_ids: i.affected_row_ids, title: i.title,
    description: i.description, evidence: i.evidence, pattern: i.pattern,
    linked_proposal_id: a.proposals.find(p => p.issue_ids.includes(i.id))?.id,
  }));
  const proposals: RepairProposal[] = a.proposals.map(mapProposal);
  return {
    run_id: a.run.id, filename: a.run.filename, input_hash: a.run.file_sha256,
    created_at: createdAt, profile: mapProfile(a.profile, a.run.filename), issues, proposals,
    is_applied: a.run.status === 'applied', is_verified: false,
    backend_run: a.run, upload_warnings: warnings,
  } as RunState;
}

export async function uploadAndAnalyze(file: File, worksheet?: string): Promise<RunState> {
  const form = new FormData(); form.append('file', file);
  if (worksheet) form.append('worksheet', worksheet);
  const uploaded = await api<S['UploadResponse']>('/api/v1/runs', { method: 'POST', body: form });
  const analyzed = await api<AnalysisResponse>(`/api/v1/runs/${uploaded.run.id}/analyze`, { method: 'POST' });
  return mapAnalysis(analyzed, uploaded.run.created_at, uploaded.warnings || []);
}

export async function listWorksheets(file: File): Promise<{ worksheets: string[]; active_worksheet: string }> {
  const form = new FormData(); form.append('file', file);
  return api<{ worksheets: string[]; active_worksheet: string }>('/api/v1/datasets/worksheets', { method: 'POST', body: form });
}

export async function loadAnalysis(runId: string): Promise<RunState> {
  const a = await api<AnalysisResponse>(`/api/v1/runs/${runId}/analyze`, { method: 'POST' });
  return mapAnalysis(a, new Date().toISOString(), []);
}
export async function recordDecision(runId: string, proposalId: string, action: 'approve'|'reject') {
  return api<S['DecisionsResponse']>(`/api/v1/runs/${runId}/decisions`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({decisions:[{proposal_id:proposalId,action}]} satisfies S['DecisionsRequest']) });
}
export async function applyRun(runId: string) { return api<S['ApplyResponse']>(`/api/v1/runs/${runId}/apply`, {method:'POST'}); }
export async function getOperations(runId: string) { return api<OperationHistoryResponse>(`/api/v1/runs/${runId}/operations`); }
export async function verifyRun(runId: string) { return api<VerificationResponse>(`/api/v1/runs/${runId}/verify`, {method:'POST'}); }
export async function getTrustPassport(runId: string) { return api<TrustPassport>(`/api/v1/runs/${runId}/export/passport`); }
export async function getUncertainty(runId: string, offset=0, limit=100) { return api<UncertaintyResponse>(`/api/v1/runs/${runId}/uncertainty?offset=${offset}&limit=${limit}`); }
export async function undoOperation(runId: string, opId: string) { return api<S['UndoResponse']>(`/api/v1/runs/${runId}/undo/${opId}`, {method:'POST'}); }
export async function editProposal(runId: string, proposalId: string, body: S['ProposalEditRequest']) {
  return api<S['ProposalEditResponse']>(`/api/v1/runs/${runId}/proposals/${proposalId}/edit`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
}
export async function downloadArtifact(runId: string, artifact: 'cleaned'|'report'|'log'|'recipe'|'passport') {
  const url = `${API_BASE_URL}/api/v1/runs/${runId}/export/${artifact}`;
  const response = await fetch(url);
  if (!response.ok) { const body = await response.json().catch(()=>({})); throw new Error(body?.message || `Export failed (${response.status})`); }
  const blob = await response.blob();
  const name = response.headers.get('content-disposition')?.match(/filename="?([^";]+)"?/i)?.[1] || `datafix_${artifact}`;
  const objectUrl = URL.createObjectURL(blob); const a=document.createElement('a');a.href=objectUrl;a.download=name;a.click();window.setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
  return name;
}

export { API_BASE_URL };
