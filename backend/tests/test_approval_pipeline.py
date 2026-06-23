"""COA-275/276/278: intake submissions, destination pushes, zero-retention deletion."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db, destinations
from app.connections import upsert_connection
from app.intake import get_invoice_drive_uploader
from app.main import app

HOST = {"host": "clienta.simplets.com.au"}
ADMIN = {"x-sts-user": "platform-admin", **HOST}


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


@pytest.fixture(autouse=True)
def clean_adapters():
    yield
    destinations.reset_adapters()


class FlakyAdapter:
    """Destination that fails until told to recover; counts every push."""

    def __init__(self, provider: str):
        self.provider = provider
        self.failing = True
        self.push_count = 0

    def push(self, access_token, fields, context):
        self.push_count += 1
        if self.failing:
            raise destinations.DestinationError(f"{self.provider} rejected the record: 500")
        return f"{self.provider}-record-{context['workflow_run_id']}"


class CountingMockAdapter(destinations.MockDestinationAdapter):
    def __init__(self):
        self.push_count = 0

    def push(self, access_token, fields, context):
        self.push_count += 1
        return super().push(access_token, fields, context)


def provision_workspace(client):
    response = client.post("/workspaces", json={"name": "Client A", "subdomain": "clienta"}, headers=ADMIN)
    assert response.status_code == 201, response.text
    return response.json()


def submit_intake(client, with_file=False):
    files = {"file": ("payslip.pdf", b"%PDF-1.4 payslip", "application/pdf")} if with_file else None
    response = client.post(
        "/submissions",
        data={
            "submitter": "end-client-jane",
            "intent": "client_intake",
            "fields": json.dumps({"full_name": "Jane Citizen", "email": "jane@example.com", "tfn": "123456782"}),
        },
        files=files,
        headers=HOST,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_form_submission_reaches_review_queue(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as client:
        provision_workspace(client)
        payload = submit_intake(client)
        queue = client.get("/workflow-runs/review-queue", headers=ADMIN)

    assert payload["workflow_run"]["extracted_fields"]["full_name"] == "Jane Citizen"
    run_ids = [item["id"] for item in queue.json()]
    assert payload["workflow_run"]["id"] in run_ids
    # The submitted payload is stored as the temporary source document.
    stored = Path(payload["document"]["temporary_storage_path"])
    assert stored.exists()
    assert payload["document"]["deletion_status"] == "retained"


def test_submission_with_file_stores_drive_pointer_metadata(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    class RecordingDriveUploader:
        def upload_file(self, access_token, *, filename, content_type, contents, parent_folder_id):
            return {"id": "drive-file-approval", "webViewLink": "https://drive.example/file/approval"}

    app.dependency_overrides[get_invoice_drive_uploader] = lambda: RecordingDriveUploader()
    try:
        with TestClient(app) as client:
            workspace = provision_workspace(client)
            with db.sqlite3.connect(db.DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO workspace_drive_datastores (workspace_id, provider, drive_root_id, invoice_folder_id, folder_path, created_at, updated_at) VALUES (?, 'google_drive', ?, ?, ?, ?, ?)",
                    (workspace["id"], "root-a", "invoice-folder-a", "Clients/A/Invoices", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
                )
                conn.commit()
                upsert_connection(conn, workspace["id"], "google_drive", access_token="drive-token")
            payload = submit_intake(client, with_file=True)
    finally:
        app.dependency_overrides.clear()

    assert payload["document"]["filename"] == "[redacted].pdf"
    assert payload["document"]["content_type"] == "application/pdf"
    assert payload["document"]["temporary_storage_path"] == "google_drive://drive-file-approval"
    assert payload["document"]["drive_file_id"] == "drive-file-approval"
    assert payload["document"]["filename_redacted"] == "[redacted].pdf"


def test_successful_approval_purges_everything_but_audit(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as client:
        provision_workspace(client)
        payload = submit_intake(client)
        run_id = payload["workflow_run"]["id"]
        stored = Path(payload["document"]["temporary_storage_path"])

        approved = client.post(
            f"/workflow-runs/{run_id}/review/approve",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=ADMIN,
        )

    assert approved.status_code == 200
    body = approved.json()
    assert body["all_succeeded"] is True
    run = body["workflow_run"]

    # COA-278: no uploaded file retrievable, no extracted field data retrievable.
    assert not stored.exists()
    assert run["extracted_fields"] is None

    # Minimal audit: approver, timestamp, destinations — zero field values.
    audit = run["audit_summary"]
    assert audit["approved_by"] == "rita-reviewer"
    assert audit["destinations"][0]["provider"] == "mock"
    audit_text = json.dumps(audit)
    for sensitive in ["Jane Citizen", "jane@example.com", "123456782"]:
        assert sensitive not in audit_text

    # Nothing sensitive left anywhere in the database.
    raw_db = (tmp_path / "data" / "simplets.sqlite3").read_bytes()
    assert b"123456782" not in raw_db


def test_failed_destination_retains_data_and_allows_retry(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    flaky = FlakyAdapter("hubspot")
    counting_mock = CountingMockAdapter()
    destinations.register_adapter(flaky)
    destinations.register_adapter(counting_mock)

    with TestClient(app) as client:
        workspace = provision_workspace(client)
        with db.sqlite3.connect(db.DB_PATH) as conn:
            conn.row_factory = db.sqlite3.Row
            upsert_connection(conn, workspace["id"], "hubspot", access_token="hubspot-token")

        payload = submit_intake(client)
        run_id = payload["workflow_run"]["id"]
        stored = Path(payload["document"]["temporary_storage_path"])

        first = client.post(
            f"/workflow-runs/{run_id}/review/approve",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=ADMIN,
        )

        assert first.status_code == 200
        assert first.json()["all_succeeded"] is False
        statuses = {push["provider"]: push for push in first.json()["destination_pushes"]}
        assert statuses["mock"]["status"] == "succeeded"
        assert statuses["hubspot"]["status"] == "failed"
        assert "rejected" in statuses["hubspot"]["error_message"]

        # Data retained while a destination is unresolved.
        assert stored.exists()
        assert first.json()["workflow_run"]["extracted_fields"] is not None
        assert first.json()["workflow_run"]["review_status"] == "pending"

        # Destination recovers; retry pushes only the failed provider.
        flaky.failing = False
        retry = client.post(
            f"/workflow-runs/{run_id}/review/retry-push",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=ADMIN,
        )

    assert retry.status_code == 200
    assert retry.json()["all_succeeded"] is True
    assert counting_mock.push_count == 1  # idempotent: mock not re-pushed on retry
    assert flaky.push_count == 2
    assert not stored.exists()
    assert retry.json()["workflow_run"]["review_status"] == "approved"


def test_failed_push_run_can_be_explicitly_discarded(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    flaky = FlakyAdapter("hubspot")
    destinations.register_adapter(flaky)

    with TestClient(app) as client:
        workspace = provision_workspace(client)
        with db.sqlite3.connect(db.DB_PATH) as conn:
            conn.row_factory = db.sqlite3.Row
            upsert_connection(conn, workspace["id"], "hubspot", access_token="hubspot-token")

        payload = submit_intake(client)
        run_id = payload["workflow_run"]["id"]
        stored = Path(payload["document"]["temporary_storage_path"])

        client.post(
            f"/workflow-runs/{run_id}/review/approve",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=ADMIN,
        )
        discarded = client.delete(f"/workflow-runs/{run_id}", headers=ADMIN)

    assert discarded.status_code == 204
    assert not stored.exists()


def test_approving_completed_run_conflicts(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as client:
        provision_workspace(client)
        run_id = submit_intake(client)["workflow_run"]["id"]
        client.post(
            f"/workflow-runs/{run_id}/review/approve",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=ADMIN,
        )
        again = client.post(
            f"/workflow-runs/{run_id}/review/approve",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=ADMIN,
        )

    assert again.status_code == 409


def test_invalid_submission_payloads_rejected(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as client:
        provision_workspace(client)
        bad_json = client.post(
            "/submissions",
            data={"submitter": "jane", "fields": "{not json"},
            headers=HOST,
        )
        empty_fields = client.post(
            "/submissions",
            data={"submitter": "jane", "fields": "{}"},
            headers=HOST,
        )

    assert bad_json.status_code == 422
    assert empty_fields.status_code == 422
