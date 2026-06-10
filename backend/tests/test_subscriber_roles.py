"""COA-283: subscriber staff roles enforced at the API, not just hidden buttons."""

import json

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.models import DocumentDeletionStatus, WorkflowRunStatus, WorkspaceRole

HOST = {"host": "clienta.simplets.com.au"}


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


def as_user(user_id: str) -> dict[str, str]:
    return {"x-sts-user": user_id, **HOST}


def seed_workspace_with_staff(tmp_path) -> None:
    db.init_db()
    upload_dir = tmp_path / "data" / "uploads" / "doc-1"
    upload_dir.mkdir(parents=True)
    source_path = upload_dir / "source.txt"
    source_path.write_text("Original source text")

    timestamp = "2026-01-01T00:00:00+00:00"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO workspaces (id, name, subdomain, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("ws-a", "Client A", "clienta", timestamp, timestamp),
        )
        for index, (user_id, role) in enumerate(
            [("alice-admin", "admin"), ("rita-reviewer", "reviewer"), ("oscar-operator", "operator")]
        ):
            conn.execute(
                "INSERT INTO workspace_users (id, workspace_id, user_id, role, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (f"membership-{index}", "ws-a", user_id, role, timestamp, timestamp),
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
                "ws-a",
                "source.txt",
                "text/plain",
                20,
                "review",
                str(source_path),
                "2026-01-08T00:00:00+00:00",
                DocumentDeletionStatus.RETAINED.value,
                timestamp,
                "client-upload",
                0,
            ),
        )
        conn.execute(
            """
            INSERT INTO workflow_runs (
                id, workspace_id, document_id, intent, status, extraction_status,
                extracted_fields, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-1",
                "ws-a",
                "doc-1",
                "review",
                WorkflowRunStatus.COMPLETED.value,
                WorkflowRunStatus.COMPLETED.value,
                json.dumps({"summary": "hello"}),
                timestamp,
                timestamp,
            ),
        )
        conn.commit()


def test_unauthenticated_requests_get_401(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        queue = client.get("/workflow-runs/review-queue", headers=HOST)
        approve = client.post(
            "/workflow-runs/run-1/review/approve",
            json={"reviewer": "ghost", "fields_reviewed": True},
            headers=HOST,
        )

    assert queue.status_code == 401
    assert approve.status_code == 401


def test_operator_can_view_queue_but_cannot_approve_or_edit(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        queue = client.get("/workflow-runs/review-queue", headers=as_user("oscar-operator"))
        detail = client.get("/workflow-runs/run-1/review", headers=as_user("oscar-operator"))
        edit = client.patch(
            "/workflow-runs/run-1/review/fields",
            json={"reviewer": "oscar-operator", "extracted_fields": {"summary": "tampered"}},
            headers=as_user("oscar-operator"),
        )
        approve = client.post(
            "/workflow-runs/run-1/review/approve",
            json={"reviewer": "oscar-operator", "fields_reviewed": True},
            headers=as_user("oscar-operator"),
        )
        export = client.get("/workflow-runs/run-1/export", headers=as_user("oscar-operator"))

    assert queue.status_code == 200
    assert detail.status_code == 200
    assert edit.status_code == 403
    assert approve.status_code == 403
    assert export.status_code == 403


def test_reviewer_can_review_and_approve_but_not_manage_users(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        edit = client.patch(
            "/workflow-runs/run-1/review/fields",
            json={"reviewer": "rita-reviewer", "extracted_fields": {"summary": "verified"}},
            headers=as_user("rita-reviewer"),
        )
        manage_users = client.put(
            "/workspaces/current/users/new-user",
            json={"role": "operator"},
            headers=as_user("rita-reviewer"),
        )
        branding = client.patch(
            "/workspaces/current/branding",
            json={"primary_color": "#ff0000"},
            headers=as_user("rita-reviewer"),
        )
        approve = client.post(
            "/workflow-runs/run-1/review/approve",
            json={"reviewer": "rita-reviewer", "fields_reviewed": True},
            headers=as_user("rita-reviewer"),
        )

    assert edit.status_code == 200
    assert manage_users.status_code == 403
    assert branding.status_code == 403
    assert approve.status_code == 200


def test_admin_can_manage_workspace_users_and_branding(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        listed = client.get("/workspaces/current/users", headers=as_user("alice-admin"))
        added = client.put(
            "/workspaces/current/users/nina-new",
            json={"role": "reviewer"},
            headers=as_user("alice-admin"),
        )
        branding = client.patch(
            "/workspaces/current/branding",
            json={"primary_color": "#123456"},
            headers=as_user("alice-admin"),
        )
        removed = client.delete("/workspaces/current/users/nina-new", headers=as_user("alice-admin"))

    assert listed.status_code == 200
    assert {user["user_id"] for user in listed.json()} == {"alice-admin", "rita-reviewer", "oscar-operator"}
    assert added.status_code == 200
    assert added.json()["role"] == WorkspaceRole.REVIEWER.value
    assert branding.status_code == 200
    assert removed.status_code == 204


def test_role_change_takes_effect_immediately(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        before = client.post(
            "/workflow-runs/run-1/review/approve",
            json={"reviewer": "oscar-operator", "fields_reviewed": True},
            headers=as_user("oscar-operator"),
        )
        promote = client.put(
            "/workspaces/current/users/oscar-operator",
            json={"role": "reviewer"},
            headers=as_user("alice-admin"),
        )
        after = client.post(
            "/workflow-runs/run-1/review/approve",
            json={"reviewer": "oscar-operator", "fields_reviewed": True},
            headers=as_user("oscar-operator"),
        )

    assert before.status_code == 403
    assert promote.status_code == 200
    assert after.status_code == 200


def test_non_member_of_workspace_gets_403(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        response = client.get("/workflow-runs/review-queue", headers=as_user("stranger"))

    assert response.status_code == 403


def test_platform_admin_can_act_across_workspaces(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspace_with_staff(tmp_path)

    with TestClient(app) as client:
        queue = client.get("/workflow-runs/review-queue", headers=as_user("platform-admin"))
        workspaces = client.get("/workspaces", headers=as_user("platform-admin"))
        forbidden = client.get("/workspaces", headers=as_user("alice-admin"))

    assert queue.status_code == 200
    assert workspaces.status_code == 200
    assert forbidden.status_code == 403
