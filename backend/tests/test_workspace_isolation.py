"""Constitution IV: workspace isolation and subdomain routing (COA-280)."""

from fastapi.testclient import TestClient

from app import db
from app.main import app


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")


def provision(client: TestClient, name: str, subdomain: str) -> dict:
    response = client.post("/workspaces", json={"name": name, "subdomain": subdomain})
    assert response.status_code == 201, response.text
    return response.json()


def upload(client: TestClient, host: str) -> dict:
    response = client.post(
        "/documents/upload",
        data={"intent": "review", "uploader": "user-a"},
        files={"file": ("intake.txt", b"Client intake details", "text/plain")},
        headers={"host": host},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_subdomain_host_routes_to_matching_workspace(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        workspace = provision(client, "Client A", "clienta")
        response = client.get("/workspaces/current", headers={"host": "clienta.simplets.com.au"})

    assert response.status_code == 200
    assert response.json()["id"] == workspace["id"]
    assert response.json()["subdomain"] == "clienta"


def test_unknown_subdomain_host_is_rejected(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.get("/workspaces/current", headers={"host": "ghost.simplets.com.au"})

    assert response.status_code == 404


def test_unrelated_host_is_rejected(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.get("/workspaces/current", headers={"host": "evil.example.com"})

    assert response.status_code == 404


def test_duplicate_subdomain_conflicts(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        provision(client, "Client A", "clienta")
        response = client.post("/workspaces", json={"name": "Imposter", "subdomain": "clienta"})

    assert response.status_code == 409


def test_invalid_and_reserved_subdomains_rejected(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        invalid = client.post("/workspaces", json={"name": "Bad", "subdomain": "Bad_Sub!"})
        reserved = client.post("/workspaces", json={"name": "Www", "subdomain": "www"})

    assert invalid.status_code == 422
    assert reserved.status_code == 422


def test_workflow_runs_are_invisible_across_workspaces(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        provision(client, "Client A", "clienta")
        provision(client, "Client B", "clientb")

        run_id = upload(client, "clienta.simplets.com.au")["workflow_run"]["id"]
        extract = client.post(f"/workflow-runs/{run_id}/extract", headers={"host": "clienta.simplets.com.au"})
        assert extract.status_code == 200

        queue_a = client.get("/workflow-runs/review-queue", headers={"host": "clienta.simplets.com.au"})
        queue_b = client.get("/workflow-runs/review-queue", headers={"host": "clientb.simplets.com.au"})

        detail_b = client.get(f"/workflow-runs/{run_id}/review", headers={"host": "clientb.simplets.com.au"})
        export_b = client.get(f"/workflow-runs/{run_id}/export", headers={"host": "clientb.simplets.com.au"})
        extract_b = client.post(f"/workflow-runs/{run_id}/extract", headers={"host": "clientb.simplets.com.au"})
        fields_b = client.patch(
            f"/workflow-runs/{run_id}/review/fields",
            json={"reviewer": "intruder", "extracted_fields": {"hijacked": True}},
            headers={"host": "clientb.simplets.com.au"},
        )
        approve_b = client.post(
            f"/workflow-runs/{run_id}/review/approve",
            json={"reviewer": "intruder", "fields_reviewed": True},
            headers={"host": "clientb.simplets.com.au"},
        )
        delete_b = client.delete(f"/workflow-runs/{run_id}", headers={"host": "clientb.simplets.com.au"})

    assert [item["id"] for item in queue_a.json()] == [run_id]
    assert queue_b.json() == []
    assert detail_b.status_code == 404
    assert export_b.status_code == 404
    assert extract_b.status_code == 404
    assert fields_b.status_code == 404
    assert approve_b.status_code == 404
    assert delete_b.status_code == 404


def test_upload_is_stamped_with_resolved_workspace(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        workspace = provision(client, "Client A", "clienta")
        payload = upload(client, "clienta.simplets.com.au")

    assert payload["document"]["workspace_id"] == workspace["id"]
    assert payload["workflow_run"]["workspace_id"] == workspace["id"]


def test_dev_host_falls_back_to_default_workspace(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        response = client.get("/workspaces/current")

    assert response.status_code == 200
    assert response.json()["subdomain"] == "coachcw"


def test_branding_is_configurable_per_workspace(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    with TestClient(app, headers={"x-sts-user": "platform-admin"}) as client:
        provision(client, "Client A", "clienta")
        provision(client, "Client B", "clientb")
        patched = client.patch(
            "/workspaces/current/branding",
            json={"logo_url": "https://cdn.clienta.example/logo.png", "primary_color": "#0a5cff"},
            headers={"host": "clienta.simplets.com.au"},
        )
        untouched = client.get("/workspaces/current", headers={"host": "clientb.simplets.com.au"})

    assert patched.status_code == 200
    assert patched.json()["branding_primary_color"] == "#0a5cff"
    assert untouched.json()["branding_logo_url"] is None
