import React, { useEffect, useState } from 'react';
import { ArrowRight, FileText, ShieldCheck } from 'lucide-react';
import { useRun } from '../app/context/RunContext';
import { useRouter } from '../app/routes';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import type { ColumnProfile } from '../lib/contract-types';
import { getUncertainty, type UncertaintyResponse } from '../lib/api';
import { FingerprintExplorer, RelationshipAndAnomalyPanels, SchemaExplorer, UncertaintyMap } from '../components/analysis/IntelligencePanels';
import { IssueExplainer } from '../components/analysis/IssueExplainer';

export const OverviewPage: React.FC = () => {
  const { currentRun } = useRun();
  const { navigate } = useRouter();
  const [heatmap, setHeatmap] = useState<UncertaintyResponse | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState('');
  const [heatmapOffset, setHeatmapOffset] = useState(0);
  useEffect(() => {
    if (!currentRun?.run_id) return;
    let active = true;
    setHeatmapLoading(true); setHeatmapError('');
    void getUncertainty(currentRun.run_id, heatmapOffset).then((result) => { if (active) setHeatmap(result); })
      .catch((error) => { if (active) { setHeatmap(null); setHeatmapError(error instanceof Error ? error.message : 'Uncertainty data could not be loaded.'); } })
      .finally(() => { if (active) setHeatmapLoading(false); });
    return () => { active = false; };
  }, [currentRun?.run_id, heatmapOffset]);

  if (!currentRun) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center space-y-4">
        <FileText className="w-12 h-12 text-slate-400 mx-auto" />
        <h2 className="text-xl font-bold text-slate-800">No active run selected</h2>
        <p className="text-sm text-slate-500">Upload a CSV or XLSX file to inspect its profile and detected issues.</p>
        <Button onClick={() => navigate('/app')}>Return to Intake</Button>
      </div>

    );
  }

  const { profile } = currentRun;
  const runId = currentRun.run_id;

  return (
    <div className="max-w-6xl mx-auto py-8 px-6 space-y-8">
      {/* Top Banner with Studio CTA */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="text-[11px] font-mono tracking-wider text-slate-500 uppercase">
            Dataset Profile & Quality Overview
          </div>
          <h1 className="font-serif text-2xl font-bold text-slate-900 mt-1">{profile.filename}</h1>
          <p className="text-xs text-slate-500 font-mono mt-1">
            {profile.row_count.toLocaleString()} rows · {profile.column_count} columns ·{' '}
            {profile.total_cells.toLocaleString()} cells · Read-only scan
          </p>
        </div>

        <Button
          size="lg"
          variant="primary"
          onClick={() => navigate(`/runs/${runId}/studio`)}
          icon={<ArrowRight className="w-4 h-4 order-last ml-1" />}
        >
          Open Repair Studio
        </Button>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <Card className="p-4">
          <div className="text-xs font-mono text-slate-500">Rows</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {profile.row_count.toLocaleString()}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs font-mono text-slate-500">Columns</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {profile.column_count}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs font-mono text-slate-500">Total Cells</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {profile.total_cells.toLocaleString()}
          </div>
        </Card>

        <Card
          className="p-4"
          borderLeftColor={profile.missing_cells > 0 ? 'amber' : 'emerald'}
        >
          <div className="text-xs font-mono text-slate-500">Missing Cells</div>
          <div
            className={`text-2xl font-bold mt-1 ${
              profile.missing_cells > 0 ? 'text-amber-600' : 'text-emerald-600'
            }`}
          >
            {profile.missing_cells.toLocaleString()}
          </div>
        </Card>

        <Card
          className="p-4"
          borderLeftColor={profile.duplicate_rows > 0 ? 'amber' : 'emerald'}
        >
          <div className="text-xs font-mono text-slate-500">Duplicate Rows</div>
          <div
            className={`text-2xl font-bold mt-1 ${
              profile.duplicate_rows > 0 ? 'text-amber-600' : 'text-emerald-600'
            }`}
          >
            {profile.duplicate_rows.toLocaleString()}
          </div>
        </Card>
      </div>

      {currentRun.upload_warnings?.length ? <Card className="p-4 border-amber-200 bg-amber-50/60"><p className="text-xs font-semibold text-amber-900">Some rows need a closer look</p><ul className="mt-1 list-disc list-inside text-xs text-amber-800">{currentRun.upload_warnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul><p className="text-[10px] text-amber-700 mt-2">DataFix kept the original file unchanged and analyzed the rows it could safely read.</p></Card> : null}

      <SchemaExplorer run={currentRun} />
      <IssueExplainer run={currentRun} onOpenProposal={(proposalId) => navigate(`/runs/${runId}/studio?proposal=${encodeURIComponent(proposalId)}`)} />
      <FingerprintExplorer run={currentRun} />
      {heatmap && <UncertaintyMap run={currentRun} data={heatmap} onPage={setHeatmapOffset} loading={heatmapLoading} />}
      {heatmapLoading && !heatmap && <Card className="p-5 text-xs text-slate-500">Loading measured row uncertainty…</Card>}
      {heatmapError && <Card className="p-5 text-xs text-rose-700 border-rose-200">Uncertainty view unavailable: {heatmapError}</Card>}
      <RelationshipAndAnomalyPanels run={currentRun} />

      {/* Column Health Statistics Table */}
      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Column Structure & Missingness</h2>
            <p className="text-xs text-slate-500 mt-0.5">Observed value types, missing information and distinct values</p>
          </div>
          <span className="text-xs font-mono text-slate-500">{profile.columns.length} columns</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 font-mono bg-slate-50/30">
                <th className="px-6 py-3 font-semibold">Column Name</th>
                <th className="px-6 py-3 font-semibold">Inferred Type</th>
                <th className="px-6 py-3 font-semibold">Missing Count</th>
                <th className="px-6 py-3 font-semibold">Missing %</th>
                <th className="px-6 py-3 font-semibold">Distinct Values</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {profile.columns.map((col: ColumnProfile) => (
                <tr key={col.name} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-6 py-3.5 font-medium text-slate-900 font-mono">{col.name}</td>
                  <td className="px-6 py-3.5 font-mono">
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[11px]">
                      {col.data_type}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 font-mono">
                    {col.missing_count > 0 ? (
                      <span className="text-amber-700 font-semibold">{col.missing_count}</span>
                    ) : (
                      <span className="text-slate-500">0</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 font-mono">
                    {col.missing_percent > 0 ? (
                      <span className="text-amber-700">{col.missing_percent}%</span>
                    ) : (
                      <span className="text-slate-400">0%</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 font-mono text-slate-700">{col.distinct_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Backend Profiling Notes Box */}
      <div className="bg-slate-50 border border-slate-200/90 rounded-xl p-5 text-xs text-slate-600 space-y-2">
        <div className="font-semibold text-slate-800 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Deterministic Profiling Guarantee</span>
        </div>
        <ul className="list-disc list-inside space-y-1 text-slate-500 pl-1">
          {profile.notes.map((note: string, idx: number) => (
            <li key={idx}>{note}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};
