from __future__ import annotations
import json, os, sys, tempfile, time
import hashlib
from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parent
BACKEND=ROOT.parent/'backend'; sys.path.insert(0,str(BACKEND))
os.environ['LLM_ENABLED']='false'
from app.main import app
from app import main
from app.storage import RunStorage

def peak_rss_mb():
    """Measure process peak resident memory without adding a runtime dependency."""
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
        counters=Counters(); counters.cb=ctypes.sizeof(counters)
        psapi=ctypes.WinDLL('psapi'); kernel32=ctypes.WinDLL('kernel32')
        kernel32.GetCurrentProcess.restype=ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            return round(counters.PeakWorkingSetSize/(1024*1024),2)
        return None
    try:
        import resource
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak/(1024*1024 if sys.platform=='darwin' else 1024),2)
    except (ImportError,AttributeError): return None

EXPECTED_CATEGORY={'missing':'missing','duplicate':'duplicate','invalid_format':'invalid_format','inconsistent':'inconsistent','anomaly':'anomaly','relationship':'relationship'}
def main_benchmark():
    dirty_path=ROOT/'orders_dirty.csv'; truth_path=ROOT/'orders_clean_truth.csv'
    manifest=json.loads((ROOT/'orders_error_manifest.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='datafix-benchmark-') as tmp:
        main.storage=RunStorage(Path(tmp)); client=TestClient(app); started=time.perf_counter()
        uploaded=client.post('/api/v1/runs',files={'file':(dirty_path.name,dirty_path.read_bytes(),'text/csv')})
        if uploaded.status_code!=201: raise SystemExit(f'upload failed {uploaded.status_code}: {uploaded.text}')
        rid=uploaded.json()['run']['id']; analyzed=client.post(f'/api/v1/runs/{rid}/analyze')
        if analyzed.status_code!=200: raise SystemExit(f'analyze failed {analyzed.status_code}: {analyzed.text}')
        analysis=analyzed.json()
        original_bytes=main.storage.get(rid)['original']; original_sha=hashlib.sha256(original_bytes).hexdigest()
        refused=[p for p in analysis['proposals'] if p['gate']['decision']=='refused']
        if not refused: raise SystemExit('canonical acceptance requires an explicit refused proposal')
        refused_override_status=client.post(f'/api/v1/runs/{rid}/decisions',json={'decisions':[{'proposal_id':refused[0]['id'],'action':'approve'}]}).status_code
        if refused_override_status!=409: raise SystemExit('refused proposal was unexpectedly overridable')
        pending=[p for p in analysis['proposals'] if p['gate']['decision']=='needs_approval']
        if pending:
            decision=client.post(f'/api/v1/runs/{rid}/decisions',json={'decisions':[{'proposal_id':p['id'],'action':'approve'} for p in pending]})
            if decision.status_code!=200: raise SystemExit(f'decisions failed: {decision.text}')
        decision_status=decision.status_code if pending else None
        applied=client.post(f'/api/v1/runs/{rid}/apply')
        if applied.status_code!=200 or applied.json()['status']!='applied': raise SystemExit(f'apply failed: {applied.text}')
        verified=client.post(f'/api/v1/runs/{rid}/verify')
        if verified.status_code!=200: raise SystemExit(f'verify failed: {verified.text}')
        verification=verified.json()
        export_responses={name:client.get(f'/api/v1/runs/{rid}/export/{name}') for name in ('cleaned','report','log','recipe')}
        if any(response.status_code!=200 for response in export_responses.values()): raise SystemExit('one or more exports failed')
        if any('attachment;' not in response.headers.get('content-disposition','') for response in export_responses.values()): raise SystemExit('export is missing downloadable attachment metadata')
        clean=pd.read_csv(pd.io.common.BytesIO(export_responses['cleaned'].content),dtype=str,keep_default_na=False)
        json_exports={name:json.loads(export_responses[name].content) for name in ('report','log','recipe')}
        truth_frame=pd.read_csv(truth_path,dtype=str,keep_default_na=False)
        truth=truth_frame.set_index('order_id'); dirty=pd.read_csv(dirty_path,dtype=str,keep_default_na=False)
        operations_response=client.get(f'/api/v1/runs/{rid}/operations')
        if operations_response.status_code!=200: raise SystemExit(f'operations failed: {operations_response.text}')
        operations=main.storage.list_operations(rid,active_only=True)
        changes=[entry for op in operations for entry in op['cell_log'] if entry.get('action')=='cell_changed']
        removed=[entry for op in operations for entry in op['cell_log'] if entry.get('action')=='row_removed']
        correct_changes=[]
        change_audit=[]
        for change in changes:
            idx=int(change['row_id'].split('_')[1])-1
            if idx<len(dirty):
                oid=dirty.iloc[idx]['order_id']
                matches=oid in truth.index and truth.loc[oid,change['column']]==change['after']
                change_audit.append({'row_id':change['row_id'],'column':change['column'],'before':change['before'],'after':change['after'],'matches_clean_truth':matches})
                if matches:
                    correct_changes.append(change)
        correct_duplicate_removals=sum(1 for item in removed if not bool(clean['order_id'].duplicated().any()))
        action_total=len(changes)+len(removed); correct_actions=len(correct_changes)+correct_duplicate_removals
        repair_precision=correct_actions/max(1,action_total)
        actionable=[e for e in manifest['errors'] if e['expected_outcome'] in {'auto_apply_if_simulation_passes','needs_approval'}]
        repaired=[]
        for e in actionable:
            if e['category']=='duplicate':
                if not clean['order_id'].duplicated().any(): repaired.append(e['error_id'])
                continue
            source=e.get('source_row_id') or e['row_id']; idx=int(source.split('_')[1])-1
            oid=dirty.iloc[idx]['order_id']
            rows=clean.loc[clean.order_id==oid,e['column']]
            if len(rows) and all(value==truth.loc[oid,e['column']] for value in rows.tolist()): repaired.append(e['error_id'])
        repair_recall=len(repaired)/max(1,len(actionable))
        expected={(e['category'],e['row_id']) for e in manifest['errors']}
        expected |= {(x['category'],x['row_id']) for x in manifest.get('preservation_cases',[]) if 'category' in x and 'row_id' in x}
        predicted={(issue['category'],rid_ref) for issue in analysis['issues'] for rid_ref in issue['affected_row_ids']}
        true_detected=expected & predicted
        detection_precision=len(true_detected)/max(1,len(predicted)); detection_recall=len(true_detected)/max(1,len(expected))
        total_cells=len(clean)*len(clean.columns); unequal=0
        for _,row in clean.iterrows():
            if row['order_id'] not in truth.index: unequal+=1; continue
            expected_row=truth.loc[row['order_id']]
            unequal += sum(1 for col in clean.columns if col!='order_id' and row[col]!=expected_row[col])
        repaired_case_status=[]
        for e in actionable:
            if e['category']=='duplicate':
                repaired_case_status.append({'error_id':e['error_id'],'repaired':not clean['order_id'].duplicated().any()}); continue
            source=e.get('source_row_id') or e['row_id']; idx=int(source.split('_')[1])-1; oid=dirty.iloc[idx]['order_id']
            rows=clean.loc[clean.order_id==oid,e['column']]
            repaired_case_status.append({'error_id':e['error_id'],'repaired':bool(len(rows) and all(value==truth.loc[oid,e['column']] for value in rows.tolist()))})
        result={
          'dataset':'synthetic regression only','seed':manifest['seed'],'rows_uploaded':uploaded.json()['run']['row_count'],'columns':uploaded.json()['run']['column_count'],
          'stage_statuses':{'upload':uploaded.status_code,'analyze':analyzed.status_code,'refused_override':refused_override_status,'decisions':decision_status,'apply':applied.status_code,'operations':operations_response.status_code,'verify':verified.status_code,'exports':{name:response.status_code for name,response in export_responses.items()}},
          'injected_error_cases':len(manifest['errors']),'detector_findings':len(predicted),'detection_true_positives':len(true_detected),
          'detection_precision':round(detection_precision,4),'detection_recall':round(detection_recall,4),
          'issues_before':analysis['summary']['issue_count'],'issues_after':verification['issues']['after'],'proposal_count':analysis['summary']['proposal_count'],
          'gate_counts':analysis['summary'],'operations_applied':len(applied.json()['applied_operations']),
          'proposal_gate_details':[{'title':p['title'],'decision':p['gate']['decision'],'reasons':p['gate']['reasons'],'failed_invariants':[i['name'] for i in p['simulation']['invariants'] if i['status']=='fail']} for p in analysis['proposals']],
          'cell_changes':len(changes),'correct_cell_changes':len(correct_changes),'row_removals':len(removed),
          'cell_change_audit':change_audit,'actionable_case_status':repaired_case_status,
          'repair_precision':round(repair_precision,4),'actionable_manifest_cases':len(actionable),'actionable_cases_repaired':len(repaired),
          'repair_recall':round(repair_recall,4),'abstentions_or_unresolved':len(manifest['errors'])-len(repaired),
          'refused_proposal_ids':[p['id'] for p in refused],'refused_override_rejected':refused_override_status==409,
          'approval_decisions':[{'proposal_id':p['id'],'action':'approve'} for p in pending],
          'applied_operation_ids':[x['op_id'] for x in applied.json()['applied_operations']],
          'previously_valid_cells_changed':verification['valid_cells_damaged'],
          'invariant_failures_in_nonrefused_proposals':sum(1 for p in analysis['proposals'] if p['gate']['decision']!='refused' and any(i['status']=='fail' for i in p['simulation']['invariants'])),
          'replay_matches':verification['replay']['match'],'output_cells_different_from_truth':unequal,
          'original_upload_sha256':uploaded.json()['run']['file_sha256'],'stored_original_sha256':original_sha,
          'original_upload_preserved':uploaded.json()['run']['file_sha256']==original_sha and main.storage.get(rid)['original']==original_bytes,
          'exports_validated':{'cleaned_csv_rows':len(clean),'report_json_object':isinstance(json_exports['report'],dict),'modification_log_json_entries':len(json_exports['log']),'recipe_json_operations':len(json_exports['recipe']['operations'])},
          'runtime_seconds':round(time.perf_counter()-started,3),'peak_process_rss_mb':peak_rss_mb(),'llm_enabled':False,
          'note':'Precision/recall are measured only on this generated dataset. Detection truth is the manifest and listed preservation cases; repair recall denominator includes cases explicitly eligible for auto-apply or approval. No general accuracy claim.'
        }
        (ROOT/'benchmark_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
if __name__=='__main__': main_benchmark()
