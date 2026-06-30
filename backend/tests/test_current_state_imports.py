"""COA-297/299: generic imports create workspace-scoped conversion jobs with source retention cleanup."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.test_current_state_maps import HOST_A, HOST_A_REVIEWER, HOST_A_SUBMITTER, HOST_B, seed_workspaces, use_temp_db


def test_current_state_import_upload_deletes_source_and_keeps_redacted_audit_metadata(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        response = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("Client PII Export.pdf", b"demo", "application/pdf")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["workspace_id"] == "ws-a"
    assert body["status"] == "failed"
    assert body["file_type"] == "application/pdf"
    assert body["uploader"] == "alice-admin"
    assert body["filename_redacted"] == "[redacted].pdf"
    assert body["filename_display"] == "Client PII Export.pdf"
    assert body["dismissed_at"] is None
    assert len(body["filename_hash"]) == 64
    assert "temporary_storage_path" not in body
    assert "source_deleted_at" not in body
    assert "source_retention_expires_at" not in body

    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        row = conn.execute("SELECT * FROM current_state_import_jobs WHERE id = ?", (body["id"],)).fetchone()
    assert not Path(row["temporary_storage_path"]).exists()
    assert row["source_deleted_at"] is not None
    assert row["source_retention_expires_at"] is not None


def test_current_state_imports_are_workspace_scoped_and_staff_only(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post(
            "/current-state-imports",
            headers=HOST_A_REVIEWER,
            files={"file": ("diagram.png", b"demo", "image/png")},
        ).json()
        own_list = client.get("/current-state-imports", headers=HOST_A_REVIEWER)
        other_list = client.get("/current-state-imports", headers=HOST_B)
        submitter_upload = client.post(
            "/current-state-imports",
            headers=HOST_A_SUBMITTER,
            files={"file": ("diagram.png", b"demo", "image/png")},
        )
        other_retry = client.post(f"/current-state-imports/{created['id']}/retry", headers=HOST_B)

    assert [item["id"] for item in own_list.json()] == [created["id"]]
    assert other_list.json() == []
    assert submitter_upload.status_code == 403
    assert other_retry.status_code == 404


def test_current_state_import_upload_converts_artifact_to_cleanup_required_draft_map_and_deletes_source(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        response = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("process.xml", b"Sales | Intake | Receive form | process\nCRM | Review | Update record | document\nReceive form -> Update record | handoff", "application/xml")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result_map_id"]
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        job = conn.execute("SELECT * FROM current_state_import_jobs WHERE id = ?", (body["id"],)).fetchone()
        draft = conn.execute("SELECT * FROM current_state_maps WHERE id = ?", (body["result_map_id"],)).fetchone()
    assert not Path(job["temporary_storage_path"]).exists()
    assert job["source_deleted_at"] is not None
    assert draft["status"] == "draft"
    assert "AI-imported draft" in draft["title"]
    assert {node["node_type"] for node in __import__("json").loads(draft["nodes"])} == {"process", "document"}
    assert __import__("json").loads(draft["connectors"])[0]["label"] == "handoff"
    assert "requires human cleanup" in draft["comments"]


def test_current_state_import_upload_parses_drawio_vertices_edges_and_swimlanes(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()
    drawio = b'''<mxfile host="app.diagrams.net"><diagram name="Client Intake"><mxGraphModel><root>
      <mxCell id="0"/><mxCell id="1" parent="0"/>
      <mxCell id="lane" parent="1" style="shape=tableRow;" value="Operations" vertex="1"><mxGeometry as="geometry"/></mxCell>
      <mxCell id="phase" parent="lane" style="swimlane;" value="Triage" vertex="1"><mxGeometry as="geometry"/></mxCell>
      <mxCell id="start" parent="phase" style="rounded=1;whiteSpace=wrap;html=1;" value="Receive referral" vertex="1"><mxGeometry x="10" y="20" width="120" height="60" as="geometry"/></mxCell>
      <mxCell id="decision" parent="phase" style="shape=mxgraph.flowchart.decision;whiteSpace=wrap;html=1;" value="Suitable?" vertex="1"><mxGeometry x="160" y="20" width="100" height="80" as="geometry"/></mxCell>
      <mxCell id="edge" parent="phase" source="start" target="decision" value="review" edge="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    </root></mxGraphModel></diagram></mxfile>'''

    with TestClient(app) as client:
        response = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("client-intake.drawio", drawio, "application/octet-stream")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        draft = conn.execute("SELECT * FROM current_state_maps WHERE id = ?", (body["result_map_id"],)).fetchone()
    assert draft["title"] == "Client Intake"
    assert json.loads(draft["lanes"])[0]["title"] == "Operations"
    assert json.loads(draft["phases"])[0]["title"] == "Triage"
    nodes = json.loads(draft["nodes"])
    assert [node["title"] for node in nodes] == ["Receive referral", "Suitable?"]
    assert {node["node_type"] for node in nodes} == {"process", "decision"}
    assert nodes[0]["position"] == {"x": 220, "y": 140}
    assert nodes[1]["position"] == {"x": 500, "y": 140}
    assert json.loads(draft["connectors"])[0]["label"] == "review"


def test_current_state_import_conversion_failure_deletes_source_and_exposes_retryable_error(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        response = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("blank.pdf", b"", "application/pdf")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert "could not extract" in body["error_message"]
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        job = conn.execute("SELECT * FROM current_state_import_jobs WHERE id = ?", (body["id"],)).fetchone()
    assert not Path(job["temporary_storage_path"]).exists()
    assert job["source_deleted_at"] is not None


def test_current_state_import_cleanup_deletes_expired_pending_or_failed_sources_without_exposing_storage_paths(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        pending = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("pending.drawio", b"demo", "application/xml")},
        ).json()

    stale_source = tmp_path / "data" / "current-state-imports" / pending["id"] / "source"
    stale_source.parent.mkdir(parents=True, exist_ok=True)
    stale_source.write_bytes(b"stale sensitive content")
    expired_at = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "UPDATE current_state_import_jobs SET status = ?, temporary_storage_path = ?, source_deleted_at = NULL, source_retention_expires_at = ? WHERE id = ?",
            ("failed", str(stale_source), expired_at, pending["id"]),
        )
        conn.commit()

    from app.current_state import cleanup_expired_import_sources

    deleted = cleanup_expired_import_sources()

    assert deleted == 1
    assert not stale_source.exists()
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        row = conn.execute("SELECT * FROM current_state_import_jobs WHERE id = ?", (pending["id"],)).fetchone()
    assert row["source_deleted_at"] is not None
    assert row["filename_redacted"] == "[redacted].drawio"


def test_failed_current_state_import_can_be_dismissed_from_default_list(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("failed.drawio", b"demo", "application/xml")},
        ).json()
        dismiss = client.post(f"/current-state-imports/{created['id']}/dismiss", headers=HOST_A)
        failed_list = client.get("/current-state-imports", headers=HOST_A)

    assert dismiss.status_code == 200, dismiss.text
    assert dismiss.json()["dismissed_at"] is not None
    assert failed_list.status_code == 200
    assert failed_list.json() == []
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        row = conn.execute("SELECT * FROM current_state_import_jobs WHERE id = ?", (created["id"],)).fetchone()
    assert row["dismissed_at"] is not None
    assert row["filename_redacted"] == "[redacted].drawio"


def test_current_state_import_upload_parses_mermaid_flowchart(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()
    mermaid = b'''flowchart LR
      A([Start]) --> B[Receive referral]
      B -->|review| C{Suitable?}
      C --> D[/Create file/]
      D --> E([End])
    '''

    with TestClient(app) as client:
        response = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("client-intake.mmd", mermaid, "text/plain")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        draft = conn.execute("SELECT * FROM current_state_maps WHERE id = ?", (body["result_map_id"],)).fetchone()
    nodes = json.loads(draft["nodes"])
    assert [node["title"] for node in nodes] == ["Start", "Receive referral", "Suitable?", "Create file", "End"]
    assert [node["node_type"] for node in nodes] == ["start", "process", "decision", "document", "end"]
    assert json.loads(draft["connectors"])[1]["label"] == "review"


def test_current_state_import_upload_parses_bpmn_process(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()
    bpmn = b'''<?xml version="1.0" encoding="UTF-8"?>
    <definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
      <process id="client_intake">
        <startEvent id="start" name="Start" />
        <task id="receive" name="Receive referral" />
        <exclusiveGateway id="decision" name="Suitable?" />
        <endEvent id="end" name="End" />
        <sequenceFlow id="flow1" sourceRef="start" targetRef="receive" />
        <sequenceFlow id="flow2" name="review" sourceRef="receive" targetRef="decision" />
        <sequenceFlow id="flow3" sourceRef="decision" targetRef="end" />
      </process>
    </definitions>'''

    with TestClient(app) as client:
        response = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("client-intake.bpmn", bpmn, "application/xml")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = db.sqlite3.Row
        draft = conn.execute("SELECT * FROM current_state_maps WHERE id = ?", (body["result_map_id"],)).fetchone()
    nodes = json.loads(draft["nodes"])
    assert [node["node_type"] for node in nodes] == ["start", "process", "decision", "end"]
    assert json.loads(draft["connectors"])[1]["label"] == "review"


def test_failed_current_state_import_job_is_visible_and_retryable(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    seed_workspaces()

    with TestClient(app) as client:
        created = client.post(
            "/current-state-imports",
            headers=HOST_A,
            files={"file": ("export.drawio", b"demo", "application/xml")},
        ).json()
        with db.sqlite3.connect(db.DB_PATH) as conn:
            conn.execute(
                "UPDATE current_state_import_jobs SET status = ?, error_message = ? WHERE id = ?",
                ("failed", "unsupported format", created["id"]),
            )
            conn.commit()
        failed_list = client.get("/current-state-imports", headers=HOST_A)
        retry = client.post(f"/current-state-imports/{created['id']}/retry", headers=HOST_A)

    assert failed_list.status_code == 200
    assert failed_list.json()[0]["status"] == "failed"
    assert failed_list.json()[0]["error_message"] == "unsupported format"
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "pending"
    assert retry.json()["error_message"] is None
