from __future__ import annotations
import ctypes, json, os, sys, tempfile, time
from ctypes import wintypes
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'backend'))
os.environ['LLM_ENABLED']='false'
from app.main import app
from app import main
from app.config import settings
from app.storage import RunStorage

def peak_rss_mb():
    if os.name!='nt':
        import resource
        value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(value/(1024*1024 if sys.platform=='darwin' else 1024),2)
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    psapi=ctypes.WinDLL('psapi');kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    return round(counters.PeakWorkingSetSize/(1024*1024),2) if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb) else None

def main_benchmark():
    rows=settings.max_rows; columns=min(settings.max_columns,40)
    with tempfile.TemporaryDirectory(prefix='datafix-cap-benchmark-') as temp:
        csv_path=Path(temp)/'max-shape.csv'
        with csv_path.open('w',encoding='utf-8',newline='') as stream:
            import csv
            writer=csv.writer(stream,lineterminator='\n')
            writer.writerow(['record_id']+[f'c{i}' for i in range(1,columns)])
            for i in range(rows): writer.writerow([f'R{i:05d}']+['1']*(columns-1))
        raw=csv_path.read_bytes()
        if len(raw)>settings.max_upload_bytes: raise SystemExit(f'generated input {len(raw)} exceeds configured byte limit')
        main.storage=RunStorage(Path(temp)/'store');client=TestClient(app);start=time.perf_counter()
        uploaded=client.post('/api/v1/runs',files={'file':('max-shape.csv',raw,'text/csv')})
        if uploaded.status_code!=201: raise SystemExit(f'upload failed {uploaded.status_code}: {uploaded.text}')
        rid=uploaded.json()['run']['id']; analyzed=client.post(f'/api/v1/runs/{rid}/analyze')
        if analyzed.status_code!=200: raise SystemExit(f'analyze failed {analyzed.status_code}: {analyzed.text}')
        wide_header=['record_id']+[f'c{i}' for i in range(1,settings.max_columns)]
        wide_body=(','.join(wide_header)+'\n'+','.join(['R0']+['1']*(settings.max_columns-1))+'\n').encode()
        wide=client.post('/api/v1/runs',files={'file':('wide.csv',wide_body,'text/csv')})
        if wide.status_code!=201 or wide.json()['run']['column_count']!=settings.max_columns: raise SystemExit(f'column limit check failed {wide.status_code}: {wide.text}')
        result={'row_limit_case':{'rows':uploaded.json()['run']['row_count'],'columns':uploaded.json()['run']['column_count'],'csv_size_bytes':len(raw),'upload_status':uploaded.status_code,'analysis_status':analyzed.status_code,'issue_count':analyzed.json()['summary']['issue_count'],'proposal_count':analyzed.json()['summary']['proposal_count']},'column_limit_case':{'rows':wide.json()['run']['row_count'],'columns':wide.json()['run']['column_count'],'csv_size_bytes':len(wide_body),'upload_status':wide.status_code},'upload_limit_bytes':settings.max_upload_bytes,'row_limit':settings.max_rows,'column_limit':settings.max_columns,'runtime_seconds':round(time.perf_counter()-start,3),'peak_process_rss_mb':peak_rss_mb(),'llm_enabled':False,'note':'Peak working set includes Python, pandas, TestClient and generated-input handling; Windows local measurement, not Render service memory. Maximum row and column dimensions are validated separately because 50,000 rows x 60 populated columns exceeds the 5 MiB upload cap.'}
        (ROOT/'benchmark_limits_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
if __name__=='__main__':main_benchmark()
