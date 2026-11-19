import React, { useState } from 'react';
import { Download, FileText, CheckCircle2, Lock, FlaskConical, AlertCircle } from 'lucide-react';
import { useRun } from '../app/context/RunContext';
import { useRouter } from '../app/routes';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { downloadArtifact } from '../lib/api';

export const ExportPage: React.FC = () => {
  const { currentRun, isDemoFixture, operations } = useRun();
  const { navigate } = useRouter();
  const [downloadedItems, setDownloadedItems] = useState<Record<string, boolean>>({});
  const [downloadErrors, setDownloadErrors] = useState<Record<string, string>>({});

  if (!currentRun) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">No active run loaded</h2>
        <Button onClick={() => navigate('/app')}>Go to Intake</Button>
      </div>
    );
  }

  const runId = currentRun.run_id;

  if (!currentRun.is_applied) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-6 text-center space-y-5">
        <div className="w-14 h-14 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
          <Lock className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-slate-900">Export Bundle Locked</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            The repaired dataset and modification logs can be downloaded once the repair plan has been applied.
          </p>
        </div>
        <Button onClick={() => navigate(`/runs/${runId}/studio`)}>Return to Repair Studio</Button>
      </div>
    );
  }

  const handleDownload = async (key: string, filename: string, content: string, type: string) => {
    if (!isDemoFixture) {
      const artifact = ({ cleaned_csv: 'cleaned', mod_log: 'log', recipe: 'recipe', quality_report: 'report', passport: 'passport' } as const)[key as 'cleaned_csv'|'mod_log'|'recipe'|'quality_report'|'passport'];
      try { setDownloadErrors(prev=>({...prev,[key]:''})); await downloadArtifact(runId, artifact); setDownloadedItems(prev=>({...prev,[key]:true})); }
      catch (error) { setDownloadErrors(prev=>({...prev,[key]:error instanceof Error ? error.message : 'Download failed. Please try again.'})); }
      return;
    }
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setDownloadedItems((prev) => ({ ...prev, [key]: true }));
  };

  const exportFiles = [
    {
      key: 'cleaned_csv',
      title: 'Cleaned Dataset',
      format: currentRun.backend_run?.format_metadata?.format === 'xlsx' ? 'XLSX' : 'CSV',
      description: 'The repaired dataset with all approved operations applied.',
      filename: `cleaned_${currentRun.filename}`,
      content:
        'customer_id,full_name,email,city,joined_on,age\nC001,Asha Rao,asha@example.test,Bengaluru,2026-02-10,24\nC002,Rahul Sen,rahul@example.test,,2026-03-14,29\nC003,Meera Das,meera@example.test,Mysuru,2026-04-02,\nC005,John Mathew,john.example.test,Bengaluru,,34\n',
      mime: 'text/csv',
    },
    {
      key: 'mod_log',
      title: 'Modification Log',
      format: 'JSON',
      description: 'Audit log of every altered cell: old value, new value, reason, and confidence.',
      filename: `modification_log_${runId}.json`,
      content:
        'seq,row_id,column,before,after,decision,confidence\n1,5,customer_id,C003,∅ removed,auto_apply,1.00\n2,6,joined_on,not-a-date,∅ null,needs_approval,0.62\n',
      mime: 'application/json',
    },
    {
      key: 'recipe',
      title: 'Replay Recipe',
      format: 'JSON',
      description: 'Deterministic ordered recipe to reproduce the cleaned dataset from the original.',
      filename: `recipe_${runId}.json`,
      content: JSON.stringify({ run_id: runId, filename: currentRun.filename, applied_operations: 2 }, null, 2),
      mime: 'application/json',
    },
    {
      key: 'quality_report',
      title: 'Quality & Invariant Report',
      format: 'JSON',
      description: 'Summary of initial issues, invariants evaluated, and verification proofs.',
      filename: `quality_report_${runId}.json`,
      content: JSON.stringify({ run_id: runId, verified: true, valid_cells_damaged: 0 }, null, 2),
      mime: 'application/json',
    },
    { key:'passport', title:'DataFix Trust Passport', format:'Verified JSON', description:'Run-level provenance, decisions, verification and artifact hashes from the backend.', filename:`passport_${runId}.json`, content:'{}', mime:'application/json' },
  ];

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 space-y-8">
      <div>
        <div className="text-[11px] font-mono tracking-wider text-slate-500 uppercase">Export Center</div>
        <h1 className="font-serif text-2xl font-bold text-slate-900 mt-1">Export Bundle</h1>
        <p className="text-xs text-slate-500 mt-1">
          Download the repaired data, verification proofs, and modification logs for your pipeline.
        </p>
      </div>

      {!isDemoFixture && <Card className="p-5 sm:p-6 space-y-4">
        <div className="flex flex-wrap justify-between items-start gap-3"><div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Deterministic workflow</p><h2 className="text-sm font-semibold text-slate-900 mt-1">Applied recipe sequence</h2><p className="text-[10px] text-slate-500 mt-1">Ordered from this run’s operation history. Exported recipe is still re-evaluated when used with another dataset.</p></div><span className="text-[10px] text-slate-500">{operations.filter((op)=>op.active).length} active operation(s)</span></div>
        <div className="flex flex-wrap items-center gap-2">{operations.filter((op)=>op.active).map((op,index)=><React.Fragment key={op.op_id}><div className="min-w-36 flex-1 border border-emerald-100 bg-emerald-50/60 rounded-xl p-3"><p className="text-[9px] uppercase font-mono text-emerald-800">Step {index+1} · {op.decided_by}</p><p className="text-xs font-semibold mt-1 text-slate-900">{op.op.replaceAll('_',' ')}</p><p className="text-[10px] text-slate-600 mt-1">{op.column || 'whole record'} · {op.cells_changed} cell(s)</p><code className="text-[8px] text-slate-400 block mt-1 truncate">{op.op_id}</code></div>{index < operations.filter((item)=>item.active).length-1 && <span aria-hidden="true" className="text-emerald-700">→</span>}</React.Fragment>)}{operations.filter((op)=>op.active).length===0&&<p className="text-xs text-slate-500">No active operations in the run ledger.</p>}</div>
        <p className="text-[10px] text-slate-500 border-t border-slate-100 pt-3">Recipe import and cross-dataset compatibility review are not available in the current API.</p>
      </Card>}

      {isDemoFixture ? (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3 text-xs text-amber-900">
          <FlaskConical className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold">Development Fixture Mode Active</span>
            <p className="text-amber-800 leading-relaxed">
              The files below are simulated demo artifacts generated from <code className="font-mono">sample_data/customers_demo.csv</code>.
              Backend bundle packaging (<code className="font-mono">GET /api/v1/runs/&#123;id&#125;/export</code>) is planned for Phase 2.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-start gap-3 text-xs text-slate-700">
          <AlertCircle className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-slate-900">Live backend exports</span>
            <p className="text-slate-500 leading-relaxed">
              Every live download below is generated from this run by the backend, including the Trust Passport.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {exportFiles.map((file) => {
          const isDownloaded = !!downloadedItems[file.key];
          return (
            <Card key={file.key} className="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-700 shrink-0">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-bold text-slate-900 flex items-center gap-2 flex-wrap">
                    <span>{file.title}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 font-mono">
                      {file.format}
                    </span>
                    {isDemoFixture && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-100 text-amber-800 font-mono">
                        Fixture
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">{file.description}</p>
                  {downloadErrors[file.key] && <p role="alert" className="text-xs text-rose-700 mt-1">{downloadErrors[file.key]}</p>}
                </div>
              </div>

              <div className="shrink-0 w-full sm:w-auto">
                {isDemoFixture ? (
                  <Button
                    size="sm"
                    variant={isDownloaded ? 'secondary' : 'primary'}
                    className="w-full sm:w-auto"
                    onClick={() => void handleDownload(file.key, file.filename, file.content, file.mime)}
                    icon={
                      isDownloaded ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )
                    }
                  >
                    {isDownloaded ? 'Downloaded' : 'Download Demo File'}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant={isDownloaded ? 'secondary' : 'primary'}
                    className="w-full sm:w-auto"
                    onClick={() => void handleDownload(file.key, file.filename, file.content, file.mime)}
                    icon={isDownloaded
                      ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      : <Download className="w-3.5 h-3.5" />}
                  >
                    {isDownloaded ? 'Downloaded' : 'Download file'}
                  </Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
