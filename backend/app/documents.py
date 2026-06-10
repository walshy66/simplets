import csv
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app import db
from app.db import get_connection
from app.extraction import ExtractionProvider, ExtractionService, get_extraction_provider
from app.models import DocumentDeletionStatus, ReviewStatus, WorkflowRunStatus
from app.schemas import (
    DocumentMetadata,
    DocumentUploadResult,
    ReviewApprovalRequest,
    ReviewFieldsUpdate,
    ReviewQueueItem,
    ReviewRunDetail,
    SourcePreview,
    Workspace,
    WorkflowRun,
)
from app.auth import WorkspaceActor, require_any_staff, require_reviewer
from app.tenancy import resolve_workspace

router = APIRouter(prefix="/documents", tags=["documents"])
workflow_router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])
RETENTION_DAYS = 7


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_filename(filename: str) -> str:
    candidate = Path(filename).name.strip()
    return candidate or "upload.bin"


def row_to_document(row: sqlite3.Row) -> DocumentMetadata:
    values = dict(row)
    values["is_permanent_archive"] = bool(values["is_permanent_archive"])
    return DocumentMetadata(**values)


def row_to_workflow_run(row: sqlite3.Row) -> WorkflowRun:
    return WorkflowRun(**dict(row))


def _row_to_review_queue_item(row: sqlite3.Row) -> ReviewQueueItem:
    values = dict(row)
    document = {
        "id": values["document_id"],
        "workspace_id": values.get("workspace_id"),
        "filename": values.pop("document_filename"),
        "content_type": values.pop("document_content_type"),
        "size_bytes": values.pop("document_size_bytes"),
        "intent": values.pop("document_intent"),
        "temporary_storage_path": values.pop("document_temporary_storage_path"),
        "retention_expires_at": values.pop("document_retention_expires_at"),
        "deletion_status": values.pop("document_deletion_status"),
        "uploaded_at": values.pop("document_uploaded_at"),
        "uploader": values.pop("document_uploader"),
        "is_permanent_archive": bool(values.pop("document_is_permanent_archive")),
    }
    return ReviewQueueItem(**values, document=DocumentMetadata(**document))


def _get_review_item(conn: sqlite3.Connection, workflow_run_id: str, workspace_id: str) -> ReviewQueueItem | None:
    row = conn.execute(
        """
        SELECT
            workflow_runs.*,
            documents.filename AS document_filename,
            documents.content_type AS document_content_type,
            documents.size_bytes AS document_size_bytes,
            documents.intent AS document_intent,
            documents.temporary_storage_path AS document_temporary_storage_path,
            documents.retention_expires_at AS document_retention_expires_at,
            documents.deletion_status AS document_deletion_status,
            documents.uploaded_at AS document_uploaded_at,
            documents.uploader AS document_uploader,
            documents.is_permanent_archive AS document_is_permanent_archive
        FROM workflow_runs
        JOIN documents ON documents.id = workflow_runs.document_id
        WHERE workflow_runs.id = ? AND workflow_runs.workspace_id = ?
        """,
        (workflow_run_id, workspace_id),
    ).fetchone()
    if row is None:
        return None
    return _row_to_review_queue_item(row)


def _source_preview(document: DocumentMetadata) -> SourcePreview:
    if document.deletion_status != DocumentDeletionStatus.RETAINED:
        return SourcePreview(available=False, reason="document no longer retained")
    source_path = Path(document.temporary_storage_path)
    if not source_path.exists():
        return SourcePreview(available=False, reason="source file missing")
    return SourcePreview(available=True, content=source_path.read_text(errors="replace"))


def _delete_source_document(document: DocumentMetadata) -> bool:
    source_path = Path(document.temporary_storage_path)
    if source_path.exists():
        source_path.unlink()
    return not source_path.exists()


def _mock_destination_record_id(workflow_run_id: str) -> str:
    return f"mock-destination-{workflow_run_id}"


@workflow_router.get("/review-queue", response_model=list[ReviewQueueItem])
def list_review_queue(
    conn: sqlite3.Connection = Depends(get_connection),
    actor: WorkspaceActor = Depends(require_any_staff),
) -> list[ReviewQueueItem]:
    workspace = actor.workspace
    rows = conn.execute(
        """
        SELECT
            workflow_runs.*,
            documents.filename AS document_filename,
            documents.content_type AS document_content_type,
            documents.size_bytes AS document_size_bytes,
            documents.intent AS document_intent,
            documents.temporary_storage_path AS document_temporary_storage_path,
            documents.retention_expires_at AS document_retention_expires_at,
            documents.deletion_status AS document_deletion_status,
            documents.uploaded_at AS document_uploaded_at,
            documents.uploader AS document_uploader,
            documents.is_permanent_archive AS document_is_permanent_archive
        FROM workflow_runs
        JOIN documents ON documents.id = workflow_runs.document_id
        WHERE workflow_runs.extraction_status = ? AND workflow_runs.review_status = ?
            AND workflow_runs.workspace_id = ?
        ORDER BY workflow_runs.updated_at DESC
        """,
        (WorkflowRunStatus.COMPLETED.value, ReviewStatus.PENDING.value, workspace.id),
    ).fetchall()
    return [_row_to_review_queue_item(row) for row in rows]


@workflow_router.get("/{workflow_run_id}/review", response_model=ReviewRunDetail)
def get_review_run(
    workflow_run_id: str,
    conn: sqlite3.Connection = Depends(get_connection),
    actor: WorkspaceActor = Depends(require_any_staff),
) -> ReviewRunDetail:
    review_item = _get_review_item(conn, workflow_run_id, actor.workspace.id)
    if review_item is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return ReviewRunDetail(**review_item.model_dump(), source_preview=_source_preview(review_item.document))


@workflow_router.patch("/{workflow_run_id}/review/fields", response_model=WorkflowRun)
def update_review_fields(
    workflow_run_id: str,
    update: ReviewFieldsUpdate,
    conn: sqlite3.Connection = Depends(get_connection),
    actor: WorkspaceActor = Depends(require_reviewer),
) -> WorkflowRun:
    if _get_review_item(conn, workflow_run_id, actor.workspace.id) is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    timestamp = now_iso()
    conn.execute(
        """
        UPDATE workflow_runs
        SET extracted_fields = ?, last_reviewed_by = ?, last_reviewed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (json.dumps(update.extracted_fields), update.reviewer, timestamp, timestamp, workflow_run_id),
    )
    conn.commit()
    workflow_run = conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()
    return row_to_workflow_run(workflow_run)


@workflow_router.get("/{workflow_run_id}/export", response_model=None)
def export_workflow_run(
    workflow_run_id: str,
    format: str = "json",
    conn: sqlite3.Connection = Depends(get_connection),
    actor: WorkspaceActor = Depends(require_reviewer),
):
    workflow_run = conn.execute(
        "SELECT * FROM workflow_runs WHERE id = ? AND workspace_id = ?", (workflow_run_id, actor.workspace.id)
    ).fetchone()
    if workflow_run is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    fields = row_to_workflow_run(workflow_run).extracted_fields
    if fields is None:
        raise HTTPException(status_code=410, detail="extracted fields have been purged")
    if format == "json":
        return fields
    if format == "csv":
        csv_buffer = StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=["field", "value"])
        writer.writeheader()
        for key, value in fields.items():
            writer.writerow({"field": key, "value": value})
        return Response(content=csv_buffer.getvalue(), media_type="text/csv")
    raise HTTPException(status_code=422, detail="format must be json or csv")


@workflow_router.post("/{workflow_run_id}/review/approve", response_model=WorkflowRun)
def approve_review_run(
    workflow_run_id: str,
    approval: ReviewApprovalRequest,
    conn: sqlite3.Connection = Depends(get_connection),
    actor: WorkspaceActor = Depends(require_reviewer),
) -> WorkflowRun:
    review_item = _get_review_item(conn, workflow_run_id, actor.workspace.id)
    if review_item is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    timestamp = now_iso()
    destination_record_id = _mock_destination_record_id(workflow_run_id)
    source_document_deleted = _delete_source_document(review_item.document)
    audit_summary = {
        "approved_by": approval.reviewer,
        "destination": "mock",
        "destination_record_id": destination_record_id,
        "export_formats": ["json", "csv"],
        "source_document_deleted": source_document_deleted,
    }
    conn.execute(
        """
        UPDATE documents
        SET deletion_status = ?
        WHERE id = ?
        """,
        (DocumentDeletionStatus.DELETED.value, review_item.document.id),
    )
    conn.execute(
        """
        UPDATE workflow_runs
        SET status = ?, review_status = ?, extracted_fields = ?, last_reviewed_by = ?, last_reviewed_at = ?,
            approved_by = ?, approved_at = ?, destination_record_id = ?, audit_summary = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            WorkflowRunStatus.COMPLETED.value,
            ReviewStatus.APPROVED.value,
            None,
            approval.reviewer,
            timestamp,
            approval.reviewer,
            timestamp,
            destination_record_id,
            json.dumps(audit_summary),
            timestamp,
            workflow_run_id,
        ),
    )
    conn.commit()
    workflow_run = conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()
    return row_to_workflow_run(workflow_run)


@workflow_router.delete("/{workflow_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow_run(
    workflow_run_id: str,
    conn: sqlite3.Connection = Depends(get_connection),
    actor: WorkspaceActor = Depends(require_reviewer),
) -> Response:
    review_item = _get_review_item(conn, workflow_run_id, actor.workspace.id)
    if review_item is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    if review_item.review_status == ReviewStatus.APPROVED:
        raise HTTPException(status_code=409, detail="approved workflow runs cannot be deleted")

    _delete_source_document(review_item.document)
    conn.execute("DELETE FROM workflow_runs WHERE id = ?", (workflow_run_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (review_item.document.id,))
    conn.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@workflow_router.post("/{workflow_run_id}/extract", response_model=WorkflowRun)
def extract_workflow_run(
    workflow_run_id: str,
    conn: sqlite3.Connection = Depends(get_connection),
    provider: ExtractionProvider = Depends(get_extraction_provider),
    workspace: Workspace = Depends(resolve_workspace),
) -> WorkflowRun:
    workflow_run = ExtractionService(conn, provider).run(workflow_run_id, workspace_id=workspace.id)
    if workflow_run is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return row_to_workflow_run(workflow_run)


@router.post("/upload", response_model=DocumentUploadResult, status_code=status.HTTP_201_CREATED)
def upload_document(
    intent: str = Form(min_length=1),
    uploader: str = Form(min_length=1),
    file: UploadFile = File(),
    conn: sqlite3.Connection = Depends(get_connection),
    workspace: Workspace = Depends(resolve_workspace),
) -> DocumentUploadResult:
    clean_intent = intent.strip()
    clean_uploader = uploader.strip()
    if not clean_intent:
        raise HTTPException(status_code=422, detail="intent is required")
    if not clean_uploader:
        raise HTTPException(status_code=422, detail="uploader is required")

    document_id = str(uuid4())
    workflow_run_id = str(uuid4())
    timestamp = now_iso()
    retention_expires_at = (datetime.now(UTC) + timedelta(days=RETENTION_DAYS)).isoformat()

    upload_dir = db.DATA_DIR / "uploads" / document_id
    upload_dir.mkdir(parents=True, exist_ok=False)
    storage_path = upload_dir / _safe_filename(file.filename or "upload.bin")

    contents = file.file.read()
    storage_path.write_bytes(contents)

    conn.execute(
        """
        INSERT INTO documents (
            id, workspace_id, filename, content_type, size_bytes, intent, temporary_storage_path,
            retention_expires_at, deletion_status, uploaded_at, uploader, is_permanent_archive
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            workspace.id,
            _safe_filename(file.filename or "upload.bin"),
            file.content_type,
            len(contents),
            clean_intent,
            str(storage_path),
            retention_expires_at,
            DocumentDeletionStatus.RETAINED.value,
            timestamp,
            clean_uploader,
            0,
        ),
    )
    conn.execute(
        """
        INSERT INTO workflow_runs (id, workspace_id, document_id, intent, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (workflow_run_id, workspace.id, document_id, clean_intent, WorkflowRunStatus.CREATED.value, timestamp, timestamp),
    )
    conn.commit()

    document = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    workflow_run = conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()
    return DocumentUploadResult(document=row_to_document(document), workflow_run=row_to_workflow_run(workflow_run))
