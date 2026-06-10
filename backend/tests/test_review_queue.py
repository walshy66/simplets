import json
import csv
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.models import DocumentDeletionStatus, WorkflowRunStatus


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


def seed_review_run(tmp_path, deleted=False):
    db.init_db()
    upload_dir = tmp_path / "data" / "uploads" / "doc-1"
    upload_dir.mkdir(parents=True)
    source_path = upload_dir / "source.txt"
    source_path.write_text("Original source text")

    with db.sqlite3.connect(db.DB_PATH) as conn:
        timestamp = "2026-01-01T00:00:00+00:00"
        # Seed the dev workspace that "testserver" requests resolve to (subdomain "coachcw").
        conn.execute(
            "INSERT INTO workspaces (id, name, subdomain, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("workspace-dev", "coachcw", "coachcw", timestamp, timestamp),
        )
        conn.execute(
            """
            INSERT INTO documents (
                id, workspace_id, filename, content_type, size_bytes, intent, temporary_storage_path,
                retention_expires_at, deletion_status, uploaded_at, uploader, is_permanent_archive
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc-1",
                "workspace-dev",
                "source.txt",
                "text/plain",
                len("Original source text"),
                "extract_actions",
                str(source_path),
                "2026-01-08T00:00:00+00:00",
                DocumentDeletionStatus.DELETED.value if deleted else DocumentDeletionStatus.RETAINED.value,
                timestamp,
                "operator-1",
                0,
            ),
        )
        conn.execute(
            """
            INSERT INTO workflow_runs (
                id, workspace_id, document_id, intent, status, extraction_status, extraction_error,
                suggested_classification, extracted_fields, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-1",
                "workspace-dev",
                "doc-1",
                "extract_actions",
                WorkflowRunStatus.COMPLETED.value,
                WorkflowRunStatus.COMPLETED.value,
                None,
                "demo_notes",
                json.dumps({"summary": "Original", "count": 1}),
                timestamp,
                timestamp,
            ),
        )
        conn.commit()


def test_review_queue_lists_pending_extracted_runs(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_review_run(tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.get("/workflow-runs/review-queue")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == ["run-1"]
    assert payload[0]["document"]["filename"] == "source.txt"
    assert payload[0]["review_status"] == "pending"
    assert payload[0]["extracted_fields"] == {"summary": "Original", "count": 1}


def test_review_detail_includes_source_preview_while_retained(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_review_run(tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.get("/workflow-runs/run-1/review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["filename"] == "source.txt"
    assert payload["source_preview"]["available"] is True
    assert payload["source_preview"]["content"] == "Original source text"


def test_review_detail_marks_source_unavailable_after_deletion(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_review_run(tmp_path, deleted=True)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.get("/workflow-runs/run-1/review")

    assert response.status_code == 200
    assert response.json()["source_preview"] == {"available": False, "content": None, "reason": "document no longer retained"}


def test_review_fields_can_be_updated_and_approval_requires_screen_review(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_review_run(tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        update = client.patch(
            "/workflow-runs/run-1/review/fields",
            json={"reviewer": "reviewer-1", "extracted_fields": {"summary": "Edited", "count": 2}},
        )
        rejected = client.post("/workflow-runs/run-1/review/approve", json={"reviewer": "reviewer-1", "fields_reviewed": False})
        approved = client.post("/workflow-runs/run-1/review/approve", json={"reviewer": "reviewer-1", "fields_reviewed": True})
        queue = client.get("/workflow-runs/review-queue")

    assert update.status_code == 200
    assert update.json()["extracted_fields"] == {"summary": "Edited", "count": 2}
    assert update.json()["last_reviewed_by"] == "reviewer-1"
    assert rejected.status_code == 422
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["approved_by"] == "reviewer-1"
    assert queue.json() == []


def test_approved_run_exports_writeback_audits_and_purges_sensitive_source(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_review_run(tmp_path)
    source_path = tmp_path / "data" / "uploads" / "doc-1" / "source.txt"

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        json_export = client.get("/workflow-runs/run-1/export?format=json")
        csv_export = client.get("/workflow-runs/run-1/export?format=csv")
        approved = client.post("/workflow-runs/run-1/review/approve", json={"reviewer": "reviewer-1", "fields_reviewed": True})
        detail = client.get("/workflow-runs/run-1/review")

    assert json_export.status_code == 200
    assert json_export.json() == {"summary": "Original", "count": 1}
    assert csv_export.status_code == 200
    rows = list(csv.DictReader(StringIO(csv_export.text)))
    assert rows == [{"field": "summary", "value": "Original"}, {"field": "count", "value": "1"}]

    payload = approved.json()
    assert payload["status"] == "completed"
    assert payload["review_status"] == "approved"
    assert payload["destination_record_id"].startswith("mock-destination-")
    assert payload["extracted_fields"] is None
    assert payload["audit_summary"] == {
        "approved_by": "reviewer-1",
        "destination": "mock",
        "destination_record_id": payload["destination_record_id"],
        "export_formats": ["json", "csv"],
        "source_document_deleted": True,
    }
    assert source_path.exists() is False
    assert detail.json()["document"]["deletion_status"] == "deleted"
