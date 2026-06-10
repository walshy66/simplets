import sqlite3

import pytest
from pydantic import ValidationError

from app import db
from app.models import FeatureKey, WorkspaceRole
from app.schemas import WorkspaceFeatureFlag, WorkspaceUser


def use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "simplets.sqlite3")


def table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    return [column["name"] for column in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]


def create_sql(conn: sqlite3.Connection, table_name: str) -> str:
    return conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)).fetchone()["sql"]


def test_workspace_tables_define_users_roles_and_feature_flags(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    db.init_db()

    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        assert table_columns(conn, "workspaces") == [
            "id",
            "name",
            "subdomain",
            "branding_logo_url",
            "branding_primary_color",
            "created_at",
            "updated_at",
        ]
        assert table_columns(conn, "workspace_users") == [
            "id",
            "workspace_id",
            "user_id",
            "role",
            "created_at",
            "updated_at",
        ]
        assert table_columns(conn, "workspace_feature_flags") == [
            "workspace_id",
            "feature_key",
            "enabled",
            "updated_at",
        ]

        workspace_users_sql = create_sql(conn, "workspace_users")
        feature_flags_sql = create_sql(conn, "workspace_feature_flags")
    finally:
        conn.close()

    assert "CHECK (role IN ('admin', 'reviewer', 'operator'))" in workspace_users_sql
    assert "FOREIGN KEY (workspace_id) REFERENCES workspaces(id)" in workspace_users_sql
    assert "CHECK (feature_key IN ('workflow_automation'))" in feature_flags_sql
    assert "CHECK (enabled IN (0, 1))" in feature_flags_sql
    assert "PRIMARY KEY (workspace_id, feature_key)" in feature_flags_sql
    assert "FOREIGN KEY (workspace_id) REFERENCES workspaces(id)" in feature_flags_sql


@pytest.mark.parametrize("role", list(WorkspaceRole))
def test_workspace_user_accepts_defined_roles(role):
    item = WorkspaceUser(
        id="membership-1",
        workspace_id="workspace-1",
        user_id="user-1",
        role=role,
        created_at="2026-05-25T00:00:00+00:00",
        updated_at="2026-05-25T00:00:00+00:00",
    )

    assert item.role == role


def test_workspace_user_rejects_unknown_role():
    with pytest.raises(ValidationError):
        WorkspaceUser(
            id="membership-1",
            workspace_id="workspace-1",
            user_id="user-1",
            role="owner",
            created_at="2026-05-25T00:00:00+00:00",
            updated_at="2026-05-25T00:00:00+00:00",
        )


def test_workflow_automation_feature_flag_can_be_disabled_per_workspace(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    db.init_db()

    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            "INSERT INTO workspaces (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("workspace-1", "Demo workspace", "2026-05-25T00:00:00Z", "2026-05-25T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO workspace_feature_flags (workspace_id, feature_key, enabled, updated_at) VALUES (?, ?, ?, ?)",
            ("workspace-1", FeatureKey.WORKFLOW_AUTOMATION.value, 0, "2026-05-25T00:00:00Z"),
        )
        stored = conn.execute(
            "SELECT feature_key, enabled FROM workspace_feature_flags WHERE workspace_id = ?",
            ("workspace-1",),
        ).fetchone()
    finally:
        conn.close()

    flag = WorkspaceFeatureFlag(
        workspace_id="workspace-1",
        feature_key=stored[0],
        enabled=bool(stored[1]),
        updated_at="2026-05-25T00:00:00+00:00",
    )

    assert flag.feature_key == FeatureKey.WORKFLOW_AUTOMATION
    assert flag.enabled is False


def test_workspace_schema_does_not_mutate_existing_sessions_schema(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    db.init_db()

    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        session_columns = table_columns(conn, "sessions")
    finally:
        conn.close()

    assert session_columns == [
        "id",
        "title",
        "repo_path",
        "harness",
        "prompt",
        "model",
        "status",
        "branch_name",
        "log_path",
        "output_tail",
        "error_message",
        "created_at",
        "updated_at",
    ]
