"""SQLite local persistence adapter: original bytes and parsed metadata are append-only."""
import json
import sqlite3
import urllib.error
import urllib.request
from contextlib import contextmanager
from urllib.parse import quote
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .config import settings

class ConcurrentWriteError(Exception):
    """The active working dataset changed after staging began."""

class RunStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.storage_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "runs.sqlite3"
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, row_count INTEGER NOT NULL, column_count INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, original BLOB NOT NULL, analysis TEXT, format_metadata TEXT NOT NULL DEFAULT '{\"format\":\"csv\"}')")
            if "format_metadata" not in {column[1] for column in db.execute("PRAGMA table_info(runs)").fetchall()}:
                db.execute("ALTER TABLE runs ADD COLUMN format_metadata TEXT NOT NULL DEFAULT '{\"format\":\"csv\"}'")
            db.execute("CREATE TABLE IF NOT EXISTS working_runs (run_id TEXT PRIMARY KEY REFERENCES runs(id), working_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS decisions (run_id TEXT NOT NULL, proposal_id TEXT NOT NULL, action TEXT NOT NULL, decided_at TEXT NOT NULL, PRIMARY KEY(run_id,proposal_id))")
            db.execute("CREATE TABLE IF NOT EXISTS operations (run_id TEXT NOT NULL, seq INTEGER NOT NULL, op_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, op TEXT NOT NULL, column_name TEXT, cells_changed INTEGER NOT NULL, rows_removed INTEGER NOT NULL, decided_by TEXT NOT NULL, applied_at TEXT NOT NULL, confidence REAL, active INTEGER NOT NULL, before_data TEXT NOT NULL, after_data TEXT NOT NULL, params TEXT NOT NULL, cell_log TEXT NOT NULL, UNIQUE(run_id,seq))")
            db.execute("CREATE TABLE IF NOT EXISTS artifacts (run_id TEXT NOT NULL, name TEXT NOT NULL, sha256 TEXT NOT NULL, content_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, object_path TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(run_id,name,sha256))")
            db.execute("CREATE TABLE IF NOT EXISTS verifications (run_id TEXT NOT NULL REFERENCES runs(id), verification_id TEXT PRIMARY KEY, verified_at TEXT NOT NULL, result TEXT NOT NULL)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, meta: dict[str, Any], original: bytes, working_json: str) -> None:
        created_at = meta["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        with self._connect() as db:
            db.execute("INSERT INTO runs (id,filename,sha256,size_bytes,row_count,column_count,status,created_at,original,analysis,format_metadata) VALUES (?,?,?,?,?,?,?,?,?,NULL,?)", (meta["id"], meta["filename"], meta["file_sha256"], meta["file_size_bytes"], meta["row_count"], meta["column_count"], "uploaded", created_at, original, json.dumps(meta.get("format_metadata", {"format":"csv"}))))
            db.execute("INSERT INTO working_runs VALUES (?, ?)", (meta["id"], working_json))

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row: return None
        result=dict(row)
        result["format_metadata"]=json.loads(result.get("format_metadata") or '{"format":"csv"}')
        return result

    def get_working(self, run_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT working_json FROM working_runs WHERE run_id=?", (run_id,)).fetchone()
        return row["working_json"] if row else None

    def mark_analyzed(self, run_id: str, analysis: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute("UPDATE runs SET status=CASE WHEN status='applied' THEN 'applied' ELSE 'analyzed' END, analysis=? WHERE id=?", (json.dumps(analysis), run_id))

    def get_analysis(self, run_id: str) -> dict[str, Any] | None:
        row=self.get(run_id)
        return json.loads(row["analysis"]) if row and row.get("analysis") else None

    def save_verification(self, run_id: str, result: dict[str, Any]) -> None:
        if self.get(run_id) is None: raise KeyError("unknown run")
        with self._connect() as db:
            db.execute("INSERT INTO verifications VALUES (?,?,?,?)", (run_id,"ver_"+__import__("uuid").uuid4().hex,datetime.now(timezone.utc).isoformat(),json.dumps(result)))

    def list_verifications(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows=db.execute("SELECT verification_id,verified_at,result FROM verifications WHERE run_id=? ORDER BY verified_at",(run_id,)).fetchall()
        return [{"verification_id":r["verification_id"],"verified_at":r["verified_at"],"result":json.loads(r["result"])} for r in rows]

    def get_decisions(self, run_id: str) -> dict[str, dict[str,str]]:
        with self._connect() as db:
            rows=db.execute("SELECT proposal_id,action,decided_at FROM decisions WHERE run_id=?",(run_id,)).fetchall()
        return {r["proposal_id"]:{"action":r["action"],"decided_at":r["decided_at"]} for r in rows}

    def save_decisions(self, run_id: str, decisions: list[dict[str,str]]) -> None:
        with self._connect() as db:
            for item in decisions:
                existing=db.execute("SELECT action FROM decisions WHERE run_id=? AND proposal_id=?",(run_id,item["proposal_id"])).fetchone()
                if existing and existing["action"]!=item["action"]:
                    raise ValueError("A proposal decision cannot be changed once recorded")
                db.execute("INSERT OR IGNORE INTO decisions VALUES (?,?,?,?)",(run_id,item["proposal_id"],item["action"],item["decided_at"]))

    def delete_decision(self, run_id: str, proposal_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM decisions WHERE run_id=? AND proposal_id=?",(run_id,proposal_id))

    def save_review(self, run_id: str, decisions: list[dict[str,str]], analysis: dict[str,Any]) -> None:
        with self._connect() as db:
            for item in decisions:
                existing=db.execute("SELECT action FROM decisions WHERE run_id=? AND proposal_id=?",(run_id,item["proposal_id"])).fetchone()
                if existing and existing["action"]!=item["action"]: raise ValueError("A proposal decision cannot be changed once recorded")
            for item in decisions:
                db.execute("INSERT OR IGNORE INTO decisions VALUES (?,?,?,?)",(run_id,item["proposal_id"],item["action"],item["decided_at"]))
            db.execute("UPDATE runs SET status=CASE WHEN status='applied' THEN 'applied' ELSE 'analyzed' END,analysis=? WHERE id=?",(json.dumps(analysis),run_id))

    def save_analysis_and_clear_decision(self, run_id: str, proposal_id: str, analysis: dict[str,Any]) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM decisions WHERE run_id=? AND proposal_id=?",(run_id,proposal_id))
            db.execute("UPDATE runs SET status=CASE WHEN status='applied' THEN 'applied' ELSE 'analyzed' END,analysis=? WHERE id=?",(json.dumps(analysis),run_id))

    def apply_batch(self, run_id: str, operation_rows: list[dict[str,Any]], final_working_json: str, expected_working_json: str) -> None:
        with self._connect() as db:
            current=db.execute("SELECT working_json FROM working_runs WHERE run_id=?",(run_id,)).fetchone()
            if current is None: raise KeyError("unknown run")
            if current["working_json"]!=expected_working_json: raise ConcurrentWriteError("The active dataset changed during apply staging")
            seqrow=db.execute("SELECT COALESCE(MAX(seq),0) AS seq FROM operations WHERE run_id=?",(run_id,)).fetchone()
            seq=seqrow["seq"]
            for item in operation_rows:
                seq+=1
                db.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                    run_id,seq,item["op_id"],item["proposal_id"],item["op"],item.get("column"),item["cells_changed"],
                    item["rows_removed"],item["decided_by"],item["applied_at"],item.get("confidence"),1,
                    item["before_data"],item["after_data"],json.dumps(item["params"]),json.dumps(item["cell_log"])))
            db.execute("UPDATE working_runs SET working_json=? WHERE run_id=?",(final_working_json,run_id))
            db.execute("UPDATE runs SET status='applied' WHERE id=?",(run_id,))

    def list_operations(self, run_id: str, active_only: bool=True) -> list[dict[str,Any]]:
        with self._connect() as db:
            query="SELECT * FROM operations WHERE run_id=?"+(" AND active=1" if active_only else "")+" ORDER BY seq"
            rows=db.execute(query,(run_id,)).fetchall()
        result=[]
        for r in rows:
            x=dict(r); x["active"]=bool(x["active"]); x["params"]=json.loads(x["params"]); x["cell_log"]=json.loads(x["cell_log"]); result.append(x)
        return result

    def undo_latest(self, run_id: str, op_id: str) -> bool:
        with self._connect() as db:
            latest=db.execute("SELECT * FROM operations WHERE run_id=? AND active=1 ORDER BY seq DESC LIMIT 1",(run_id,)).fetchone()
            if latest is None or latest["op_id"]!=op_id: return False
            db.execute("UPDATE working_runs SET working_json=? WHERE run_id=?",(latest["before_data"],run_id))
            db.execute("UPDATE operations SET active=0 WHERE op_id=?",(op_id,))
            remaining=db.execute("SELECT 1 FROM operations WHERE run_id=? AND active=1 LIMIT 1",(run_id,)).fetchone()
            db.execute("UPDATE runs SET status=? WHERE id=?",("applied" if remaining else "analyzed",run_id))
            return True

    def save_artifact(self, run_id: str, name: str, content: bytes, content_type: str) -> None:
        row = self.get(run_id)
        if row is None: raise KeyError("unknown run")
        digest = __import__("hashlib").sha256(content).hexdigest()
        object_path = Path("artifacts") / run_id / f"{name}-{digest}"
        target = self.root / object_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
        with self._connect() as db:
            db.execute("INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?,?,?,?)", (run_id,name,digest,content_type,len(content),object_path.as_posix(),datetime.now(timezone.utc).isoformat()))

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT name,sha256,content_type,size_bytes,object_path,created_at FROM artifacts WHERE run_id=? ORDER BY name,created_at", (run_id,)).fetchall()
        return [dict(r) for r in rows]

class SupabaseStorage:
    """Supabase Postgres + Storage adapter using the backend service-role key.

    The adapter deliberately uses the small PostgREST/Storage HTTP surface needed
    by DataFix, avoiding an SDK dependency in the deterministic Python backend.
    The SQL schema is documented in backend/docs/supabase_schema.sql.
    """
    def __init__(self, url: str, backend_key: str, bucket: str = "datafix", bearer_auth: bool = True) -> None:
        if not url or not backend_key:
            raise ValueError("Supabase URL and backend-only key are required")
        self.url = url.rstrip("/")
        self.key = backend_key
        self.bearer_auth = bearer_auth
        self.bucket = bucket

    def _request(self, path: str, method: str = "GET", body: bytes | None = None,
                 content_type: str = "application/json", prefer: str | None = None) -> bytes:
        headers = {"apikey": self.key, "Content-Type": content_type}
        # Legacy service_role JWTs are also bearer auth. New sb_secret keys are
        # API keys, not JWTs, and must only be sent through the apikey header.
        if self.bearer_auth:
            headers["Authorization"] = f"Bearer {self.key}"
        if content_type == "text/csv":
            headers["x-upsert"] = "false"
        if prefer:
            headers["Prefer"] = prefer
        request = urllib.request.Request(self.url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body=exc.read()
            try: code=json.loads(body.decode()).get("code")
            except (ValueError,AttributeError): code=None
            if code=="40001": raise ConcurrentWriteError("The active dataset changed during apply staging") from exc
            raise RuntimeError("Supabase storage request failed") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # Never expose request headers, response bodies, or credentials.
            raise RuntimeError("Supabase storage request failed") from exc

    def create(self, meta: dict[str, Any], original: bytes, working_json: str) -> None:
        run_id = meta["id"]
        suffix = ".xlsx" if meta.get("format_metadata", {}).get("format") == "xlsx" else ".csv"
        object_path = f"runs/{run_id}/original{suffix}"
        self._request(f"/storage/v1/object/{self.bucket}/{object_path}", "POST", original,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if suffix == ".xlsx" else "text/csv")
        row = {
            "id": run_id, "filename": meta["filename"], "sha256": meta["file_sha256"],
            "size_bytes": meta["file_size_bytes"], "row_count": meta["row_count"],
            "column_count": meta["column_count"], "status": "uploaded",
            "created_at": meta["created_at"].isoformat() if isinstance(meta["created_at"], datetime) else meta["created_at"],
            "original_path": object_path, "working_json": working_json, "analysis": None,
            "format_metadata": meta.get("format_metadata", {"format":"csv"}),
        }
        try:
            self._request("/rest/v1/datafix_runs", "POST", json.dumps(row).encode(),
                          "application/json", "return=minimal")
        except Exception:
            # Remove the uploaded object if metadata insertion fails.
            try:
                self._request(f"/storage/v1/object/{self.bucket}/{object_path}", "DELETE")
            except Exception:
                pass
            raise

    def get(self, run_id: str) -> dict[str, Any] | None:
        encoded=quote(run_id,safe="")
        rows = json.loads(self._request(f"/rest/v1/datafix_runs?id=eq.{encoded}&select=*").decode() or "[]")
        if not rows:
            return None
        row = rows[0]
        row.setdefault("format_metadata", {"format": "csv"})
        row["original"] = self._request(f"/storage/v1/object/{self.bucket}/{quote(row['original_path'],safe='/')}")
        return row

    def get_working(self, run_id: str) -> str | None:
        rows = json.loads(self._request(f"/rest/v1/datafix_runs?id=eq.{quote(run_id,safe='')}&select=working_json").decode() or "[]")
        return rows[0]["working_json"] if rows else None

    def mark_analyzed(self, run_id: str, analysis: dict[str, Any]) -> None:
        self._request("/rest/v1/rpc/datafix_mark_analyzed", "POST",
                      json.dumps({"p_run_id":run_id,"p_analysis":analysis}).encode(), "application/json")

    def get_analysis(self, run_id: str) -> dict[str, Any] | None:
        rows=json.loads(self._request(f"/rest/v1/datafix_runs?id=eq.{quote(run_id,safe='')}&select=analysis").decode() or "[]")
        return rows[0]["analysis"] if rows else None

    def save_verification(self, run_id: str, result: dict[str, Any]) -> None:
        payload={"run_id":run_id,"verification_id":"ver_"+__import__("uuid").uuid4().hex,"verified_at":datetime.now(timezone.utc).isoformat(),"result":result}
        self._request("/rest/v1/datafix_verifications","POST",json.dumps(payload).encode(),"application/json","return=minimal")

    def list_verifications(self, run_id: str) -> list[dict[str, Any]]:
        encoded=quote(run_id,safe="")
        return json.loads(self._request(f"/rest/v1/datafix_verifications?run_id=eq.{encoded}&select=verification_id,verified_at,result&order=verified_at.asc").decode() or "[]")

    def get_decisions(self, run_id: str) -> dict[str, dict[str,str]]:
        rows=json.loads(self._request(f"/rest/v1/datafix_decisions?run_id=eq.{quote(run_id,safe='')}&select=proposal_id,action,decided_at").decode() or "[]")
        return {r["proposal_id"]:{"action":r["action"],"decided_at":r["decided_at"]} for r in rows}

    def save_decisions(self, run_id: str, decisions: list[dict[str,str]]) -> None:
        payload=[{"run_id":run_id,**x} for x in decisions]
        self._request("/rest/v1/datafix_decisions?on_conflict=run_id,proposal_id","POST",json.dumps(payload).encode(),"application/json","resolution=ignore-duplicates,return=minimal")

    def delete_decision(self, run_id: str, proposal_id: str) -> None:
        self._request(f"/rest/v1/datafix_decisions?run_id=eq.{quote(run_id,safe='')}&proposal_id=eq.{quote(proposal_id,safe='')}","DELETE",prefer="return=minimal")

    def save_review(self, run_id: str, decisions: list[dict[str,str]], analysis: dict[str,Any]) -> None:
        self._request("/rest/v1/rpc/datafix_save_review","POST",json.dumps({"p_run_id":run_id,"p_decisions":decisions,"p_analysis":analysis}).encode(),"application/json")

    def save_analysis_and_clear_decision(self, run_id: str, proposal_id: str, analysis: dict[str,Any]) -> None:
        self._request("/rest/v1/rpc/datafix_save_analysis_and_clear_decision","POST",json.dumps({"p_run_id":run_id,"p_proposal_id":proposal_id,"p_analysis":analysis}).encode(),"application/json")

    def apply_batch(self, run_id: str, operation_rows: list[dict[str,Any]], final_working_json: str, expected_working_json: str) -> None:
        payload={"p_run_id":run_id,"p_operations":operation_rows,"p_working_json":final_working_json,"p_expected_working_json":expected_working_json}
        self._request("/rest/v1/rpc/datafix_apply_batch","POST",json.dumps(payload).encode(),"application/json")

    def list_operations(self, run_id: str, active_only: bool=True) -> list[dict[str,Any]]:
        query=f"/rest/v1/datafix_operations?run_id=eq.{quote(run_id,safe='')}&select=*"+("&active=eq.true" if active_only else "")+"&order=seq.asc"
        rows=json.loads(self._request(query).decode() or "[]")
        for x in rows:
            for name in ("params","cell_log"):
                if isinstance(x.get(name),str): x[name]=json.loads(x[name])
        return rows

    def undo_latest(self, run_id: str, op_id: str) -> bool:
        result=self._request("/rest/v1/rpc/datafix_undo_latest","POST",json.dumps({"p_run_id":run_id,"p_op_id":op_id}).encode(),"application/json")
        try: return bool(json.loads(result.decode()))
        except ValueError: return False

    def save_artifact(self, run_id: str, name: str, content: bytes, content_type: str) -> None:
        if self.get_working(run_id) is None: raise KeyError("unknown run")
        digest = __import__("hashlib").sha256(content).hexdigest()
        encoded_run = quote(run_id,safe="")
        query=f"/rest/v1/datafix_artifacts?run_id=eq.{encoded_run}&name=eq.{quote(name,safe='')}&sha256=eq.{digest}&select=sha256"
        existing=json.loads(self._request(query).decode() or "[]")
        if existing: return
        object_path=f"runs/{run_id}/artifacts/{name}-{digest}"
        storage_path=f"/storage/v1/object/{self.bucket}/{quote(object_path,safe='/')}"
        try:
            self._request(storage_path,"POST",content,content_type)
        except RuntimeError as upload_error:
            # A prior request may have uploaded the content-addressed object but
            # failed before its metadata insert. Reuse it only after verifying
            # the stored bytes match the path hash; never overwrite it.
            try:
                stored=self._request(storage_path,"GET")
            except RuntimeError:
                raise upload_error
            if __import__("hashlib").sha256(stored).hexdigest()!=digest:
                raise RuntimeError("Supabase artifact path contains different content") from upload_error
        metadata={"run_id":run_id,"name":name,"sha256":digest,"content_type":content_type,"size_bytes":len(content),"object_path":object_path,"created_at":datetime.now(timezone.utc).isoformat()}
        try:
            self._request("/rest/v1/datafix_artifacts","POST",json.dumps(metadata).encode(),"application/json","return=minimal")
        except Exception:
            # Keep the content addressed object; a retry can safely reuse it.
            raise

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        encoded=quote(run_id,safe="")
        return json.loads(self._request(f"/rest/v1/datafix_artifacts?run_id=eq.{encoded}&select=name,sha256,content_type,size_bytes,object_path,created_at&order=created_at.asc").decode() or "[]")


def build_storage(config=settings):
    backend = config.storage_backend
    if backend == "local":
        return RunStorage()
    if backend == "supabase":
        if not config.supabase_configured:
            raise RuntimeError("Supabase storage selected but backend credentials are incomplete")
        return SupabaseStorage(config.supabase_url, config.supabase_backend_key, config.supabase_storage_bucket,
                               bearer_auth=not bool(config.supabase_secret_key))
    raise RuntimeError("DATAFIX_STORAGE_BACKEND must be 'local' or 'supabase'")


storage = build_storage()
