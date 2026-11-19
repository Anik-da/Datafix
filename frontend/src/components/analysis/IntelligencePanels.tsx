import React, { useMemo, useState } from 'react';
import { ArrowRight, Fingerprint, Network, Search, ShieldAlert } from 'lucide-react';
import type { RunState } from '../../lib/contract-types';
import type { UncertaintyResponse } from '../../lib/api';
import { Card } from '../common/Card';

const tone: Record<string, string> = {
  verified_by_checks: 'bg-emerald-500', issue_detected: 'bg-rose-500',
  pending_human_review: 'bg-amber-400', refused_repair: 'bg-indigo-500',
  unresolved: 'bg-orange-500', not_evaluated: 'bg-slate-200',
};

export const SchemaExplorer: React.FC<{ run: RunState }> = ({ run }) => (
  <Card className="overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3">
      <div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Observed schema</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Column explorer</h2></div>
      <span className="text-[10px] text-slate-500">{run.profile.columns.length} fields · measured from this run</span>
    </div>
    <div className="grid sm:grid-cols-2 xl:grid-cols-3 divide-x divide-y divide-slate-100">
      {run.profile.columns.map((column) => {
        const total = Math.max(1, run.profile.row_count);
        const missingPct = Math.min(100, (column.missing_count / total) * 100);
        const uniquePct = Math.min(100, (column.distinct_count / total) * 100);
        return <div key={column.name} className="p-4 min-w-0">
          <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="font-mono text-xs font-semibold text-slate-900 truncate">{column.name}</h3><p className="text-[10px] text-slate-500 mt-1">Observed type · {column.data_type}</p></div>{column.is_key_candidate && <span className="text-[9px] uppercase tracking-wide text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-1">Key candidate</span>}</div>
          <div className="mt-4 space-y-2 text-[10px]">
            <div className="flex justify-between text-slate-500"><span>Missing</span><span>{column.missing_count} / {total}</span></div><div className="h-1.5 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-amber-400" style={{ width: `${missingPct}%` }} /></div>
            <div className="flex justify-between text-slate-500"><span>Distinct values</span><span>{column.distinct_count} · {uniquePct.toFixed(0)}% of rows</span></div><div className="h-1.5 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-emerald-600" style={{ width: `${uniquePct}%` }} /></div>
          </div>
        </div>;
      })}
    </div>
    <p className="px-5 py-3 border-t border-slate-100 text-[10px] text-slate-500">Semantic roles and user-confirmed schema constraints are not supplied by the current API.</p>
  </Card>
);

export const FingerprintExplorer: React.FC<{ run: RunState }> = ({ run }) => {
  const patterns = run.issues.filter((issue) => issue.pattern);
  const [selectedId, setSelectedId] = useState(patterns[0]?.id ?? '');
  const selected = patterns.find((issue) => issue.id === selectedId) ?? patterns[0];
  if (!patterns.length) return <Card className="p-5"><h2 className="text-sm font-semibold">Error fingerprints</h2><p className="text-xs text-slate-500 mt-2">No recurring issue signatures were returned for this run.</p></Card>;
  const maxFrequency = Math.max(1, ...patterns.map((issue) => issue.pattern?.frequency_count ?? 0));
  return <Card className="overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-200 flex items-center gap-3"><div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center"><Fingerprint className="w-4 h-4" /></div><div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Recurring issue signatures</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Fingerprint explorer</h2></div></div>
    <div className="grid md:grid-cols-[minmax(180px,0.8fr)_1.2fr]">
      <div className="divide-y divide-slate-100 border-r border-slate-100">{patterns.map((issue) => <button key={issue.id} onClick={() => setSelectedId(issue.id)} className={`w-full text-left px-4 py-3 transition-colors hover:bg-slate-50 ${selected?.id === issue.id ? 'bg-emerald-50/70' : ''}`}><div className="flex justify-between gap-2 text-xs"><span className="font-medium text-slate-800 truncate">{issue.pattern?.title}</span><span className="font-mono text-slate-500">{issue.pattern?.frequency_count}×</span></div><div className="mt-2 h-1 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-emerald-600" style={{ width: `${((issue.pattern?.frequency_count ?? 0) / maxFrequency) * 100}%` }} /></div><code className="text-[9px] text-slate-400 mt-1 block truncate">{issue.pattern?.fingerprint_id}</code></button>)}</div>
      {selected && <div className="p-5 space-y-4"><div className="flex items-center justify-between gap-3"><div><p className="text-[10px] uppercase font-mono tracking-wider text-slate-500">Selected signature</p><p className="text-sm font-semibold mt-1">{selected.pattern?.title}</p></div><span className="text-[10px] rounded-full px-2.5 py-1 bg-slate-100 text-slate-700">{selected.pattern?.match_method}</span></div><div className="flex items-center gap-2 text-[10px] text-slate-600"><span className="px-2 py-1 bg-slate-50 border rounded">{selected.column || 'multiple columns'}</span><ArrowRight className="w-3 h-3 text-slate-400" /><span className="px-2 py-1 bg-emerald-50 border border-emerald-100 text-emerald-800 rounded">{selected.pattern?.suggested_strategy || 'Review evidence'}</span></div><p className="text-xs leading-relaxed text-slate-600">{selected.pattern?.explanation}</p><ul className="space-y-1">{(selected.pattern?.evidence ?? []).map((evidence, index) => <li key={index} className="text-[10px] text-slate-500 flex gap-2"><span className="text-emerald-600">•</span>{evidence}</li>)}</ul><p className="text-[10px] text-slate-400">Signatures describe normalized patterns; raw cell values are not shown. A match does not approve a repair.</p></div>}
    </div>
  </Card>;
};

export const UncertaintyMap: React.FC<{ run: RunState; data: UncertaintyResponse; onPage: (offset: number) => void; loading?: boolean }> = ({ run, data, onPage, loading }) => {
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [columnFilter, setColumnFilter] = useState('all');
  const [selectedRow, setSelectedRow] = useState<string | null>(null);
  const issueById = useMemo(() => new Map(run.issues.map((issue) => [issue.id, issue])), [run.issues]);
  const records = data.records.filter((record) => {
    const rowIssues = record.evidence_references.map((id) => issueById.get(id)).filter(Boolean);
    return (statusFilter === 'all' || record.state === statusFilter) &&
      (categoryFilter === 'all' || rowIssues.some((issue) => issue?.category === categoryFilter)) &&
      (columnFilter === 'all' || record.columns.includes(columnFilter));
  }).slice(0, 24);
  const columns = data.columns;
  const chosen = data.records.find((row) => row.row_id === selectedRow);
  const states = [...new Set(data.records.map((record) => record.state))];
  const categories = [...new Set(run.issues.map((issue) => issue.category))];
  return <Card className="overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap justify-between items-center gap-3"><div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Row × column review state</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Uncertainty map</h2></div><span className="text-[10px] text-slate-500">Rows {data.offset + 1}–{Math.min(data.offset + data.records.length, data.total_records)} of {data.total_records}</span></div>
    <div className="px-5 py-4 grid md:grid-cols-[1fr_auto] gap-5">
      <div className="space-y-3"><div className="flex flex-wrap gap-2">{columns.map((column) => <button key={column.column} onClick={() => setColumnFilter(columnFilter === column.column ? 'all' : column.column)} className={`text-left px-2 py-1.5 border rounded-lg transition-colors ${columnFilter === column.column ? 'border-emerald-600 bg-emerald-50' : 'border-slate-200'}`}><span className="block text-[10px] font-mono text-slate-700">{column.column}</span><span className="block text-[9px] text-slate-500">{column.unresolved_issues} unresolved · missing {(column.missing_rate*100).toFixed(1)}%</span><span className="block text-[9px] text-slate-400">invalid {(column.invalid_rate*100).toFixed(1)}% · {column.anomaly_count} anomalies</span></button>)}</div>
        <div className="flex flex-wrap gap-2"><label className="text-[10px] text-slate-500 flex items-center gap-1">State<select className="border border-slate-200 rounded-md px-2 py-1 bg-white text-slate-700" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">All states</option>{states.map((state) => <option key={state} value={state}>{state.replaceAll('_', ' ')}</option>)}</select></label><label className="text-[10px] text-slate-500 flex items-center gap-1">Issue<select className="border border-slate-200 rounded-md px-2 py-1 bg-white text-slate-700" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}><option value="all">All categories</option>{categories.map((category) => <option key={category} value={category}>{category.replaceAll('_', ' ')}</option>)}</select></label><button onClick={() => {setStatusFilter('all');setCategoryFilter('all');setColumnFilter('all')}} className="text-[10px] text-emerald-800 underline">Reset filters</button></div>
        <div className="space-y-1.5" aria-label="Paginated row uncertainty heatmap">{records.map((record) => <button key={record.row_id} title={`${record.row_id}: ${record.state}; ${record.reasons.join(', ')}`} onClick={() => setSelectedRow(selectedRow === record.row_id ? null : record.row_id)} className={`w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors ${selectedRow === record.row_id ? 'bg-emerald-50 ring-1 ring-emerald-200' : 'hover:bg-slate-50'}`}><span className="w-20 shrink-0 font-mono text-[9px] text-slate-500">{record.row_id}</span><span className="flex-1 flex gap-1">{run.profile.columns.slice(0, 20).map((column) => { const affected = record.columns.includes(column.name); return <span key={column.name} title={`${column.name}: ${affected ? 'issue detected' : record.state.replaceAll('_', ' ')}`} className={`h-3 flex-1 min-w-[3px] rounded-[2px] ${affected ? 'bg-rose-400' : tone[record.state] || 'bg-slate-200'}`} />; })}</span><span className="w-36 shrink-0 text-right text-[9px] text-slate-600">{record.state.replaceAll('_', ' ')}</span></button>)}</div>
        <div className="flex items-center justify-between pt-2"><button disabled={data.offset <= 0 || loading} onClick={() => onPage(Math.max(0, data.offset - data.limit))} className="text-[10px] text-emerald-800 disabled:text-slate-300">← Previous rows</button><span className="text-[9px] text-slate-400">Showing at most 24 rows per page</span><button disabled={data.offset + data.limit >= data.total_records || loading} onClick={() => onPage(data.offset + data.limit)} className="text-[10px] text-emerald-800 disabled:text-slate-300">Next rows →</button></div>
      </div>
      <div className="md:w-56 border-t md:border-t-0 md:border-l border-slate-100 md:pl-5 pt-4 md:pt-0">{chosen ? <><p className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">Record inspection</p><h3 className="font-mono text-xs mt-1">{chosen.row_id} · {chosen.state.replaceAll('_', ' ')}</h3><p className="text-[10px] text-slate-500 mt-2">{chosen.issue_density} finding(s) · confidence {chosen.confidence == null ? 'not estimated' : `${Math.round(chosen.confidence * 100)}%`}</p><ul className="mt-3 space-y-2">{chosen.evidence_references.map((id) => {const issue=issueById.get(id);return <li key={id} className="text-[10px] border-t pt-2"><p className="text-left font-semibold text-slate-800">{issue?.title || id}</p><p className="text-slate-500">{issue?.category} · {issue?.column || 'cross-column'}</p><p className="mt-1 text-slate-600">{issue?.description}</p>{issue?.evidence?.slice(0,2).map((evidence,index)=><p key={index} className="mt-1 text-slate-400">{evidence.label}: {evidence.detail}</p>)}{issue?.linked_proposal_id&&<button onClick={()=>window.location.hash=`/runs/${run.run_id}/studio?proposal=${encodeURIComponent(issue.linked_proposal_id!)}`} className="mt-1 text-emerald-800 underline">Open proposal</button>}</li>})}</ul><p className="mt-3 text-[9px] text-slate-400">{chosen.reasons.join(' · ')}</p></> : <div className="h-full min-h-28 flex flex-col justify-center text-center"><Search className="w-4 h-4 mx-auto text-slate-300"/><p className="text-[10px] text-slate-500 mt-2">Select a row to inspect its evidence references.</p></div>}</div>
    </div>
    <div className="px-5 py-2 border-t border-slate-100 flex flex-wrap gap-3 text-[9px] text-slate-500">{Object.entries(tone).map(([label,color])=><span className="flex items-center gap-1" key={label}><i className={`w-2 h-2 rounded-sm ${color}`} />{label.replaceAll('_',' ')}</span>)}<span>Rose cell = affected column</span></div>
  </Card>;
};

export const RelationshipAndAnomalyPanels: React.FC<{ run: RunState }> = ({ run }) => {
  const relationships = run.issues.filter((issue) => issue.category === 'relationship');
  const anomalies = run.issues.filter((issue) => issue.category === 'anomaly');
  return <div className="grid lg:grid-cols-2 gap-4">
    <Card className="overflow-hidden"><div className="px-5 py-4 border-b border-slate-200 flex items-center gap-3"><div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center"><Network className="w-4 h-4" /></div><div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Evidence-backed cross-column checks</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Relationship review</h2></div><span className="ml-auto text-xs font-mono">{relationships.length}</span></div><div className="p-4 space-y-3">{relationships.length ? relationships.map((issue) => <article id={`issue-${issue.id}`} key={issue.id} className="border-l-2 border-amber-400 pl-3 py-1"><div className="flex justify-between gap-3"><h3 className="text-xs font-semibold">{issue.title}</h3><span className="text-[9px] text-slate-500">{issue.affected_rows ?? issue.affected_cells} affected</span></div><p className="text-[10px] text-slate-600 mt-1">{issue.description}</p><div className="mt-2 flex flex-wrap gap-1">{issue.evidence?.map((e,index)=><span key={index} className="px-2 py-1 bg-slate-50 border rounded text-[9px]">{e.label}</span>)}</div><p className="text-[9px] text-slate-400 mt-1">Affected records: {(issue.affected_row_ids ?? []).slice(0,8).join(', ') || 'not enumerated'}</p></article>) : <p className="text-xs text-slate-500">No relationship findings were returned.</p>}<p className="text-[9px] text-slate-400 border-t pt-2">No cross-file/table foreign-key graph is inferred by this API.</p></div></Card>
    <Card className="overflow-hidden"><div className="px-5 py-4 border-b border-slate-200 flex items-center gap-3"><div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-700 flex items-center justify-center"><ShieldAlert className="w-4 h-4" /></div><div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Observed deviations</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Anomaly explorer</h2></div><span className="ml-auto text-xs font-mono">{anomalies.length}</span></div><div className="p-4 space-y-2">{anomalies.length ? anomalies.map((issue) => <article id={`issue-${issue.id}`} key={issue.id} className="group flex gap-3 border-b last:border-0 pb-3"><div className="w-12 shrink-0 text-center"><span className="block text-base font-bold text-rose-700">{issue.affected_rows ?? issue.affected_cells}</span><span className="text-[9px] text-slate-400">rows</span></div><div><h3 className="text-xs font-semibold">{issue.title} <span className="font-normal text-slate-500">· {issue.column || 'dataset'}</span></h3><p className="text-[10px] text-slate-600 mt-1">{issue.description}</p><div className="mt-1 space-y-1">{issue.evidence?.slice(0,2).map((e,index)=><p className="text-[9px] text-slate-500" key={index}>{e.label}: {e.detail}</p>)}</div><p className="text-[9px] text-slate-400 mt-1">Anomaly finding is not by itself a repair instruction.</p></div></article>) : <p className="text-xs text-slate-500">No anomaly findings were returned.</p>}</div></Card>
  </div>;
};
