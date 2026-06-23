"""End-client form intake (COA-275 backend).

A submission is the golden-path intake unit: structured form fields plus an
optional supporting document. The submitted payload is written to temporary
storage as the source artifact so the zero-retention purge path (COA-278)
covers form data and uploads identically.
"""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app import db
from app.db import get_connection
from app.connections import ConnectorDisconnected, get_valid_access_token
from app.connectors import GoogleDriveAdapter, make_refresher
from app.destinations import DestinationError
from app.documents import RETENTION_DAYS, _safe_filename, row_to_document, row_to_workflow_run
from app.extraction import ExtractionProvider, ExtractionRequest, get_extraction_provider
from app.models import DocumentDeletionStatus, WorkflowRunStatus
from app.schemas import DocumentUploadResult, ExtractionPreview, Workspace
from app.tenancy import resolve_workspace

DRIVE_DATASTORE_REQUIRED = "google_drive_datastore_setup_required"


def has_drive_datastore(conn: sqlite3.Connection, workspace_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM workspace_drive_datastores WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()
    return row is not None


def _drive_datastore(conn: sqlite3.Connection, workspace_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT invoice_folder_id FROM workspace_drive_datastores WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()


def _redacted_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"[redacted]{suffix}" if suffix else "[redacted]"


def get_invoice_drive_uploader() -> GoogleDriveAdapter:
    return GoogleDriveAdapter()


router = APIRouter(prefix="/submissions", tags=["submissions"])


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@router.post("/extract-preview", response_model=ExtractionPreview)
def extract_preview(
    intent: str = Form(default="client_intake"),
    file: UploadFile = File(),
    provider: ExtractionProvider = Depends(get_extraction_provider),
    conn: sqlite3.Connection = Depends(get_connection),
    workspace: Workspace = Depends(resolve_workspace),
) -> ExtractionPreview:
    """Run extraction on an uploaded file without storing anything.

    Used by the intake form to populate fields while the end-client is still
    editing. Nothing is written to disk or the database; the file only becomes
    a stored submission when the form is submitted.
    """
    if not has_drive_datastore(conn, workspace.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DRIVE_DATASTORE_REQUIRED)
    contents = file.file.read()
    try:
        result = provider.extract(
            ExtractionRequest(
                document_id="preview",
                filename=_safe_filename(file.filename or "upload.bin"),
                content_type=file.content_type,
                intent=intent.strip() or "client_intake",
                content=contents,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"extraction failed: {exc}")
    return ExtractionPreview(
        fields=result.fields,
        suggested_classification=result.suggested_classification,
    )


@router.post("", response_model=DocumentUploadResult, status_code=status.HTTP_201_CREATED)
def create_submission(
    submitter: str = Form(min_length=1),
    intent: str = Form(default="client_intake"),
    fields: str = Form(min_length=2),
    file: UploadFile | None = File(default=None),
    conn: sqlite3.Connection = Depends(get_connection),
    workspace: Workspace = Depends(resolve_workspace),
    drive_uploader: GoogleDriveAdapter = Depends(get_invoice_drive_uploader),
) -> DocumentUploadResult:
    clean_submitter = submitter.strip()
    if not clean_submitter:
        raise HTTPException(status_code=422, detail="submitter is required")
    try:
        parsed_fields = json.loads(fields)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="fields must be valid JSON")
    if not isinstance(parsed_fields, dict) or not parsed_fields:
        raise HTTPException(status_code=422, detail="fields must be a non-empty JSON object")
    datastore = _drive_datastore(conn, workspace.id)
    if file is not None and file.filename and datastore is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DRIVE_DATASTORE_REQUIRED)

    document_id = str(uuid4())
    workflow_run_id = str(uuid4())
    timestamp = now_iso()
    retention_expires_at = (datetime.now(UTC) + timedelta(days=RETENTION_DAYS)).isoformat()

    upload_dir = db.DATA_DIR / "uploads" / document_id
    upload_dir.mkdir(parents=True, exist_ok=False)

    drive_file_id = None
    drive_web_url = None
    filename_hash = None
    filename_redacted = None
    if file is not None and file.filename:
        original_filename = _safe_filename(file.filename)
        filename = _redacted_filename(original_filename)
        contents = file.file.read()
        content_type = file.content_type
        filename_hash = hashlib.sha256(original_filename.encode("utf-8")).hexdigest()
        filename_redacted = filename
        try:
            access_token = get_valid_access_token(conn, workspace.id, "google_drive", refresher=make_refresher("google_drive"))
            drive_result = drive_uploader.upload_file(
                access_token,
                filename=filename,
                content_type=content_type,
                contents=contents,
                parent_folder_id=datastore["invoice_folder_id"],
            )
        except (ConnectorDisconnected, DestinationError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        drive_file_id = drive_result["id"]
        drive_web_url = drive_result.get("webViewLink")
        storage_path = f"google_drive://{drive_file_id}"
    else:
        filename = "client-intake-submission.json"
        contents = json.dumps({"submitter": clean_submitter, "fields": parsed_fields}).encode()
        content_type = "application/json"
        storage_path = upload_dir / filename
        storage_path.write_bytes(contents)

    conn.execute(
        """
        INSERT INTO documents (
            id, workspace_id, filename, content_type, size_bytes, intent, temporary_storage_path,
            retention_expires_at, deletion_status, uploaded_at, uploader, is_permanent_archive,
            drive_file_id, drive_web_url, filename_hash, filename_redacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            workspace.id,
            filename,
            content_type,
            len(contents),
            intent.strip() or "client_intake",
            str(storage_path),
            retention_expires_at,
            DocumentDeletionStatus.RETAINED.value,
            timestamp,
            clean_submitter,
            0,
            drive_file_id,
            drive_web_url,
            filename_hash,
            filename_redacted,
        ),
    )
    # Form submissions arrive already structured: they enter the review queue
    # directly with extraction marked complete.
    conn.execute(
        """
        INSERT INTO workflow_runs (
            id, workspace_id, document_id, intent, status, extraction_status,
            extracted_fields, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workflow_run_id,
            workspace.id,
            document_id,
            intent.strip() or "client_intake",
            WorkflowRunStatus.COMPLETED.value,
            WorkflowRunStatus.COMPLETED.value,
            json.dumps(parsed_fields),
            timestamp,
            timestamp,
        ),
    )
    conn.commit()

    document = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    workflow_run = conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()
    return DocumentUploadResult(document=row_to_document(document), workflow_run=row_to_workflow_run(workflow_run))
