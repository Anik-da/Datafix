"""FastAPI application for DataFix's first deterministic analysis milestone."""
import logging, uuid, json, io
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi import Query
import hashlib
from fastapi.openapi.utils import get_openapi
from .config import settings
from .schemas import AnalysisResponse, AnalysisRunMetadata, CompatibilityProfileResponse, ErrorEnvelope, HealthResponse, LLMHealth, RunMetadata, RunStatus, UploadResponse, DecisionsRequest, DecisionsResponse, DecisionState, ApplyResponse, AppliedOperationResult, SkippedProposal, OperationHistoryResponse, AppliedOperation, VerificationResponse, VerificationIssues, ReplayResult, IssueCategoryCount, UndoRequest, UndoResponse, Operation, Proposal, Invariant, ProposalEditRequest, ProposalEditResponse, BulkDecisionRequest, BulkDecisionsResponse, BulkDecisionResult, ColumnUncertainty, RecordUncertainty, UncertaintyResponse, TrustPassport, DecisionAuditEntry, WorksheetListResponse
from .services import InputProblem, analyze_frame, create_run, parse_csv, profile, PLACEHOLDERS
from .ingestion import get_adapter, parse_dataset
from .ingestion.registry import list_worksheets
from .llm import explain_issue
from .lifecycle import execute, frame_hash, simulate, quality, csv_safe, invariant_results, AGGREGATE_DRIFT_LIMITS
from .storage import ConcurrentWriteError, storage
from .fingerprints import fingerprint_issue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="DataFix API", version="0.1.0", description="Deterministic CSV and XLSX profiling, issue analysis, repair proposals, approval decisions, repair application, verification, undo, and format-aware exports.")
COMMON_ERRORS = {400:{"model":ErrorEnvelope},422:{"model":ErrorEnvelope},500:{"model":ErrorEnvelope}}
UPLOAD_ERRORS = {**COMMON_ERRORS,413:{"model":ErrorEnvelope},415:{"model":ErrorEnvelope}}
RUN_ERRORS = {**COMMON_ERRORS,404:{"model":ErrorEnvelope},409:{"model":ErrorEnvelope}}
app.add_middleware(CORSMiddleware,allow_origins=list(settings.cors_origins),allow_credentials=False,allow_methods=["GET","POST","OPTIONS"],allow_headers=["Content-Type","X-Request-ID"])

@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logging.getLogger("datafix.http").info(json.dumps({"event":"request_complete","request_id":request.state.request_id,"method":request.method,"path":request.url.path,"status_code":response.status_code},separators=(",",":")))
    return response

def error_response(request: Request, status: int, code: str, message: str, details: dict | None = None):
    body=ErrorEnvelope(code=code,message=message,details=details or {},request_id=getattr(request.state,"request_id",str(uuid.uuid4())))
    return JSONResponse(status_code=status,content=body.model_dump(mode="json"))

@app.exception_handler(InputProblem)
async def input_problem_handler(request: Request, exc: InputProblem):
    return error_response(request,exc.status,exc.code,str(exc),exc.details)

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return error_response(request,422,"validation_error","Request validation failed.",{"errors":[str(e.get("loc",()))+": "+e.get("msg","invalid") for e in exc.errors()]})

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    status=exc.status_code
    return error_response(request,status,"not_found" if status==404 else "http_error",str(exc.detail) if status<500 else "The request could not be completed.")

@app.exception_handler(Exception)
async def unexpected_handler(request: Request, exc: Exception):
    logging.getLogger("datafix.api").exception("Unhandled request error request_id=%s",getattr(request.state,"request_id",None))
    return error_response(request,500,"internal_error","An unexpected server error occurred.")

@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok",api="available",llm=LLMHealth(enabled=settings.llm_enabled,available=settings.llm_available,model=settings.llm_model or None),limits={"max_upload_bytes":settings.max_upload_bytes,"max_rows":settings.max_rows,"max_columns":settings.max_columns,"max_cell_chars":settings.max_cell_chars})

async def bounded_read(file: UploadFile) -> bytes:
    content=bytearray()
    while True:
        chunk=await file.read(64*1024)
        if not chunk: break
        content.extend(chunk)
        if len(content)>settings.max_upload_bytes:
            raise InputProblem(413,"upload_too_large","Upload exceeds the configured size limit.",{"limit_bytes":settings.max_upload_bytes})
    return bytes(content)

@app.post("/api/v1/runs",response_model=UploadResponse,status_code=201,tags=["runs"],responses=UPLOAD_ERRORS)
async def upload_run(file: UploadFile = File(...,description=f"CSV or XLSX file, maximum {settings.max_upload_bytes} bytes"), worksheet: str | None = Form(None,description="Optional worksheet name for XLSX; defaults to the active worksheet.")) -> UploadResponse:
    raw=await bounded_read(file)
    filename=file.filename or "upload.csv"
    meta,frame=create_run(filename,raw,worksheet)
    working=frame.to_json(orient="split",force_ascii=False)
    storage.create(meta.model_dump(mode="json"),raw,working)
    logging.getLogger("datafix.api").info("Created run id=%s rows=%d columns=%d",meta.id,meta.row_count,meta.column_count)
    structural_count=int((frame.get("__datafix_actual_fields",pd.Series(dtype="int64")).astype(int)!=meta.column_count).sum()) if meta.format_metadata.get("format")=="csv" else 0
    warnings=[f"{structural_count} record(s) have a field count different from the header; all parseable values were preserved for analysis."] if structural_count else []
    return UploadResponse(run=meta,warnings=warnings)

@app.post("/api/v1/datasets/worksheets",response_model=WorksheetListResponse,status_code=200,tags=["datasets"],responses=UPLOAD_ERRORS)
async def workbook_worksheets(file: UploadFile = File(...,description="XLSX workbook to inspect before selecting a worksheet")) -> WorksheetListResponse:
    raw=await bounded_read(file)
    names,active=list_worksheets(file.filename or "upload.xlsx",raw)
    return WorksheetListResponse(worksheets=names,active_worksheet=active)

def _metadata(row: dict, status: str | None = None) -> RunMetadata:
    return RunMetadata(id=row["id"],filename=row["filename"],file_sha256=row["sha256"],file_size_bytes=row["size_bytes"],row_count=row["row_count"],column_count=row["column_count"],status=RunStatus(status or row["status"]),created_at=datetime.fromisoformat(row["created_at"]),engine_version=settings.engine_version,format_metadata=row.get("format_metadata") or {"format":"csv"})

def _original_frame(row: dict) -> pd.DataFrame:
    metadata=row.get("format_metadata") or {"format":"csv"}
    return parse_dataset(row["filename"],row["original"],metadata.get("selected_worksheet")).frame

@app.post("/api/v1/runs/{run_id}/analyze",response_model=AnalysisResponse,tags=["runs"],responses=RUN_ERRORS)
def analyze_run(run_id: str) -> AnalysisResponse:
    row=storage.get(run_id)
    if row is None: raise InputProblem(404,"unknown_run","No uploaded run exists with this id.")
    # Analysis is a persisted snapshot: return it for analyzed/applied runs so a
    # retry is idempotent and cannot re-run optional external explanations or
    # replace lifecycle state after review decisions and proposal revisions.
    if row["status"] in {"analyzed", "applied"} and row.get("analysis"):
        return AnalysisResponse.model_validate(json.loads(row["analysis"]))
    working=storage.get_working(run_id)
    if working is None: raise InputProblem(500,"working_data_unavailable","The stored parsed dataset is unavailable.")
    frame=pd.read_json(io.StringIO(working),orient="split",dtype="string")
    prof,issues,proposals=analyze_frame(run_id,frame,row["size_bytes"])
    issues=[issue.model_copy(update={"pattern":fingerprint_issue(issue,next((c.inferred_type for c in prof.columns if c.name==issue.column),"unknown"))}) for issue in issues]
    issues=[issue.model_copy(update={"description":explain_issue(issue,run_id)}) for issue in issues]
    # Rewriting row structure in XLSX can invalidate workbook formula references. Keep
    # duplicate findings visible but unresolved; value-only workbook repairs remain safe.
    format_metadata=row.get("format_metadata") or {"format":"csv"}
    if format_metadata.get("format")=="xlsx":
        proposals=[p for p in proposals if p.op!=Operation.drop_exact_dupes]
        formula_cells={(x["row_id"],x["column"]) for x in format_metadata.get("formula_cells",[])}
        safe_proposals=[]
        for proposal in proposals:
            try: _candidate,_changes,_removed,_audit=execute(frame,proposal)
            except Exception: safe_proposals.append(proposal); continue
            if not any((str(change.get("row_id")),str(change.get("column"))) in formula_cells for change in _changes):
                safe_proposals.append(proposal)
        proposals=safe_proposals
    updated=[]
    for proposal in proposals:
        simulation,gate=simulate(frame,proposal,issues,row["size_bytes"])
        updated.append(proposal.model_copy(update={"simulation":simulation,"gate":gate,"status":"refused" if gate.decision=="refused" else "pending"}))
    proposals=updated
    current_status="applied" if row["status"]=="applied" else "analyzed"
    uploaded_meta=_metadata(row,current_status)
    meta=AnalysisRunMetadata(id=uploaded_meta.id,filename=uploaded_meta.filename,row_count=uploaded_meta.row_count,column_count=uploaded_meta.column_count,file_sha256=uploaded_meta.file_sha256,status=uploaded_meta.status,engine_version=uploaded_meta.engine_version,format_metadata=uploaded_meta.format_metadata)
    response=AnalysisResponse(run=meta,profile=prof,issues=issues,proposals=proposals,summary={"issue_count":len(issues),"proposal_count":len(proposals),"auto_apply_count":sum(x.gate and x.gate.decision=="auto_apply" for x in proposals),"needs_approval_count":sum(x.gate and x.gate.decision=="needs_approval" for x in proposals),"refused_count":sum(x.gate and x.gate.decision=="refused" for x in proposals)})
    storage.mark_analyzed(run_id,response.model_dump(mode="json"))
    return response

def _require_run(run_id: str) -> dict:
    row=storage.get(run_id)
    if row is None: raise InputProblem(404,"unknown_run","No uploaded run exists with this id.")
    return row

def _stored_analysis(run_id: str) -> AnalysisResponse:
    data=storage.get_analysis(run_id)
    if not data: raise InputProblem(409,"analysis_required","Analyze the run before using repair lifecycle endpoints.")
    return AnalysisResponse.model_validate(data)

def _frame_json(frame: pd.DataFrame) -> str:
    return frame.to_json(orient="split",force_ascii=False)

def _working_frame(run_id: str) -> pd.DataFrame:
    payload=storage.get_working(run_id)
    if payload is None: raise InputProblem(500,"working_data_unavailable","The stored parsed dataset is unavailable.")
    return pd.read_json(io.StringIO(payload),orient="split",dtype="string")

def _persist_analysis(analysis: AnalysisResponse) -> None:
    storage.mark_analyzed(analysis.run.id,analysis.model_dump(mode="json"))

@app.post("/api/v1/runs/{run_id}/proposals/{proposal_id}/edit",response_model=ProposalEditResponse,tags=["runs"],responses=RUN_ERRORS)
def edit_proposal(run_id: str, proposal_id: str, request: ProposalEditRequest) -> ProposalEditResponse:
    _require_run(run_id); analysis=_stored_analysis(run_id)
    proposal=next((p for p in analysis.proposals if p.id==proposal_id),None)
    if proposal is None: raise InputProblem(404,"unknown_proposal","Proposal does not belong to this run.")
    if proposal.gate and proposal.gate.decision=="refused": raise InputProblem(409,"proposal_refused","A refused proposal cannot be edited to bypass the Safety Gate.")
    if proposal.status in {"applied","failed"}: raise InputProblem(409,"invalid_proposal_state","Applied or failed proposals cannot be edited.")
    prior=storage.get_decisions(run_id)
    if proposal_id in prior and prior[proposal_id]["action"]=="approve": raise InputProblem(409,"already_approved","An approved proposal cannot be edited.")
    frame=_working_frame(run_id)
    if request.column not in frame.columns or request.column!=proposal.column: raise InputProblem(422,"invalid_edit_column","Edit column must match the proposal column.")
    try: index=int(request.row_id.rsplit("_",1)[1])-1
    except (ValueError,IndexError): raise InputProblem(422,"invalid_row_reference","Use a stable row reference such as row_12.")
    if not 0<=index<len(frame): raise InputProblem(422,"invalid_row_reference","Row reference is outside the current dataset.")
    actual=str(frame.iloc[index][request.column])
    if actual!=request.original_value: raise InputProblem(409,"stale_original_value","The cell value changed since it was reviewed.")
    if request.row_id not in {rid for issue in analysis.issues if issue.id in proposal.issue_ids for rid in issue.affected_row_ids}:
        raise InputProblem(422,"unaffected_row","The selected row is not part of the issue this proposal addresses.")
    metadata=_require_run(run_id).get("format_metadata") or {}
    if metadata.get("format")=="xlsx" and {"row_id":request.row_id,"column":request.column} in metadata.get("formula_cells",[]):
        raise InputProblem(409,"formula_cell_protected","Formula cells cannot be manually overwritten; the workbook formula is preserved.")
    col_values=frame[request.column].fillna("").astype(str); inferred=next((c.inferred_type for c in analysis.profile.columns if c.name==request.column),"string")
    if inferred in {"integer","number","numeric"}:
        try: new_number=float(request.edited_value.replace(",","")); old_numbers=pd.to_numeric(col_values.str.replace(",","",regex=False),errors="coerce").dropna()
        except ValueError: raise InputProblem(422,"invalid_edit_type","Edited value must be numeric for this column.")
        if not old_numbers.empty and not old_numbers.min()<=new_number<=old_numbers.max(): raise InputProblem(422,"edit_out_of_range","Edited value is outside the observed numeric range.")
    elif inferred=="date":
        from .services import parse_date
        parsed,_=parse_date(request.edited_value)
        if parsed is None: raise InputProblem(422,"invalid_edit_type","Edited value must be a valid date.")
    elif inferred=="category":
        allowed=set(col_values)-{"",actual}
        if request.edited_value not in allowed: raise InputProblem(422,"invalid_category_value","Edited category must match a value already present in this column.")
    if len(request.edited_value)>max(1,int(col_values.str.len().max() or 1))*4: raise InputProblem(422,"edit_out_of_range","Edited text exceeds the column's observed length allowance.")
    old_status=proposal.status; version=proposal.version+1
    params={"op":"manual_edit","row_id":request.row_id,"expected_value":request.original_value,"value":request.edited_value,"reason":request.reason}
    edited=Proposal.model_validate({**proposal.model_dump(mode="python"),"op":Operation.manual_edit,"risk_class":"value_substitution","source":"human","title":f"Human-edited: {proposal.title}","explanation":f"User supplied a value for {request.row_id}; it was type/range checked and re-simulated. Reason: {request.reason}","params":params,"version":version,"status":"edited_pending_reapproval","gate":None,"simulation":None})
    simulation,gate=simulate(frame,edited,analysis.issues,_require_run(run_id)["size_bytes"])
    if gate.decision=="refused": edited=edited.model_copy(update={"status":"refused","gate":gate,"simulation":simulation})
    else:
        gate=gate.model_copy(update={"decision":"needs_approval","reasons":[*gate.reasons,"Manual edits always require explicit reapproval." ]})
        edited=edited.model_copy(update={"gate":gate,"simulation":simulation,"status":"edited_pending_reapproval"})
    event=DecisionAuditEntry(previous_state=old_status,new_state=edited.status,action="edit",timestamp=datetime.now(timezone.utc),proposal_version=version,reason=request.reason,original_value=request.original_value,edited_value=request.edited_value,prior_proposal=proposal.model_dump(mode="json"))
    suggested=None
    if proposal.op==Operation.map_values: suggested=proposal.params.mapping.get(request.original_value)
    elif proposal.op in {Operation.trim_text,Operation.normalize_date,Operation.cast_numeric}: suggested=proposal.params.row_values.get(request.row_id)
    event=event.model_copy(update={"suggested_value":suggested})
    edited=edited.model_copy(update={"decision_history":[*proposal.decision_history,event]})
    analysis.proposals=[edited if p.id==proposal_id else p for p in analysis.proposals]
    if proposal_id in prior and prior[proposal_id]["action"]=="reject": storage.save_analysis_and_clear_decision(run_id,proposal_id,analysis.model_dump(mode="json"))
    else: _persist_analysis(analysis)
    return ProposalEditResponse(proposal=edited,status=edited.status)

@app.post("/api/v1/runs/{run_id}/decisions",response_model=DecisionsResponse,tags=["runs"],responses=RUN_ERRORS)
def record_decisions(run_id: str, request: DecisionsRequest) -> DecisionsResponse:
    _require_run(run_id); analysis=_stored_analysis(run_id)
    by_id={p.id:p for p in analysis.proposals}; prior=storage.get_decisions(run_id); to_save=[]; states=[]
    for decision in request.decisions:
        proposal=by_id.get(decision.proposal_id)
        if proposal is None: raise InputProblem(404,"unknown_proposal","Proposal does not belong to this run.")
        if not proposal.gate or proposal.gate.decision!="needs_approval":
            raise InputProblem(409,"invalid_decision_state","Only proposals that need approval can be approved or rejected.")
        old=prior.get(decision.proposal_id)
        if old and old["action"]!=decision.action.value:
            raise InputProblem(409,"decision_already_recorded","A recorded proposal decision cannot be changed.")
        timestamp=old["decided_at"] if old else datetime.now(timezone.utc).isoformat()
        if not old: to_save.append({"proposal_id":decision.proposal_id,"action":decision.action.value,"decided_at":timestamp})
        new_state="approved" if decision.action.value=="approve" else "rejected"
        event=DecisionAuditEntry(previous_state=proposal.status,new_state=new_state,action=decision.action.value,timestamp=datetime.fromisoformat(timestamp),proposal_version=proposal.version)
        replacement=proposal.model_copy(update={"status":new_state,"decision_history":proposal.decision_history if old else [*proposal.decision_history,event]})
        analysis.proposals=[replacement if p.id==proposal.id else p for p in analysis.proposals]
        states.append(DecisionState(proposal_id=decision.proposal_id,action=decision.action,state=new_state,decided_at=datetime.fromisoformat(timestamp)))
    storage.save_review(run_id,to_save,analysis.model_dump(mode="json"))
    return DecisionsResponse(decisions=states)

@app.post("/api/v1/runs/{run_id}/bulk-decisions",response_model=BulkDecisionsResponse,tags=["runs"],responses=RUN_ERRORS)
def bulk_decisions(run_id: str, request: BulkDecisionRequest) -> BulkDecisionsResponse:
    _require_run(run_id); analysis=_stored_analysis(run_id); by_id={p.id:p for p in analysis.proposals}
    if len(set(request.proposal_ids))!=len(request.proposal_ids): raise InputProblem(422,"duplicate_proposal_ids","Bulk review requires distinct proposal IDs.")
    selected=[]
    for pid in request.proposal_ids:
        p=by_id.get(pid)
        if p is None: raise InputProblem(404,"unknown_proposal","Every proposal ID must belong to this run.")
        if not p.gate or p.gate.decision!="needs_approval": raise InputProblem(409,"invalid_decision_state","Bulk review accepts only eligible needs_approval proposals; refused proposals cannot be overridden.")
        selected.append(p)
    saved=[]; results=[]; now=datetime.now(timezone.utc)
    prior=storage.get_decisions(run_id)
    for proposal in selected:
        action=request.action; old=prior.get(proposal.id)
        if old and old["action"]!=action: raise InputProblem(409,"decision_already_recorded","A previous decision cannot be changed.")
        when=datetime.fromisoformat(old["decided_at"]) if old else now
        if not old: saved.append({"proposal_id":proposal.id,"action":action,"decided_at":when.isoformat()})
        state="approved" if action=="approve" else "rejected"
        event=DecisionAuditEntry(previous_state=proposal.status,new_state=state,action=action,timestamp=when,proposal_version=proposal.version)
        repl=proposal.model_copy(update={"status":state,"decision_history":proposal.decision_history if old else [*proposal.decision_history,event]})
        analysis.proposals=[repl if p.id==proposal.id else p for p in analysis.proposals]
        results.append(BulkDecisionResult(proposal_id=proposal.id,state=state))
    storage.save_review(run_id,saved,analysis.model_dump(mode="json"))
    return BulkDecisionsResponse(results=results)

@app.post("/api/v1/runs/{run_id}/apply",response_model=ApplyResponse,tags=["runs"],responses=RUN_ERRORS)
def apply_repairs(run_id: str) -> ApplyResponse:
    _require_run(run_id); analysis=_stored_analysis(run_id); initial_working=storage.get_working(run_id)
    if initial_working is None: raise InputProblem(500,"working_data_unavailable","The stored parsed dataset is unavailable.")
    original_frame=pd.read_json(io.StringIO(initial_working),orient="split",dtype="string")
    decisions=storage.get_decisions(run_id); staged=original_frame.copy(deep=True); operation_rows=[]; output=[]; skipped=[]; combined_changes=[]; combined_removed=0; now=datetime.now(timezone.utc).isoformat()
    priority={Operation.manual_edit:-1,Operation.map_values:0,Operation.normalize_date:1,Operation.set_null:2,Operation.trim_text:3,Operation.cast_numeric:4,Operation.drop_exact_dupes:9}
    for proposal in sorted(analysis.proposals,key=lambda x:(priority.get(x.op,8),x.id)):
        if proposal.status=="applied":
            skipped.append(SkippedProposal(proposal_id=proposal.id,reason="Proposal was already applied in this run.")); continue
        decision=decisions.get(proposal.id); automatic=proposal.gate and proposal.gate.decision=="auto_apply"
        approved=decision and decision["action"]=="approve"
        if not automatic and not approved:
            reason="Proposal was refused by a safety invariant." if proposal.gate and proposal.gate.decision=="refused" else ("Proposal was rejected." if decision and decision["action"]=="reject" else "Pending approval.")
            skipped.append(SkippedProposal(proposal_id=proposal.id,reason=reason)); continue
        before=_frame_json(staged)
        try: after,changes,removed,audit_log=execute(staged,proposal)
        except Exception:
            return ApplyResponse(status="aborted",applied_operations=[],skipped=skipped,blocking_invariants=[Invariant(name="operation_execution",status="fail",detail="A typed operation failed during atomic staging.")])
        if not changes and not removed:
            skipped.append(SkippedProposal(proposal_id=proposal.id,reason="No changes remained applicable after earlier operations.")); continue
        staged=after; combined_changes.extend(changes); combined_removed += removed
        op_id="op_"+uuid.uuid4().hex
        operation_rows.append({"op_id":op_id,"proposal_id":proposal.id,"op":proposal.op.value,"column":proposal.column,"cells_changed":len(changes),"rows_removed":removed,"decided_by":"auto" if automatic else "user","applied_at":now,"confidence":proposal.confidence.value,"before_data":before,"after_data":_frame_json(staged),"params":proposal.params.model_dump(mode="json"),"cell_log":audit_log})
        output.append(AppliedOperationResult(op_id=op_id,proposal_id=proposal.id,op=proposal.op,column=proposal.column,cells_changed=len(changes),rows_removed=removed,decided_by="auto" if automatic else "user",applied_at=datetime.fromisoformat(now)))
    if operation_rows:
        selected_ids={x["proposal_id"] for x in operation_rows}
        selected_risks=[p.risk_class for p in analysis.proposals if p.id in selected_ids]
        batch_risk=min(selected_risks,key=lambda risk:AGGREGATE_DRIFT_LIMITS[risk],default=None)
        combined_invariants,_,_=invariant_results(original_frame,staged,issues=analysis.issues,changes=combined_changes,removed=combined_removed,risk_class=batch_risk)
        blocking=[item for item in combined_invariants if item.status=="fail"]
        if blocking:
            return ApplyResponse(status="aborted",applied_operations=[],skipped=skipped,blocking_invariants=blocking)
        _,post_issues,_=analyze_frame(run_id,staged,_require_run(run_id)["size_bytes"])
        before_signatures={(i.category,i.title,i.column) for i in analysis.issues}
        new=[i for i in post_issues if (i.category,i.title,i.column) not in before_signatures]
        if new:
            return ApplyResponse(status="aborted",applied_operations=[],skipped=skipped,blocking_invariants=[Invariant(name="combined_plan_no_new_issues",status="fail",detail="Combined plan introduced issue signatures; no operation was saved.",observed=len(new),threshold=0,unit="issue signatures")])
        try: storage.apply_batch(run_id,operation_rows,_frame_json(staged),initial_working)
        except ConcurrentWriteError as exc: raise InputProblem(409,"concurrent_run_update","Run data changed while repairs were staged. Analyze and retry.") from exc
        operation_by_proposal={x["proposal_id"]:x for x in operation_rows}; revised=[]
        for proposal in analysis.proposals:
            operation=operation_by_proposal.get(proposal.id)
            if operation is None: revised.append(proposal); continue
            previous=proposal.status
            event=DecisionAuditEntry(previous_state=previous,new_state="applied",action="apply",timestamp=datetime.fromisoformat(now),proposal_version=proposal.version,operation_id=operation["op_id"],edited_value=(operation["cell_log"][0].get("after") if operation["cell_log"] and operation["cell_log"][0].get("action")=="cell_changed" else None))
            revised.append(proposal.model_copy(update={"status":"applied","decision_history":[*proposal.decision_history,event]}))
        analysis.proposals=revised; _persist_analysis(analysis)
    return ApplyResponse(status="applied",applied_operations=output,skipped=skipped,blocking_invariants=[])

@app.get("/api/v1/runs/{run_id}/operations",response_model=OperationHistoryResponse,tags=["runs"],responses=RUN_ERRORS)
def operation_history(run_id: str) -> OperationHistoryResponse:
    _require_run(run_id)
    items=[AppliedOperation(seq=x["seq"],op_id=x["op_id"],proposal_id=x["proposal_id"],op=x["op"],column=x["column_name"],cells_changed=x["cells_changed"],rows_removed=x["rows_removed"],decided_by=x["decided_by"],applied_at=datetime.fromisoformat(x["applied_at"]),confidence_at_decision=x["confidence"],active=x["active"]) for x in storage.list_operations(run_id,active_only=False)]
    return OperationHistoryResponse(operations=items)

@app.post("/api/v1/runs/{run_id}/verify",response_model=VerificationResponse,tags=["runs"],responses=RUN_ERRORS)
def verify_run(run_id: str) -> VerificationResponse:
    row=_require_run(run_id); analysis=_stored_analysis(run_id)
    original=_original_frame(row); replay=original.copy(deep=True)
    proposal_map={p.id:p for p in analysis.proposals}; operations=storage.list_operations(run_id,active_only=True)
    for operation in operations:
        proposal=proposal_map.get(operation["proposal_id"])
        if proposal is None: raise InputProblem(500,"replay_unavailable","An applied operation is missing its stored proposal.")
        replay,_,_,_=execute(replay,proposal)
    current=_working_frame(run_id); _,remaining,_=analyze_frame(run_id,current,row["size_bytes"]); _,before_issues,_=analyze_frame(run_id,original,row["size_bytes"])
    before_ids={(x.category,x.title,x.column) for x in before_issues}; after_ids={(x.category,x.title,x.column) for x in remaining}
    by_cat=[]
    counts={}
    for issue in remaining: counts[issue.category]=counts.get(issue.category,0)+1
    by_cat=[IssueCategoryCount(category=k,count=v) for k,v in sorted(counts.items(),key=lambda x:x[0].value)]
    damaged=sum(x.previously_valid_cells_changed for p in analysis.proposals for x in [p.simulation] if x is not None)
    response=VerificationResponse(replay=ReplayResult(operations=len(operations),input_hash=frame_hash(original),replay_hash=frame_hash(replay),match=frame_hash(replay)==frame_hash(current)),issues=VerificationIssues(before=len(before_ids),after=len(after_ids),resolved=len(before_ids-after_ids),introduced=len(after_ids-before_ids),by_category=by_cat),valid_cells_damaged=damaged,quality_dimensions={"before":quality(original,before_issues),"after":quality(current,remaining)},remaining=remaining)
    storage.save_verification(run_id,response.model_dump(mode="json"))
    return response

@app.post("/api/v1/runs/{run_id}/undo/{op_id}",response_model=UndoResponse,tags=["runs"],responses=RUN_ERRORS)
def undo_operation(run_id: str,op_id: str) -> UndoResponse:
    _require_run(run_id)
    operations=storage.list_operations(run_id,active_only=True)
    target=next((x for x in operations if x["op_id"]==op_id),None)
    if not storage.undo_latest(run_id,op_id): return UndoResponse(status="refused",op_id=op_id,reason="Only the most recent active operation can be undone.")
    if target:
        analysis_data=storage.get_analysis(run_id)
        if analysis_data:
            analysis=AnalysisResponse.model_validate(analysis_data); decisions=storage.get_decisions(run_id); revised=[]
            for proposal in analysis.proposals:
                if proposal.id!=target["proposal_id"]: revised.append(proposal); continue
                prior=proposal.status; decision=decisions.get(proposal.id)
                restored="approved" if decision and decision["action"]=="approve" else ("rejected" if decision and decision["action"]=="reject" else "pending")
                event=DecisionAuditEntry(previous_state=prior,new_state=restored,action="undo",timestamp=datetime.now(timezone.utc),proposal_version=proposal.version,operation_id=op_id)
                revised.append(proposal.model_copy(update={"status":restored,"decision_history":[*proposal.decision_history,event]}))
            analysis.proposals=revised; _persist_analysis(analysis)
    return UndoResponse(status="undone",op_id=op_id)

@app.get("/api/v1/runs/{run_id}/export/passport",tags=["runs"],responses={**RUN_ERRORS,200:{"model":TrustPassport,"description":"Verified Trust Passport JSON attachment"}})
def export_passport(run_id: str) -> Response:
    payload=_passport_payload(run_id); body=(json.dumps(payload,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    storage.save_artifact(run_id,"passport",body,"application/json")
    return Response(content=body,media_type="application/json",headers={"Content-Disposition":f'attachment; filename="datafix_{run_id}_passport.json"'})

@app.get("/api/v1/runs/{run_id}/export/{artifact}",tags=["runs"],responses=RUN_ERRORS)
def export_artifact(run_id: str,artifact: str) -> Response:
    body,mime=_artifact_content(run_id,artifact)
    storage.save_artifact(run_id,artifact,body,mime)
    format_name=(_require_run(run_id).get("format_metadata") or {}).get("format","csv")
    extension=("xlsx" if format_name=="xlsx" else "csv") if artifact=="cleaned" else "json"
    return Response(content=body,media_type=mime,headers={"Content-Disposition":f'attachment; filename="datafix_{run_id}_{artifact}.{extension}"'})

def _artifact_content(run_id: str,artifact: str) -> tuple[bytes,str]:
    row=_require_run(run_id); frame=_working_frame(run_id); ops=storage.list_operations(run_id,active_only=True)
    if artifact=="cleaned":
        frame=_clean_export_frame(frame)
        adapter=get_adapter(row["filename"])
        body=adapter.export_cleaned(row["original"],frame,row.get("format_metadata") or {"format":"csv"})
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if (row.get("format_metadata") or {}).get("format")=="xlsx" else "text/csv"
    elif artifact in {"report","log","recipe"}:
        if artifact=="report": payload={"format":"application/json","run_id":run_id,"file_sha256":row["sha256"],"analysis":storage.get_analysis(run_id),"operations":[{k:v for k,v in x.items() if k not in {"before_data","after_data","cell_log","params"}} for x in ops]}
        elif artifact=="log": payload=[{**entry,"op_id":op["op_id"],"proposal_id":op["proposal_id"],"decided_by":op["decided_by"],"applied_at":op["applied_at"]} for op in ops for entry in op["cell_log"]]
        else: payload={"input_sha256":row["sha256"],"operations":[{"seq":x["seq"],"op_id":x["op_id"],"proposal_id":x["proposal_id"],"op":x["op"],"column":x["column_name"],"params":x["params"]} for x in ops]}
        body=(json.dumps(payload,indent=2,ensure_ascii=False)+"\n").encode("utf-8"); mime="application/json"
    elif artifact=="passport":
        payload=_passport_payload(run_id); body=(json.dumps(payload,indent=2,ensure_ascii=False)+"\n").encode("utf-8"); mime="application/json"
    else: raise InputProblem(404,"unknown_artifact","Supported artifacts are cleaned, report, log, recipe and passport.")
    return body,mime

def _clean_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Hide ingestion bookkeeping while keeping unresolved overflow values exportable."""
    visible=frame.loc[:,[c for c in frame.columns if not str(c).startswith("__datafix_")]].copy()
    for column in frame.columns:
        if not str(column).startswith("__datafix_extra_"):
            continue
        values=frame[column].fillna("").astype(str)
        if not values.str.strip().ne("").any():
            continue
        suffix=str(column).rsplit("_",1)[1]
        name=f"__unexpected_extra_{suffix}"
        while name in visible.columns:
            name="_"+name
        visible[name]=values
    return visible

@app.get("/api/v1/runs/{run_id}/uncertainty",response_model=UncertaintyResponse,tags=["runs"],responses=RUN_ERRORS)
def uncertainty_heatmap(run_id: str, offset: int=Query(0,ge=0), limit: int=Query(100,ge=1,le=500)) -> UncertaintyResponse:
    _require_run(run_id); analysis=_stored_analysis(run_id); frame=_working_frame(run_id); n=len(frame)
    visible_columns=[c for c in frame.columns if not str(c).startswith("__datafix_")]
    _,current_issues,_=analyze_frame(run_id,frame,_require_run(run_id)["size_bytes"])
    decisions=storage.get_decisions(run_id); issues_by_col={str(c):[] for c in visible_columns}; row_issues={}
    for issue in current_issues:
        cols=[issue.column] if issue.column in issues_by_col else list(issues_by_col) if issue.column is None else []
        for col in cols: issues_by_col[col].append(issue)
        for rid in issue.affected_row_ids: row_issues.setdefault(rid,[]).append(issue)
    proposals_by_col={str(c):[] for c in visible_columns}
    for proposal in analysis.proposals:
        if proposal.column in proposals_by_col: proposals_by_col[proposal.column].append(proposal)
    columns=[]
    for col in map(str,visible_columns):
        relevant=issues_by_col[col]; categories={x.category.value for x in relevant}
        invalid=len({rid for x in relevant if x.category.value=="invalid_format" for rid in x.affected_row_ids}); inconsistent=len({rid for x in relevant if x.category.value in {"inconsistent","relationship"} for rid in x.affected_row_ids}); anomalies=len({rid for x in relevant if x.category.value=="anomaly" for rid in x.affected_row_ids})
        series=frame[col].fillna("").astype(str); missing=int(series.map(lambda value:not value.strip() or value.strip().casefold() in PLACEHOLDERS).sum())
        proposals=proposals_by_col[col]; pending=sum(1 for p in proposals if p.status in {"pending","edited_pending_reapproval"}); refused=sum(1 for p in proposals if p.status=="refused" or (p.gate and p.gate.decision=="refused"))
        columns.append(ColumnUncertainty(column=col,total_records=n,missing_count=missing,missing_rate=missing/max(1,n),invalid_count=min(n,invalid),invalid_rate=min(n,invalid)/max(1,n),inconsistent_count=min(n,inconsistent),inconsistent_rate=min(n,inconsistent)/max(1,n),anomaly_count=min(n,anomalies),pending_proposals=pending,refused_proposals=refused,unresolved_issues=len(relevant),evidence_available=all(bool(x.evidence) for x in relevant) if relevant else True,confidence_available=any(p.confidence.value is not None for p in proposals),rule_coverage=sorted(categories)))
    try: verified= _require_run(run_id)["status"]=="applied" and verify_run(run_id).replay.match
    except Exception: verified=False
    records=[]
    for idx in range(offset,min(n,offset+limit)):
        rid=f"row_{idx+1}"; row_issues_here=row_issues.get(rid,[]); related=[p for p in analysis.proposals if any(iid in {x.id for x in row_issues_here} for iid in p.issue_ids)]
        if row_issues_here and any(p.status=="refused" or (p.gate and p.gate.decision=="refused") for p in related): state="refused_repair"
        elif row_issues_here and any(p.status=="edited_pending_reapproval" or (p.gate and p.gate.decision=="needs_approval" and p.id not in decisions) for p in related): state="pending_human_review"
        elif row_issues_here and not related: state="issue_detected"
        elif row_issues_here: state="unresolved"
        elif verified: state="verified_by_checks"
        elif row_issues_here: state="issue_detected"
        else: state="not_evaluated"
        records.append(RecordUncertainty(row_id=rid,state=state,issue_density=len(row_issues_here),columns=sorted({x.column for x in row_issues_here if x.column}),reasons=[x.title for x in row_issues_here[:8]],evidence_references=[x.id for x in row_issues_here[:8]],confidence=None))
    return UncertaintyResponse(run_id=run_id,offset=offset,limit=limit,total_records=n,columns=columns,records=records,calculation_notes=["Rates are measured counts divided by row count; overlapping issues can be counted in separate categories.","Record confidence is null because record-level correctness probability is not estimated.","verified_by_checks means the applied run replayed and the record has no remaining detector findings; it is not a universal correctness claim.","Rule coverage lists detector categories observed for the column, not complete domain validation."])

def _passport_payload(run_id: str) -> dict:
    row=_require_run(run_id); analysis=_stored_analysis(run_id); frame=_working_frame(run_id); operations=storage.list_operations(run_id,active_only=False); active=[x for x in operations if x["active"]]
    clean_export=_clean_export_frame(frame)
    cleaned=_artifact_content(run_id,"cleaned")[0]
    original=_original_frame(row); _,initial_issues,_=analyze_frame(run_id,original,row["size_bytes"]); _,remaining,_=analyze_frame(run_id,frame,row["size_bytes"])
    current_verification=verify_run(run_id) if analysis and row["status"]=="applied" else None
    category_counts={}
    for issue in initial_issues: category_counts[issue.category]=category_counts.get(issue.category,0)+1
    decisions=storage.get_decisions(run_id)
    issue_cells={(rid,str(issue.column)) for issue in initial_issues if issue.column for rid in issue.affected_row_ids}
    changed_valid={(entry.get("row_id"),entry.get("column")) for op in active for entry in op["cell_log"] if entry.get("action")=="cell_changed" and (entry.get("row_id"),entry.get("column")) not in issue_cells}
    all_events=[event for proposal in analysis.proposals for event in proposal.decision_history]
    operation_models=[AppliedOperation(seq=x["seq"],op_id=x["op_id"],proposal_id=x["proposal_id"],op=x["op"],column=x["column_name"],cells_changed=x["cells_changed"],rows_removed=x["rows_removed"],decided_by=x["decided_by"],applied_at=datetime.fromisoformat(x["applied_at"]),confidence_at_decision=x["confidence"],active=x["active"]) for x in operations]
    created=datetime.fromisoformat(row["created_at"]); times=[datetime.fromisoformat(x["applied_at"]) for x in operations]
    generated=max([created,*times]).astimezone(timezone.utc)
    artifact_hashes={name:hashlib.sha256(_artifact_content(run_id,name)[0]).hexdigest() for name in ("cleaned","report","log","recipe")}
    proposal_decisions=[{"proposal_id":p.id,"proposal_version":p.version,"status":p.status,"gate_decision":p.gate.decision if p.gate else None,"decision_history":[event.model_dump(mode="json") for event in p.decision_history]} for p in analysis.proposals]
    original_column_count=sum(not str(c).startswith("__datafix_") for c in original.columns)
    output_column_count=len(clean_export.columns)
    payload={"passport_version":"1.0","run_id":run_id,"original_filename":row["filename"],"original_sha256":hashlib.sha256(row["original"]).hexdigest(),"cleaned_sha256":hashlib.sha256(cleaned).hexdigest(),"passport_sha256":"","exported_artifact_sha256":artifact_hashes,"original_size_bytes":row["size_bytes"],"original_row_count":len(original),"original_column_count":original_column_count,"output_row_count":len(frame),"output_column_count":output_column_count,"engine_version":settings.engine_version,"generated_at":generated,"initial_issue_count":len(initial_issues),"initial_issue_categories":[{"category":k,"count":v} for k,v in sorted(category_counts.items(),key=lambda x:x[0].value)],"final_unresolved_issues":remaining,"previously_valid_cells_changed":len(changed_valid),"quality_before":quality(original,initial_issues),"quality_after":quality(frame,remaining),"proposal_count":len(analysis.proposals),"auto_apply_decisions":sum(x["decided_by"]=="auto" for x in active),"user_approvals":sum(x.action=="approve" for x in all_events),"rejections":sum(x.action=="reject" for x in all_events),"edited_proposals":sum(p.version>1 for p in analysis.proposals),"refused_repairs":sum(p.status=="refused" for p in analysis.proposals),"applied_operations":operation_models,"modification_log_reference":f"/api/v1/runs/{run_id}/export/log","simulation_summary":[p.simulation for p in analysis.proposals if p.simulation],"gate_outcomes":{p.id:p.gate.decision for p in analysis.proposals if p.gate},"proposal_decisions":proposal_decisions,"verification_status":"verified" if current_verification and current_verification.replay.match else "replay_mismatch" if current_verification else "not_run","replay_hash":current_verification.replay.replay_hash if current_verification else None,"replay_matches":current_verification.replay.match if current_verification else None,"benchmark_version":None,"limitations":["Passport is an integrity summary, not a guarantee of universal correctness.","Dataset checks are limited to implemented deterministic rules.","No cryptographic signature is applied.","exported_artifact_sha256 covers cleaned, report, log, and recipe exports; passport_sha256 covers the canonical passport payload."],"unresolved_count":len(remaining),"abstained_repairs":sum(p.status=="refused" for p in analysis.proposals),"llm_enabled":settings.llm_enabled}
    passport_proposals=[]
    for proposal in analysis.proposals:
        params=proposal.params
        summary: dict[str,str|int|float|None]={"operation":proposal.op.value,"values":"redacted"}
        if hasattr(params,"row_values"): summary["target_row_count"]=len(params.row_values)
        if hasattr(params,"row_ids"): summary["target_row_count"]=len(params.row_ids)
        if hasattr(params,"mapping"): summary["mapping_count"]=len(params.mapping)
        if hasattr(params,"duplicate_row_groups"):
            summary["duplicate_group_count"]=len(params.duplicate_row_groups)
            summary["duplicate_row_count"]=sum(max(0,len(group)-1) for group in params.duplicate_row_groups)
        if hasattr(params,"row_id"): summary["target_row_count"]=1
        passport_proposals.append({"proposal_id":proposal.id,"proposal_version":proposal.version,"operation":proposal.op,"column":proposal.column,"risk_class":proposal.risk_class,"title":proposal.title,"explanation":proposal.explanation,"parameter_summary":summary,"confidence":proposal.confidence,"simulation":proposal.simulation,"gate_decision":proposal.gate.decision if proposal.gate else None,"status":proposal.status})
    source_profile=profile(original,row["size_bytes"])
    payload.update({"passport_id":"pass_"+hashlib.sha256(f"{run_id}|{row['sha256']}".encode()).hexdigest()[:16],"original_column_schema":[{"name":col.name,"inferred_type":col.inferred_type} for col in source_profile.columns],"proposals":passport_proposals})
    payload["passport_sha256"]=""
    normalized=TrustPassport.model_validate(payload).model_dump(mode="json")
    canonical=json.dumps({k:v for k,v in normalized.items() if k!="passport_sha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    normalized["passport_sha256"]=hashlib.sha256(canonical).hexdigest()
    return normalized

@app.post("/api/v1/datasets/profile",response_model=CompatibilityProfileResponse,tags=["compatibility"],responses=UPLOAD_ERRORS)
async def compatibility_profile(file: UploadFile = File(...,description=f"CSV or XLSX file, maximum {settings.max_upload_bytes} bytes"), worksheet: str | None = Form(None)) -> CompatibilityProfileResponse:
    raw=await bounded_read(file)
    frame=parse_dataset(file.filename or "upload.csv",raw,worksheet).frame
    profile,_,_=analyze_frame("compat",frame,len(raw))
    return CompatibilityProfileResponse(profile=profile)

def generate_openapi(path: Path | None = None) -> Path:
    target=path or Path(__file__).resolve().parents[2]/"docs"/"openapi.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(app.openapi(),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return target

def _openapi_with_binary_uploads() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema=get_openapi(title=app.title,version=app.version,description=app.description,routes=app.routes)
    for model in schema.get("components",{}).get("schemas",{}).values():
        file_schema=model.get("properties",{}).get("file") if isinstance(model,dict) else None
        if file_schema and file_schema.get("type")=="string":
            file_schema["format"]="binary"
            file_schema.pop("contentMediaType",None)
    app.openapi_schema=schema
    return schema

app.openapi=_openapi_with_binary_uploads

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app",host="127.0.0.1",port=8000,reload=False)
