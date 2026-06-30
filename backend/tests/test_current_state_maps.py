"""COA-290: workspace-scoped current-state process maps."""

from fastapi.testclient import TestClient

from app import db
from app.main import app

HOST_A = {"host": "clienta.simplets.com.au", "x-sts-user": "alice-admin"}
HOST_A_REVIEWER = {"host": "clienta.simplets.com.au", "x-sts-user": "alice-reviewer"}
HOST_A_OPERATOR = {"host": "clienta.simplets.com.au", "x-sts-user": "alice-operator"}
HOST_A_SUBMITTER = {"host": "clienta.simplets.com.au", "x-sts-user": "client-submit-only"}
HOST_B = {"host": "clientb.simplets.com.au", "x-sts-user": "bob-admin"}


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


def seed_workspaces():
    db.init_db()
    timestamp = "2026-01-01T00:00:00+00:00"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        for workspace_id, name, subdomain in [
            ("ws-a", "Client A", "clienta"),
            ("ws-b", "Client B", "clientb"),
        ]:
            conn.execute(
                "INSERT INTO workspaces (id, name, subdomain, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (workspace_id, name, subdomain, timestamp, timestamp),
            )
        for workspace_id, user_id, role in [
            ("ws-a", "alice-admin", "admin"),
            ("ws-a", "alice-reviewer", "reviewer"),
            ("ws-a", "alice-operator", "operator"),
            ("ws-b", "bob-admin", "admin"),
        ]:
            conn.execute(
                "INSERT INTO workspace_users (id, workspace_id, user_id, role, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (f"m-{workspace_id}-{user_id}", workspace_id, user_id, role, timestamp, timestamp),
            )
        conn.commit()


def valid_payload():
    return {
        "title": "Client onboarding current state",
        "version_ref": "discovery-v1",
        "lanes": [{"id": "sales", "title": "Sales"}],
        "phases": [{"id": "intake", "title": "Intake"}],
        "nodes": [
            {
                "id": "receive-form",
                "lane_id": "sales",
                "phase_id": "intake",
                "title": "Receive form",
                "node_type": "task",
            }
        ],
        "connectors": [{"id": "flow-1", "source_node_id": "receive-form", "target_node_id": "receive-form", "label": "Yes"}],
        "comments": [
            {
                "id": "c1",
                "node_id": "receive-form",
                "body": "Verify owner",
                "author": "alice-admin",
                "created_at": "2026-01-01T00:00:00+00:00",
                "resolved": False,
            }
        ],
    }


def test_current_state_map_create_get_and_list_are_workspace_scoped(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A)
        assert created.status_code == 201, created.text
        map_id = created.json()["id"]

        own_get = client.get(f"/current-state-maps/{map_id}", headers=HOST_A)
        other_get = client.get(f"/current-state-maps/{map_id}", headers=HOST_B)
        own_list = client.get("/current-state-maps", headers=HOST_A)
        other_list = client.get("/current-state-maps", headers=HOST_B)

    assert own_get.status_code == 200
    assert own_get.json()["workspace_id"] == "ws-a"
    assert own_get.json()["phases"][0]["id"] == "intake"
    assert own_get.json()["connectors"][0]["label"] == "Yes"
    assert other_get.status_code == 404
    assert [item["id"] for item in own_list.json()] == [map_id]
    assert other_list.json() == []


def test_current_state_map_defaults_empty_shell_to_process_phase(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        response = client.post("/current-state-maps", json={"title": "Untitled process"}, headers=HOST_A)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["lanes"] == []
    assert body["phases"] == [{"id": "process", "title": "Process"}]
    assert body["nodes"] == []


def test_current_state_map_allows_subscriber_staff_view_but_blocks_submitters(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A)
        map_id = created.json()["id"]
        reviewer_get = client.get(f"/current-state-maps/{map_id}", headers=HOST_A_REVIEWER)
        reviewer_list = client.get("/current-state-maps", headers=HOST_A_REVIEWER)
        submitter_get = client.get(f"/current-state-maps/{map_id}", headers=HOST_A_SUBMITTER)
        submitter_list = client.get("/current-state-maps", headers=HOST_A_SUBMITTER)

    assert reviewer_get.status_code == 200
    assert [item["id"] for item in reviewer_list.json()] == [map_id]
    assert submitter_get.status_code == 403
    assert submitter_list.status_code == 403


def test_current_state_map_freeform_node_allows_position_without_lane_or_phase(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()
    payload = {
        "title": "Freeform map",
        "nodes": [{"id": "n1", "title": "Receive request", "node_type": "process", "position": {"x": 120, "y": 240}}],
    }

    with TestClient(app) as client:
        response = client.post("/current-state-maps", json=payload, headers=HOST_A)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["nodes"][0]["lane_id"] is None
    assert body["nodes"][0]["phase_id"] is None
    assert body["nodes"][0]["position"] == {"x": 120.0, "y": 240.0}


def test_current_state_map_node_rejects_unknown_lane_or_phase_when_provided(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()
    payload = valid_payload()
    payload["nodes"][0]["lane_id"] = "missing-lane"

    with TestClient(app) as client:
        response = client.post("/current-state-maps", json=payload, headers=HOST_A)

    assert response.status_code == 422
    assert "lane_id" in response.text


def test_current_state_map_staff_can_comment_edit_and_accept(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A).json()
        map_id = created["id"]
        comment = client.post(
            f"/current-state-maps/{map_id}/comments",
            json={"node_id": "receive-form", "body": "Please confirm handoff", "resolved": False},
            headers=HOST_A_REVIEWER,
        )
        staff_edit = client.put(
            f"/current-state-maps/{map_id}",
            json={**valid_payload(), "title": "Reviewer mutation"},
            headers=HOST_A_REVIEWER,
        )
        accepted = client.post(f"/current-state-maps/{map_id}/accept", headers=HOST_A_REVIEWER)

    assert comment.status_code == 201, comment.text
    body = comment.json()
    assert body["comments"][-1]["body"] == "Please confirm handoff"
    assert body["comments"][-1]["node_id"] == "receive-form"
    assert body["comments"][-1]["author"] == "alice-reviewer"
    assert body["comments"][-1]["created_at"]
    assert body["comments"][-1]["resolved"] is False
    assert staff_edit.status_code == 200
    assert staff_edit.json()["title"] == "Reviewer mutation"
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "approved"


def test_current_state_map_comment_requires_workspace_and_valid_node(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A).json()
        other_workspace = client.post(
            f"/current-state-maps/{created['id']}/comments",
            json={"node_id": "receive-form", "body": "Cross tenant"},
            headers=HOST_B,
        )
        invalid_node = client.post(
            f"/current-state-maps/{created['id']}/comments",
            json={"node_id": "missing", "body": "Bad node"},
            headers=HOST_A_REVIEWER,
        )

    assert other_workspace.status_code == 404
    assert invalid_node.status_code == 422
    assert "node_id" in invalid_node.text


def test_current_state_map_can_save_draft_and_list_version_history(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A).json()
        saved = client.put(
            f"/current-state-maps/{created['id']}",
            json={**valid_payload(), "title": "Updated map", "version_ref": "discovery-v2"},
            headers=HOST_A,
        )
        history = client.get(f"/current-state-maps/{created['id']}/versions", headers=HOST_A)
        other_history = client.get(f"/current-state-maps/{created['id']}/versions", headers=HOST_B)

    assert saved.status_code == 200, saved.text
    assert saved.json()["title"] == "Updated map"
    assert saved.json()["version_ref"] == "discovery-v2"
    assert saved.json()["status"] == "draft"
    assert history.status_code == 200
    assert [item["version_ref"] for item in history.json()] == ["discovery-v1", "discovery-v2"]
    assert other_history.status_code == 404


def test_current_state_map_approved_version_is_immutable_and_can_be_duplicated(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A).json()
        approved = client.post(f"/current-state-maps/{created['id']}/accept", headers=HOST_A)
        draft_from_approved = client.put(
            f"/current-state-maps/{created['id']}",
            json={**valid_payload(), "title": "Should not save"},
            headers=HOST_A,
        )
        duplicate = client.post(f"/current-state-maps/{created['id']}/duplicate", headers=HOST_A)

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert draft_from_approved.status_code == 200, draft_from_approved.text
    assert draft_from_approved.json()["status"] == "draft"
    assert draft_from_approved.json()["source_version_id"] == created["id"]
    assert duplicate.status_code == 409
    assert "active draft" in duplicate.text


def test_current_state_map_approval_archives_previous_approved_version(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A).json()
        approved = client.post(f"/current-state-maps/{created['id']}/accept", headers=HOST_A).json()
        draft = client.put(
            f"/current-state-maps/{approved['id']}",
            json={**valid_payload(), "title": "Updated approved map", "version_ref": "discovery-v2"},
            headers=HOST_A,
        ).json()
        promoted = client.post(f"/current-state-maps/{draft['id']}/accept", headers=HOST_A).json()
        old = client.get(f"/current-state-maps/{approved['id']}", headers=HOST_A).json()
        active_list = client.get("/current-state-maps", headers=HOST_A).json()
        history = client.get(f"/current-state-maps/{promoted['id']}/versions", headers=HOST_A).json()

    assert promoted["status"] == "approved"
    assert old["status"] == "archived"
    assert [item["id"] for item in active_list] == [promoted["id"]]
    assert {item["status"] for item in history} == {"archived", "approved"}


def test_current_state_map_approved_duplicate_is_workspace_scoped(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post("/current-state-maps", json=valid_payload(), headers=HOST_A).json()
        client.post(f"/current-state-maps/{created['id']}/lock", headers=HOST_A)
        duplicate = client.post(f"/current-state-maps/{created['id']}/duplicate", headers=HOST_B)

    assert duplicate.status_code == 404
