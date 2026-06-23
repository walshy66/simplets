from fastapi.testclient import TestClient

from app import db
from app.connections import upsert_connection
from app.intake import get_invoice_drive_uploader
from app.main import app

HOST_A = {"host": "clienta.simplets.com.au"}
HOST_B = {"host": "clientb.simplets.com.au"}


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


def seed_workspaces():
    db.init_db()
    timestamp = "2026-01-01T00:00:00+00:00"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        for ws_id, subdomain in [("ws-a", "clienta"), ("ws-b", "clientb")]:
            conn.execute(
                "INSERT INTO workspaces (id, name, subdomain, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (ws_id, subdomain, subdomain, timestamp, timestamp),
            )
        conn.execute(
            "INSERT INTO workspace_users (id, workspace_id, user_id, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("membership-a", "ws-a", "alice-admin", "admin", timestamp, timestamp),
        )
        conn.commit()


def test_client_context_blocks_invoice_upload_until_drive_datastore_setup_exists(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        context = client.get("/workspaces/current/client-context", headers={"x-sts-user": "alice-admin", **HOST_A})
        upload = client.post(
            "/submissions",
            data={"submitter": "Client", "intent": "client_intake", "fields": '{"business_name":"Demo"}'},
            files={"file": ("invoice.pdf", b"synthetic invoice", "application/pdf")},
            headers=HOST_A,
        )

    assert context.status_code == 200
    assert context.json()["invoice_upload"]["available"] is False
    assert context.json()["invoice_upload"]["reason"] == "google_drive_datastore_setup_required"
    assert context.json()["drive_datastore"] is None
    assert upload.status_code == 409
    assert upload.json()["detail"] == "google_drive_datastore_setup_required"


def test_drive_datastore_setup_stores_pointer_metadata_only_and_is_workspace_scoped(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        configured = client.put(
            "/workspaces/current/client-context/drive-datastore",
            json={"drive_root_id": "root-a", "invoice_folder_id": "folder-a", "folder_path": "Clients/A/Invoices"},
            headers={"x-sts-user": "alice-admin", **HOST_A},
        )
        context_a = client.get("/workspaces/current/client-context", headers={"x-sts-user": "alice-admin", **HOST_A})
        context_b = client.get("/workspaces/current/client-context", headers={"x-sts-user": "platform-admin", **HOST_B})

    assert configured.status_code == 200
    assert configured.json()["drive_datastore"] == {
        "provider": "google_drive",
        "drive_root_id": "root-a",
        "invoice_folder_id": "folder-a",
        "folder_path": "Clients/A/Invoices",
    }
    assert "token" not in configured.text.lower()
    assert "secret" not in configured.text.lower()
    assert context_a.json()["invoice_upload"]["available"] is True
    assert context_b.json()["invoice_upload"]["available"] is False
    assert context_b.json()["drive_datastore"] is None


def test_invoice_upload_sends_file_to_configured_drive_folder_and_stores_only_pointer_metadata(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()
    db.init_db()
    captured: dict[str, object] = {}

    class RecordingDriveUploader:
        def upload_file(self, access_token, *, filename, content_type, contents, parent_folder_id):
            captured.update(
                {
                    "access_token": access_token,
                    "filename": filename,
                    "content_type": content_type,
                    "contents": contents,
                    "parent_folder_id": parent_folder_id,
                }
            )
            return {"id": "drive-file-123", "webViewLink": "https://drive.example/file/123"}

    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO workspace_drive_datastores (workspace_id, provider, drive_root_id, invoice_folder_id, folder_path, created_at, updated_at) VALUES (?, 'google_drive', ?, ?, ?, ?, ?)",
            ("ws-a", "root-a", "invoice-folder-a", "Clients/A/Invoices", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
        upsert_connection(conn, "ws-a", "google_drive", access_token="drive-token")

    app.dependency_overrides[get_invoice_drive_uploader] = lambda: RecordingDriveUploader()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/submissions",
                data={"submitter": "Client", "intent": "client_intake", "fields": '{"business_name":"Demo"}'},
                files={"file": ("ACME Invoice 123.pdf", b"synthetic invoice", "application/pdf")},
                headers=HOST_A,
            )
            review_queue = client.get("/workflow-runs/review-queue", headers={"x-sts-user": "alice-admin", **HOST_A})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert captured == {
        "access_token": "drive-token",
        "filename": "[redacted].pdf",
        "content_type": "application/pdf",
        "contents": b"synthetic invoice",
        "parent_folder_id": "invoice-folder-a",
    }
    document = response.json()["document"]
    assert document["filename"] == "[redacted].pdf"
    assert document["temporary_storage_path"] == "google_drive://drive-file-123"
    assert document["drive_file_id"] == "drive-file-123"
    assert document["drive_web_url"] == "https://drive.example/file/123"
    assert len(document["filename_hash"]) == 64
    assert document["filename_redacted"] == "[redacted].pdf"
    assert not (tmp_path / "data" / "uploads" / document["id"] / "ACME Invoice 123.pdf").exists()
    assert review_queue.status_code == 200
    assert review_queue.json()[0]["review_status"] == "pending"
