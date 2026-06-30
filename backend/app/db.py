import os
import sqlite3
from pathlib import Path
from typing import Iterator

ROOT_DIR = Path(__file__).resolve().parents[2]
# Local dev keeps data in the repo's gitignored data/ folder; deployed machines
# point STS_DATA_DIR at a mounted volume (see backend/fly.toml).
DATA_DIR = Path(os.environ.get("STS_DATA_DIR", "") or ROOT_DIR / "data")
DB_PATH = DATA_DIR / "simplets.sqlite3"
UPLOADS_DIR = DATA_DIR / "uploads"


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                repo_path TEXT,
                harness TEXT NOT NULL CHECK (harness IN ('test', 'codex', 'pi')),
                prompt TEXT,
                model TEXT,
                status TEXT NOT NULL CHECK (status IN ('created', 'running', 'stopped', 'completed', 'errored')),
                branch_name TEXT,
                log_path TEXT,
                output_tail TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        existing_columns = {column[1] for column in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "model" not in existing_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
        if "output_tail" not in existing_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN output_tail TEXT")
        if "error_message" not in existing_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN error_message TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tag TEXT NOT NULL CHECK (tag IN ('comment', 'note', 'attachment', 'handoff', 'status', 'prompt', 'branch')),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                subdomain TEXT,
                branding_logo_url TEXT,
                branding_primary_color TEXT,
                activepieces_project_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        workspace_columns = {column[1] for column in conn.execute("PRAGMA table_info(workspaces)").fetchall()}
        if "subdomain" not in workspace_columns:
            conn.execute("ALTER TABLE workspaces ADD COLUMN subdomain TEXT")
        if "branding_logo_url" not in workspace_columns:
            conn.execute("ALTER TABLE workspaces ADD COLUMN branding_logo_url TEXT")
        if "branding_primary_color" not in workspace_columns:
            conn.execute("ALTER TABLE workspaces ADD COLUMN branding_primary_color TEXT")
        if "activepieces_project_id" not in workspace_columns:
            conn.execute("ALTER TABLE workspaces ADD COLUMN activepieces_project_id TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_subdomain ON workspaces(subdomain)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_users (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'reviewer', 'operator')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_feature_flags (
                workspace_id TEXT NOT NULL,
                feature_key TEXT NOT NULL CHECK (feature_key IN ('workflow_automation')),
                enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, feature_key),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                intent TEXT NOT NULL,
                temporary_storage_path TEXT NOT NULL,
                retention_expires_at TEXT NOT NULL,
                deletion_status TEXT NOT NULL CHECK (deletion_status IN ('retained', 'deleted')),
                uploaded_at TEXT NOT NULL,
                uploader TEXT NOT NULL,
                is_permanent_archive INTEGER NOT NULL CHECK (is_permanent_archive IN (0, 1)) DEFAULT 0,
                drive_file_id TEXT,
                drive_web_url TEXT,
                filename_hash TEXT,
                filename_redacted TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                document_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('created', 'running', 'completed', 'errored')),
                extraction_status TEXT,
                extraction_error TEXT,
                suggested_classification TEXT,
                extracted_fields TEXT,
                review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'approved')) DEFAULT 'pending',
                last_reviewed_by TEXT,
                last_reviewed_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                destination_record_id TEXT,
                audit_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS connector_connections (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('connected', 'disconnected')),
                encrypted_access_token TEXT,
                encrypted_refresh_token TEXT,
                token_expires_at TEXT,
                scopes TEXT,
                external_account_label TEXT,
                disconnect_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (workspace_id, provider),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_drive_datastores (
                workspace_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL CHECK (provider = 'google_drive'),
                drive_root_id TEXT NOT NULL,
                invoice_folder_id TEXT NOT NULL,
                folder_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS destination_pushes (
                id TEXT PRIMARY KEY,
                workflow_run_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed')),
                destination_record_id TEXT,
                error_message TEXT,
                attempted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (workflow_run_id, provider),
                FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS current_state_maps (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                title TEXT NOT NULL,
                version_ref TEXT,
                status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'archived')) DEFAULT 'draft',
                source_version_id TEXT,
                lanes TEXT NOT NULL,
                phases TEXT NOT NULL,
                nodes TEXT NOT NULL,
                connectors TEXT NOT NULL,
                comments TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )
        current_state_map_schema = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'current_state_maps'").fetchone()
        if current_state_map_schema and "'locked'" in (current_state_map_schema[0] or ""):
            conn.execute("ALTER TABLE current_state_maps RENAME TO current_state_maps_legacy")
            conn.execute(
                """
                CREATE TABLE current_state_maps (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    version_ref TEXT,
                    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'archived')) DEFAULT 'draft',
                    source_version_id TEXT,
                    lanes TEXT NOT NULL,
                    phases TEXT NOT NULL,
                    nodes TEXT NOT NULL,
                    connectors TEXT NOT NULL,
                    comments TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO current_state_maps (
                    id, workspace_id, title, version_ref, status, source_version_id, lanes, phases, nodes, connectors, comments, created_at, updated_at
                )
                SELECT id, workspace_id, title, version_ref, CASE status WHEN 'locked' THEN 'approved' ELSE status END, source_version_id, lanes, phases, nodes, connectors, comments, created_at, updated_at
                FROM current_state_maps_legacy
                """
            )
            conn.execute("DROP TABLE current_state_maps_legacy")
        current_state_map_columns = {column[1] for column in conn.execute("PRAGMA table_info(current_state_maps)").fetchall()}
        if "status" not in current_state_map_columns:
            conn.execute("ALTER TABLE current_state_maps ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
        if "source_version_id" not in current_state_map_columns:
            conn.execute("ALTER TABLE current_state_maps ADD COLUMN source_version_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_current_state_maps_workspace ON current_state_maps(workspace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_current_state_maps_source ON current_state_maps(source_version_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS current_state_import_jobs (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                filename_hash TEXT NOT NULL,
                filename_redacted TEXT NOT NULL,
                filename_display TEXT,
                dismissed_at TEXT,
                file_type TEXT NOT NULL,
                uploader TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed')),
                error_message TEXT,
                temporary_storage_path TEXT NOT NULL,
                source_deleted_at TEXT,
                source_retention_expires_at TEXT,
                result_map_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
            """
        )
        current_state_import_columns = {column[1] for column in conn.execute("PRAGMA table_info(current_state_import_jobs)").fetchall()}
        if "result_map_id" not in current_state_import_columns:
            conn.execute("ALTER TABLE current_state_import_jobs ADD COLUMN result_map_id TEXT")
        if "source_retention_expires_at" not in current_state_import_columns:
            conn.execute("ALTER TABLE current_state_import_jobs ADD COLUMN source_retention_expires_at TEXT")
        if "filename_display" not in current_state_import_columns:
            conn.execute("ALTER TABLE current_state_import_jobs ADD COLUMN filename_display TEXT")
        if "dismissed_at" not in current_state_import_columns:
            conn.execute("ALTER TABLE current_state_import_jobs ADD COLUMN dismissed_at TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_current_state_import_jobs_workspace ON current_state_import_jobs(workspace_id)")

        document_columns = {column[1] for column in conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "workspace_id" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN workspace_id TEXT")
        if "drive_file_id" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN drive_file_id TEXT")
        if "drive_web_url" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN drive_web_url TEXT")
        if "filename_hash" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN filename_hash TEXT")
        if "filename_redacted" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN filename_redacted TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id)")

        workflow_run_columns = {column[1] for column in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()}
        if "workspace_id" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN workspace_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_workspace ON workflow_runs(workspace_id)")
        if "extraction_status" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN extraction_status TEXT")
        if "extraction_error" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN extraction_error TEXT")
        if "suggested_classification" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN suggested_classification TEXT")
        if "extracted_fields" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN extracted_fields TEXT")
        if "review_status" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved'))")
        if "last_reviewed_by" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN last_reviewed_by TEXT")
        if "last_reviewed_at" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN last_reviewed_at TEXT")
        if "approved_by" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN approved_by TEXT")
        if "approved_at" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN approved_at TEXT")
        if "destination_record_id" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN destination_record_id TEXT")
        if "audit_summary" not in workflow_run_columns:
            conn.execute("ALTER TABLE workflow_runs ADD COLUMN audit_summary TEXT")
        conn.commit()


def get_connection() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
