from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.extraction import ExtractionRequest, ExtractionResult, get_extraction_provider
from app.main import app


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


def test_document_upload_creates_temporary_file_metadata_and_workflow_run(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.post(
            "/documents/upload",
            data={"intent": "summarize", "uploader": "user-123"},
            files={"file": ("notes.txt", b"Important demo notes", "text/plain")},
        )

    assert response.status_code == 201
    payload = response.json()
    document = payload["document"]
    workflow_run = payload["workflow_run"]

    assert document["filename"] == "notes.txt"
    assert document["intent"] == "summarize"
    assert document["uploader"] == "user-123"
    assert document["deletion_status"] == "retained"
    assert document["is_permanent_archive"] is False
    assert datetime.fromisoformat(document["uploaded_at"]).tzinfo is not None
    assert datetime.fromisoformat(document["retention_expires_at"]) > datetime.fromisoformat(document["uploaded_at"])

    stored_path = Path(document["temporary_storage_path"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"Important demo notes"
    assert str(stored_path).startswith(str(tmp_path / "data" / "uploads"))

    assert workflow_run["document_id"] == document["id"]
    assert workflow_run["intent"] == "summarize"
    assert workflow_run["status"] == "created"
    assert datetime.fromisoformat(workflow_run["created_at"]).tzinfo is not None


def test_uploaded_document_extraction_uses_provider_intent_and_returns_editable_fields(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seen_requests: list[ExtractionRequest] = []

    class RecordingExtractionProvider:
        def extract(self, request: ExtractionRequest) -> ExtractionResult:
            seen_requests.append(request)
            return ExtractionResult(
                suggested_classification="demo_notes",
                fields={"summary": "Important demo notes", "action_items": ["Follow up"]},
            )

    app.dependency_overrides[get_extraction_provider] = lambda: RecordingExtractionProvider()
    try:
        with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
            upload = client.post(
                "/documents/upload",
                data={"intent": "extract_actions", "uploader": "user-123"},
                files={"file": ("notes.txt", b"Important demo notes", "text/plain")},
            )
            workflow_run_id = upload.json()["workflow_run"]["id"]

            response = client.post(f"/workflow-runs/{workflow_run_id}/extract")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == workflow_run_id
    assert payload["status"] == "completed"
    assert payload["extraction_status"] == "completed"
    assert payload["extraction_error"] is None
    assert payload["suggested_classification"] == "demo_notes"
    assert payload["extracted_fields"] == {"summary": "Important demo notes", "action_items": ["Follow up"]}
    assert seen_requests[0].intent == "extract_actions"
    assert seen_requests[0].content == b"Important demo notes"
    assert seen_requests[0].filename == "notes.txt"


def test_uploaded_document_can_be_deleted_when_loaded_by_mistake(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        upload = client.post(
            "/documents/upload",
            data={"intent": "summarize", "uploader": "user-123"},
            files={"file": ("wrong-notes.txt", b"Wrong document", "text/plain")},
        )
        payload = upload.json()
        workflow_run_id = payload["workflow_run"]["id"]
        stored_path = Path(payload["document"]["temporary_storage_path"])

        response = client.delete(f"/workflow-runs/{workflow_run_id}")
        deleted_review_run = client.get(f"/workflow-runs/{workflow_run_id}/review")

    assert response.status_code == 204
    assert not stored_path.exists()
    assert deleted_review_run.status_code == 404



def test_document_upload_requires_intent_uploader_and_file(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        missing_intent = client.post(
            "/documents/upload",
            data={"uploader": "user-123"},
            files={"file": ("notes.txt", b"Important demo notes", "text/plain")},
        )
        missing_uploader = client.post(
            "/documents/upload",
            data={"intent": "summarize"},
            files={"file": ("notes.txt", b"Important demo notes", "text/plain")},
        )
        missing_file = client.post(
            "/documents/upload",
            data={"intent": "summarize", "uploader": "user-123"},
        )

    assert missing_intent.status_code == 422
    assert missing_uploader.status_code == 422
    assert missing_file.status_code == 422
