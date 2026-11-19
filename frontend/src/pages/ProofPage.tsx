import React, { useEffect, useState } from 'react';
import { ShieldCheck, CheckCircle2, ChevronDown, ChevronUp, Lock, FlaskConical, HelpCircle, Copy, Fingerprint } from 'lucide-react';
import { useRun } from '../app/context/RunContext';
import { useRouter } from '../app/routes';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { downloadArtifact, getTrustPassport, type TrustPassport } from '../lib/api';

export const ProofPage: React.FC = () => {
  const { currentRun, isDemoFixture, verifyNow } = useRun();
  const { navigate } = useRouter();
  const [showHonestyPanel, setShowHonestyPanel] = useState(true);
  const [showQualityDetails, setShowQualityDetails] = useState(false);
  const [passport, setPassport] = useState<TrustPassport | null>(null);
  const [passportError, setPassportError] = useState('');
  const [copiedHash, setCopiedHash] = useState('');
  const [passportDownloadError, setPassportDownloadError] = useState('');
  const [passportDownloading, setPassportDownloading] = useState(false);
  const handlePassportDownload = async () => {
    if (!currentRun) return;
    setPassportDownloadError(''); setPassportDownloading(true);
    try { await downloadArtifact(currentRun.run_id, 'passport'); }
    catch (error) { setPassportDownloadError(error instanceof Error ? error.message : 'Passport download failed.'); }
    finally { setPassportDownloading(false); }
  };
  useEffect(() => {
    if (!currentRun?.run_id || !currentRun.is_applied || isDemoFixture) return;
    let active = true;
    void getTrustPassport(currentRun.run_id).then((value) => { if (active) setPassport(value); })
      .catch((error) => { if (active) setPassportError(error instanceof Error ? error.message : 'Trust Passport unavailable.'); });
    return () => { active = false; };
  }, [currentRun?.run_id, currentRun?.is_applied, isDemoFixture]);

  if (!currentRun) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">No active run loaded</h2>
        <Button onClick={() => navigate('/app')}>Go to Intake</Button>
      </div>
    );
  }

  const runId = currentRun.run_id;
  const verification = currentRun.verification;

  if (!currentRun.is_applied) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-6 text-center space-y-5">
        <div className="w-14 h-14 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
          <Lock className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-slate-900">Verification Locked</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Closed-loop verification runs after approved repairs are applied to the working copy.
          </p>
        </div>
        <Button onClick={() => navigate(`/runs/${runId}/studio`)}>Return to Repair Studio</Button>
      </div>
    );
  }

  if (!verification) return <div className="max-w-2xl mx-auto py-16 px-6 text-center space-y-4"><h2 className="text-lg font-bold">Verification not recorded yet</h2><p className="text-sm text-slate-500">Run the backend replay check to see actual results.</p><Button onClick={()=>void verifyNow()}>Run verification</Button></div>;

  // Calculate actual issue resolution considering refused and unapproved repairs
  const resolvedIssues = verification.issues.resolved;
  const refusedIssues = currentRun.proposals.filter(p=>p.decision==='refused').length;
  const remainingIssues = verification.issues.after;
  const score=(q:{completeness:number;validity:number;uniqueness:number;consistency:number})=>Math.round((q.completeness+q.validity+q.uniqueness+q.consistency)*25);

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 space-y-8">
      {/* Verification Header */}
      <div className="p-5 sm:p-6 bg-emerald-50/70 border border-emerald-200 rounded-2xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs font-mono text-emerald-800 font-semibold uppercase">Closed-Loop Verification</div>
            <h1 className="text-base sm:text-lg font-bold text-emerald-950">
              {verification.replay.match ? 'Verified: replay matches the working dataset' : 'Replay mismatch: review the run before export'}
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button size="sm" variant="secondary" onClick={() => navigate(`/runs/${runId}/export`)}>
            Go to Export Bundle
          </Button>
        </div>
      </div>

      {isDemoFixture && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-2 text-xs font-mono text-amber-800">
          <FlaskConical className="w-4 h-4 shrink-0 text-amber-600" />
          <span>
            Development Fixture Note: Verification metrics below reflect simulated calculations based on the planned
            GAP-5 contract specification.
          </span>
        </div>
      )}

      {/* 4 Claim Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Claim 1: Issues Delta */}
        <Card className="p-5 space-y-2 flex flex-col justify-between" borderLeftColor="emerald">
          <div>
            <div className="text-xs font-mono text-slate-500">1. Issues Delta</div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {verification.issues.before} → {remainingIssues}
            </div>
            <p className="text-xs text-slate-600 mt-0.5 font-medium">
              {resolvedIssues} resolved · {remainingIssues} unresolved
            </p>
            {refusedIssues > 0 && (
              <p className="text-[11px] text-indigo-700 font-mono mt-0.5">
                ({refusedIssues} refused to prevent corruption)
              </p>
            )}
          </div>
          <div className="text-[11px] text-emerald-700 font-medium flex items-center gap-1 pt-2 border-t border-slate-100">
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>{verification.issues.introduced} new issues introduced</span>
          </div>
        </Card>

        {/* Claim 2: Valid Cells Damaged */}
        <Card className="p-5 space-y-2 flex flex-col justify-between" borderLeftColor="emerald">
          <div>
            <div className="text-xs font-mono text-slate-500">2. Valid Cells Damaged</div>
            <div className="text-xl font-bold text-emerald-600 mt-1">{verification.valid_cells_damaged}</div>
            <p className="text-xs text-slate-500 mt-0.5">
              {verification.valid_cells_damaged === 0 ? 'No previously valid cells altered' : `${verification.valid_cells_damaged} previously valid cells changed`}
            </p>
          </div>
          <div className={`text-[11px] font-medium flex items-center gap-1 pt-2 border-t border-slate-100 ${verification.valid_cells_damaged === 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
            <span>{verification.valid_cells_damaged === 0 ? 'Integrity invariant passed' : 'Review detected changes to previously valid cells'}</span>
          </div>
        </Card>

        {/* Claim 3: Replay Check */}
        <Card className="p-5 space-y-2 flex flex-col justify-between" borderLeftColor="emerald">
          <div>
            <div className="text-xs font-mono text-slate-500">3. Replay Check</div>
            <div className="text-sm font-bold text-slate-900 font-mono mt-1 truncate">
              {verification.replay.replay_hash.slice(0, 18)}…
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {verification.replay.match ? 'Replay hash matches cleaned output' : 'Replay hash mismatch'}
            </p>
          </div>
          <div className={`text-[11px] font-medium flex items-center gap-1 pt-2 border-t border-slate-100 ${verification.replay.match ? 'text-emerald-700' : 'text-rose-700'}`}>
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
            <span>{verification.replay.match ? 'Deterministic replay matched' : 'Replay hash mismatch'}</span>
          </div>
        </Card>

        {/* Claim 4: Quality Score */}
        <Card className="p-5 space-y-2 flex flex-col justify-between" borderLeftColor="emerald">
          <div>
            <div className="text-xs font-mono text-slate-500 flex items-center justify-between">
              <span>4. Quality Score</span>
              <button
                onClick={() => setShowQualityDetails(!showQualityDetails)}
                className="text-slate-400 hover:text-slate-600"
                title="View score definition & calculation source"
              >
                <HelpCircle className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {score(verification.quality_dimensions.before)}% → <span className="text-emerald-600">{score(verification.quality_dimensions.after)}%</span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Backend quality dimensions summary
            </p>
          </div>
          <div className="text-[10px] text-slate-400 leading-tight pt-2 border-t border-slate-100">
            Arithmetic mean of the four backend quality dimensions
          </div>
        </Card>
      </div>

      {!isDemoFixture && <Card className="overflow-hidden border-emerald-200">
        <div className="p-5 sm:p-6 bg-emerald-50/60 border-b border-emerald-100 flex flex-wrap justify-between items-center gap-3">
          <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl bg-white border border-emerald-100 flex items-center justify-center text-emerald-700"><Fingerprint className="w-5 h-5" /></div><div><p className="text-[10px] font-mono uppercase tracking-wider text-emerald-800">Run integrity record</p><h2 className="text-base font-bold text-slate-900">DataFix Trust Passport</h2></div></div>
          <Button size="sm" variant="secondary" onClick={() => void handlePassportDownload()} disabled={passportDownloading}>{passportDownloading ? 'Preparing…' : 'Download Passport JSON'}</Button>
        </div>
        {passportDownloadError && <p role="alert" className="px-5 pt-3 text-xs text-rose-700">{passportDownloadError}</p>}
        {passport ? <div className="p-5 sm:p-6 space-y-5">
          <div className="flex flex-wrap justify-between gap-3 text-xs"><div><p className="text-[10px] text-slate-500 uppercase tracking-wider">Dataset</p><p className="font-semibold mt-1">{passport.original_filename}</p><code className="text-[9px] text-slate-400">{passport.run_id}</code></div><div className="text-right"><p className="text-[10px] text-slate-500 uppercase tracking-wider">Replay status</p><p className={`font-semibold mt-1 ${passport.verification_status === 'verified' ? 'text-emerald-700' : 'text-amber-700'}`}>{passport.verification_status.replaceAll('_', ' ')}</p><p className="text-[9px] text-slate-400">No digital signature is claimed</p></div></div>
          <div className="grid md:grid-cols-2 gap-3">{[['Original SHA-256',passport.original_sha256],['Cleaned SHA-256',passport.cleaned_sha256],['Passport SHA-256',passport.passport_sha256]].map(([label,hash])=><div key={label} className="p-3 bg-slate-50 border border-slate-200 rounded-xl min-w-0"><div className="flex items-center justify-between gap-2"><p className="text-[9px] uppercase tracking-wider font-mono text-slate-500">{label}</p><button className="text-slate-500 hover:text-emerald-700" aria-label={`Copy ${label}`} onClick={() => {void navigator.clipboard.writeText(hash);setCopiedHash(label);window.setTimeout(()=>setCopiedHash(''),1400)}}><Copy className="w-3.5 h-3.5" /></button></div><code className="block mt-2 text-[9px] text-slate-700 break-all">{hash}</code>{copiedHash===label&&<span className="text-[9px] text-emerald-700">Copied</span>}</div>)}</div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">{[['Initial findings',passport.initial_issue_count],['Proposals',passport.proposal_count],['Applied operations',passport.applied_operations.filter((op)=>op.active).length],['Unresolved',passport.unresolved_count]].map(([label,value])=><div key={String(label)} className="border-l-2 border-emerald-500 pl-3 py-1"><p className="text-[9px] uppercase font-mono text-slate-500">{label}</p><p className="text-lg font-bold text-slate-900">{value}</p></div>)}</div>
          <div className="grid md:grid-cols-2 gap-4 border-t border-slate-100 pt-4"><div><p className="text-[10px] uppercase font-mono text-slate-500">Quality dimensions · before → after</p><div className="mt-2 space-y-2">{(['completeness','validity','uniqueness','consistency'] as const).map((name)=>{const before=passport.quality_before[name];const after=passport.quality_after[name];return <div key={name}><div className="flex justify-between text-[9px] text-slate-600"><span>{name}</span><span>{(before*100).toFixed(1)}% → {(after*100).toFixed(1)}%</span></div><div className="mt-1 h-1.5 rounded-full bg-slate-100 overflow-hidden"><div className="h-full bg-emerald-600 transition-all duration-500" style={{width:`${Math.max(0,Math.min(100,after*100))}%`}} /></div></div>})}</div></div><div><p className="text-[10px] uppercase font-mono text-slate-500">Audit sequence</p><ol className="mt-2 border-l border-emerald-200 pl-4 space-y-2 text-[10px] text-slate-600"><li>Original preserved · {passport.original_row_count} rows / {passport.original_column_count} columns</li><li>{passport.user_approvals} approvals · {passport.rejections} rejections · {passport.refused_repairs} refused</li><li>{passport.applied_operations.filter((op)=>op.active).length} active operation(s) recorded</li><li>{passport.replay_matches ? 'Replay hash matches' : passport.verification_status === 'not_run' ? 'Replay not run' : 'Replay mismatch'}{passport.replay_hash ? ` · ${passport.replay_hash.slice(0,16)}…` : ''}</li></ol></div></div>
          <details className="border-t border-slate-100 pt-3"><summary className="cursor-pointer text-[10px] text-emerald-800 font-medium">Passport limitations and integrity notes</summary><ul className="mt-2 space-y-1">{passport.limitations.map((note,index)=><li key={index} className="text-[9px] text-slate-500">{note}</li>)}</ul><p className="mt-2 text-[9px] text-slate-400">Engine {passport.engine_version} · issued {new Date(passport.generated_at).toLocaleString()}</p></details>
        </div> : <div className="p-5 text-xs text-slate-500">{passportError ? `Passport could not be loaded: ${passportError}` : 'Loading run-backed passport…'}</div>}
      </Card>}

      {/* Quality Score Explainer Modal/Callout */}
      {showQualityDetails && (
        <Card className="p-5 bg-slate-50/80 border-slate-200 text-xs space-y-2">
          <div className="font-bold text-slate-900 flex items-center justify-between">
            <span>Quality Score Definition & Source (GAP-5)</span>
            <button
              onClick={() => setShowQualityDetails(false)}
              className="text-slate-400 hover:text-slate-600 font-mono"
            >
              Close ✕
            </button>
          </div>
          <p className="text-slate-600 leading-relaxed">
            <strong>Calculation Method:</strong> The displayed summary is the arithmetic mean of the four backend dimensions: completeness, validity, uniqueness and consistency.
          </p>
          <ul className="list-disc list-inside space-y-1 text-slate-600 pl-1">
            <li>
              <strong>Before ({score(verification.quality_dimensions.before)}%):</strong> Backend quality dimensions before applying the recorded operations.
            </li>
            <li>
              <strong>After ({score(verification.quality_dimensions.after)}%):</strong> Backend quality dimensions after apply and replay; {resolvedIssues} issue(s) resolved and {remainingIssues} remain.
            </li>
            <li>
              <strong>Source:</strong> Actual verification response from the current backend run. Displayed score is the arithmetic mean of its four quality dimensions.
            </li>
          </ul>
        </Card>
      )}

      {/* "What this does and does not prove" Panel */}
      <Card className="overflow-hidden">
        <button
          onClick={() => setShowHonestyPanel(!showHonestyPanel)}
          className="w-full px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-left hover:bg-slate-100/60 transition-colors"
        >
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold">
              Honesty & Epistemic Boundaries
            </div>
            <h2 className="text-sm font-bold text-slate-900">What this does and does not prove</h2>
          </div>
          {showHonestyPanel ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </button>

        {showHonestyPanel && (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 text-xs text-slate-700">
            <div className="space-y-2 bg-emerald-50/40 p-4 rounded-xl border border-emerald-100">
              <div className="font-semibold text-emerald-950 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>What is proven</span>
              </div>
              <ul className="list-disc list-inside space-y-1.5 text-slate-600 pl-1 leading-relaxed">
                <li>Every applied change is recorded in the ordered operation log.</li>
                <li>Replaying the log on the untouched original reproduces the exported result byte-for-byte.</li>
                <li>Zero cells that were valid under active detectors were altered or corrupted.</li>
                <li>Refused repairs remain safely unapplied to prevent fabricated values.</li>
              </ul>
            </div>

            <div className="space-y-2 bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div className="font-semibold text-slate-900">What is NOT proven</div>
              <ul className="list-disc list-inside space-y-1.5 text-slate-500 pl-1 leading-relaxed">
                <li>Does not prove semantic real-world business correctness of user inputs.</li>
                <li>Does not guarantee all potential errors in unprofiled columns were detected.</li>
                <li>Quality score reflects rule detector pass rates, not external benchmark ground truth.</li>
                <li>Unresolved or refused issues are not claimed as fixed without explicit human confirmation.</li>
              </ul>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
