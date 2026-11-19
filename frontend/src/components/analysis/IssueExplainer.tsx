import React from 'react';
import { ArrowRight, CircleHelp } from 'lucide-react';
import type { DetectedIssue, RepairProposal, RunState } from '../../lib/contract-types';
import { Card } from '../common/Card';

const simpleIssue: Record<DetectedIssue['category'], { title: string; matters: string }> = {
  missing: { title: 'Some information is missing', matters: 'A missing value can make a record incomplete or prevent later steps from using it.' },
  duplicate: { title: 'Some entries appear more than once', matters: 'Repeated entries can inflate totals or cause the same record to be processed multiple times.' },
  format: { title: 'Some values use an unexpected format', matters: 'Other tools may not be able to read or use a value in this format.' },
  invalid_format: { title: 'Some values do not look valid', matters: 'The value may be rejected by another system or may need a person to confirm it.' },
  inconsistent: { title: 'Some values are written in different ways', matters: 'Different spellings or spacing can split the same group into separate categories.' },
  anomaly: { title: 'This value is unusual compared with others', matters: 'Unusual does not always mean wrong; it should be checked against your context.' },
  relationship: { title: 'Some related information does not agree', matters: 'A mismatch can make totals or related fields inconsistent. DataFix does not guess which side is wrong.' },
  row_structure_mismatch: { title: 'Some rows have a different number of fields', matters: 'Values may be shifted into the wrong columns or need a person to review unexpected fields.' },
};

function safetyText(proposal?: RepairProposal) {
  if (!proposal) return { label: 'Needs your attention', why: 'There is no safe automatic suggestion for this finding. Review the source data before changing it.' };
  if (proposal.decision === 'auto_apply') return { label: 'Ready to fix automatically', why: 'The checks allow this change when you apply the repair plan. No change has been made yet.' };
  if (proposal.decision === 'needs_approval') return { label: 'Waiting for your approval', why: 'DataFix prepared a suggestion, but it will not be applied until you approve it.' };
  return { label: 'Cannot safely fix', why: 'DataFix found a problem, but there is not enough reliable information to correct it safely.' };
}

export const IssueExplainer: React.FC<{ run: RunState; onOpenProposal: (proposalId: string) => void }> = ({ run, onOpenProposal }) => (
  <Card className="overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3"><div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Findings from this upload</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Problems to review</h2></div><span className="text-xs font-mono text-slate-500">{run.issues.length} found</span></div>
    {run.issues.length === 0 ? <div className="p-6 text-sm text-slate-600">No problems were detected by the checks DataFix ran. This does not prove every value is correct.</div> : <div className="divide-y divide-slate-100">{run.issues.map((issue) => {
      const plain = simpleIssue[issue.category];
      const proposal = run.proposals.find((item) => item.id === issue.linked_proposal_id);
      const safety = safetyText(proposal);
      const rowIds = issue.affected_row_ids ?? [];
      const sampleDiff = proposal?.simulation?.sample_diff ?? [];
      return <article id={`issue-${issue.id}`} key={issue.id} className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-slate-900">{plain.title}</h3><p className="text-xs text-slate-600 mt-1">{issue.description}</p></div><span className={`rounded-full border px-2.5 py-1 text-[10px] ${proposal?.decision === 'auto_apply' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : proposal?.decision === 'needs_approval' ? 'bg-amber-50 border-amber-200 text-amber-800' : proposal?.decision === 'refused' ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-slate-50 border-slate-200 text-slate-700'}`}>{safety.label}</span></div>
        <div className="grid sm:grid-cols-2 gap-x-6 gap-y-3 mt-4 text-xs">
          <div><p className="text-[9px] uppercase tracking-wider font-mono text-slate-400">Where is it?</p><p className="mt-1 text-slate-700"><strong>Column:</strong> {issue.column || 'More than one column'} · <strong>Rows:</strong> {rowIds.length ? rowIds.slice(0,8).join(', ')+(rowIds.length>8?'…':'') : `${issue.affected_rows ?? issue.affected_cells} affected`}</p></div>
          <div><p className="text-[9px] uppercase tracking-wider font-mono text-slate-400">Why does it matter?</p><p className="mt-1 text-slate-700">{plain.matters}</p></div>
          <div><p className="text-[9px] uppercase tracking-wider font-mono text-slate-400">What can DataFix do?</p><p className="mt-1 text-slate-700">{proposal ? proposal.title : 'No automatic correction is suggested. Review the original file and confirm the intended value.'}</p>{sampleDiff.slice(0,2).map((diff,index)=><div key={index} className="mt-2 flex items-center gap-2 font-mono text-[10px]"><span className="text-slate-500">Row {diff.row_id} · {diff.column}</span><span className="line-through text-slate-400">{String(diff.before ?? 'blank')}</span><ArrowRight className="w-3 h-3 text-slate-400"/><span className="text-emerald-800">{String(diff.after ?? 'blank')}</span></div>)}</div>
          <div><p className="text-[9px] uppercase tracking-wider font-mono text-slate-400">Is it safe?</p><p className="mt-1 text-slate-700">{safety.why}</p>{proposal?.decision === 'refused' && <p className="mt-1 text-slate-500">Reason: {proposal.reasons[0] || proposal.explanation} Next step: correct the source data if you know the intended value, then upload it again.</p>}{proposal?.decision === 'auto_apply' && <p className="mt-1 text-slate-500">This change is only applied after you choose Apply in the Repair Studio.</p>}</div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">{proposal && <button onClick={() => onOpenProposal(proposal.id)} className="text-xs font-medium text-emerald-800 hover:underline">Review suggestion in Repair Studio →</button>}<details className="text-[10px] text-slate-500"><summary className="cursor-pointer inline-flex items-center gap-1"><CircleHelp className="w-3 h-3"/>Advanced details</summary><div className="mt-2 p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2"><p>Detector category: <code>{issue.category}</code> · Issue ID: <code>{issue.id}</code> · affected cells: {issue.affected_cells}</p><p>{issue.likely_cause}</p>{issue.evidence?.map((e,index)=><div key={index}><strong>{e.label}</strong><p>{e.detail}</p>{e.examples?.length ? <p>Examples: {e.examples.join(' · ')}</p> : null}</div>)}{proposal&&<p>Operation: <code>{proposal.op}</code> · risk class: <code>{proposal.risk_class}</code> · Gate: <code>{proposal.decision}</code> · confidence: {proposal.confidence.value===null?'not available':`${Math.round(proposal.confidence.value*100)}%`}</p>}</div></details></div>
      </article>;
    })}</div>}
  </Card>
);
