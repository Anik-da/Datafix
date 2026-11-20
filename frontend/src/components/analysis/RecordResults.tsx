import React, { useMemo } from 'react';
import { Download } from 'lucide-react';
import type { RunState } from '../../lib/contract-types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';

type RecordResult = {
  rowId: string;
  category: string;
  issue: string;
  action: string;
  needsReview: boolean;
};

function csvCell(value: string) {
  return `"${value.replaceAll('"', '""')}"`;
}

export const RecordResults: React.FC<{ run: RunState }> = ({ run }) => {
  const results = useMemo(() => {
    const rows = new Map<number, { categories: Set<string>; issues: Set<string>; actions: Set<string>; needsReview: boolean }>();
    for (let index = 1; index <= run.profile.row_count; index += 1) {
      rows.set(index, { categories: new Set(), issues: new Set(), actions: new Set(), needsReview: false });
    }

    for (const issue of run.issues) {
      const related = run.proposals.filter((proposal) => proposal.issue_ids.includes(issue.id));
      for (const sourceId of issue.affected_row_ids ?? []) {
        const match = /^row_(\d+)$/.exec(sourceId);
        if (!match) continue;
        const result = rows.get(Number(match[1]));
        if (!result) continue;
        result.categories.add(issue.category.replaceAll('_', ' '));
        result.issues.add(issue.title || issue.category);
        if (related.length === 0) {
          result.actions.add('Review source; no safe repair proposed');
          result.needsReview = true;
        } else {
          for (const proposal of related) {
            result.actions.add(proposal.title);
            const changedRows = proposal.simulation?.impact?.direct_row_ids ?? [];
            const sampleRows = proposal.simulation?.sample_diff.map((diff) => String(diff.row_id)) ?? [];
            const proposalCoversRow = changedRows.includes(sourceId) || sampleRows.includes(sourceId);
            if (proposal.decision !== 'auto_apply' || !proposalCoversRow) result.needsReview = true;
          }
        }
      }
    }

    return [...rows.entries()].map(([index, value]): RecordResult => ({
      rowId: run.source_row_labels?.[index - 1] || `row_${index}`,
      category: value.categories.size ? [...value.categories].join('; ') : 'Data Quality Issue',
      issue: value.issues.size ? [...value.issues].join('; ') : 'No issue detected',
      action: value.actions.size ? [...value.actions].join('; ') : 'No repair expected',
      needsReview: value.needsReview,
    }));
  }, [run]);

  const reviewCount = results.filter((row) => row.needsReview).length;
  const issueCount = results.filter((row) => row.issue !== 'No issue detected').length;

  const download = () => {
    const lines = [
      ['test_case_id', 'test_category', 'detected_issue', 'recommended_action', 'needs_human_review'],
      ...results.map((row) => [row.rowId, row.category, row.issue, row.action, row.needsReview ? 'Yes' : 'No']),
    ];
    const blob = new Blob([`\uFEFF${lines.map((line) => line.map(csvCell).join(',')).join('\r\n')}`], {
      type: 'text/csv;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${run.filename.replace(/\.[^.]+$/, '')}_row_results.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Record-by-record output</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-900">Detected issue and recommended action</h2>
          <p className="mt-1 text-xs text-slate-500">Rows are source data rows after the header. Review flags come from the actual findings and Safety Gate.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={download} icon={<Download className="h-3.5 w-3.5" />}>
          Download results CSV
        </Button>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 border-b border-slate-100 bg-slate-50/60 px-5 py-3 text-xs text-slate-600">
        <span><strong className="text-slate-900">{results.length}</strong> rows analyzed</span>
        <span><strong className="text-slate-900">{issueCount}</strong> rows with findings</span>
        <span><strong className="text-amber-800">{reviewCount}</strong> rows needing human review</span>
      </div>
      <div className="max-h-[560px] overflow-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 bg-slate-50 text-[10px] font-mono uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3">Test / record ID</th>
              <th className="px-5 py-3">Category</th>
              <th className="px-5 py-3">Detected issue</th>
              <th className="px-5 py-3">Recommended action</th>
              <th className="px-5 py-3">Needs human review</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {results.map((row) => (
              <tr key={row.rowId} className="align-top hover:bg-slate-50/70">
                <td className="whitespace-nowrap px-5 py-3 font-mono text-slate-700">{row.rowId}</td>
                <td className="px-5 py-3 text-slate-600">{row.category}</td>
                <td className="max-w-[260px] px-5 py-3 text-slate-800">{row.issue}</td>
                <td className="max-w-[360px] px-5 py-3 text-slate-700">{row.action}</td>
                <td className="px-5 py-3">
                  <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${row.needsReview ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-800'}`}>
                    {row.needsReview ? 'Yes' : 'No'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
