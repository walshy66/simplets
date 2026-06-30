import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth import CurrentUser, WorkspaceActor, require_admin, require_platform_admin
from app.db import get_connection
from app.schemas import (
    ClientContext,
    DriveDatastore,
    DriveDatastoreSetup,
    InvoiceUploadGate,
    Workspace,
    WorkspaceBrandingUpdate,
    WorkspaceCanvasUpdate,
    WorkspaceCreate,
    WorkspaceUser,
    WorkspaceUserUpsert,
)
from app.tenancy import (
    create_workspace_record,
    now_iso,
    resolve_workspace,
    row_to_workspace,
    validate_subdomain,
    workspace_by_subdomain,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024
BRANDING_ASSET_DIR = Path("data/workspace-branding")


@router.post("", response_model=Workspace, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    conn: sqlite3.Connection = Depends(get_connection),
    _admin: CurrentUser = Depends(require_platform_admin),
) -> Workspace:
    subdomain = validate_subdomain(payload.subdomain)
    if workspace_by_subdomain(conn, subdomain) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="subdomain already provisioned")
    return row_to_workspace(create_workspace_record(conn, name=payload.name.strip(), subdomain=subdomain))


@router.get("", response_model=list[Workspace])
def list_workspaces(
    conn: sqlite3.Connection = Depends(get_connection),
    _admin: CurrentUser = Depends(require_platform_admin),
) -> list[Workspace]:
    rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at").fetchall()
    return [row_to_workspace(row) for row in rows]


def current_drive_datastore(conn: sqlite3.Connection, workspace_id: str) -> DriveDatastore | None:
    row = conn.execute(
        "SELECT provider, drive_root_id, invoice_folder_id, folder_path FROM workspace_drive_datastores WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()
    return DriveDatastore(**dict(row)) if row else None


@router.get("/current", response_model=Workspace)
def current_workspace(workspace: Workspace = Depends(resolve_workspace)) -> Workspace:
    return workspace


@router.get("/current/client-context", response_model=ClientContext)
def current_client_context(
    workspace: Workspace = Depends(resolve_workspace),
    conn: sqlite3.Connection = Depends(get_connection),
) -> ClientContext:
    datastore = current_drive_datastore(conn, workspace.id)
    return ClientContext(
        workspace=workspace,
        drive_datastore=datastore,
        invoice_upload=InvoiceUploadGate(
            available=datastore is not None,
            reason=None if datastore else "google_drive_datastore_setup_required",
        ),
    )


@router.put("/current/client-context/drive-datastore", response_model=ClientContext)
def set_drive_datastore(
    payload: DriveDatastoreSetup,
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> ClientContext:
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO workspace_drive_datastores (
            workspace_id, provider, drive_root_id, invoice_folder_id, folder_path, created_at, updated_at
        ) VALUES (?, 'google_drive', ?, ?, ?, ?, ?)
        ON CONFLICT (workspace_id) DO UPDATE SET
            drive_root_id = excluded.drive_root_id,
            invoice_folder_id = excluded.invoice_folder_id,
            folder_path = excluded.folder_path,
            updated_at = excluded.updated_at
        """,
        (
            actor.workspace.id,
            payload.drive_root_id.strip(),
            payload.invoice_folder_id.strip(),
            payload.folder_path.strip() if payload.folder_path else None,
            timestamp,
            timestamp,
        ),
    )
    conn.commit()
    datastore = current_drive_datastore(conn, actor.workspace.id)
    return ClientContext(
        workspace=actor.workspace,
        drive_datastore=datastore,
        invoice_upload=InvoiceUploadGate(available=True),
    )


@router.post("/current/branding/logo", response_model=Workspace)
async def upload_branding_logo(
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
    file: UploadFile = File(),
) -> Workspace:
    extension = ALLOWED_LOGO_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="workspace logo must be a PNG, JPEG, WebP, or SVG image",
        )

    content = await file.read(MAX_LOGO_BYTES + 1)
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="workspace logo is too large")

    workspace_dir = BRANDING_ASSET_DIR / actor.workspace.id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    for stale in workspace_dir.glob("logo.*"):
        stale.unlink(missing_ok=True)
    logo_path = workspace_dir / f"logo{extension}"
    logo_path.write_bytes(content)
    logo_url = f"/workspace-branding/{actor.workspace.id}/logo{extension}"

    conn.execute(
        """
        UPDATE workspaces
        SET branding_logo_url = ?, updated_at = ?
        WHERE id = ?
        """,
        (logo_url, now_iso(), actor.workspace.id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (actor.workspace.id,)).fetchone()
    return row_to_workspace(row)


@router.patch("/current/branding", response_model=Workspace)
def update_branding(
    payload: WorkspaceBrandingUpdate,
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> Workspace:
    conn.execute(
        """
        UPDATE workspaces
        SET branding_logo_url = ?, branding_primary_color = ?, updated_at = ?
        WHERE id = ?
        """,
        (payload.logo_url, payload.primary_color, now_iso(), actor.workspace.id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (actor.workspace.id,)).fetchone()
    return row_to_workspace(row)


@router.get("/current/canvas")
def workflow_canvas(
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> dict[str, str]:
    """Embed URL for the white-labeled workflow canvas (COA-284).

    The canvas URL is only issued to authenticated workspace admins, and is
    scoped to the workspace's own Activepieces project so subscribers only see
    their workflows. STS_ACTIVEPIECES_URL points at the forked, branding-free
    instance.
    """
    base_url = os.environ.get("STS_ACTIVEPIECES_URL", "").rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow canvas is not configured (STS_ACTIVEPIECES_URL)",
        )
    project_id = actor.workspace.activepieces_project_id
    embed_url = f"{base_url}/projects/{project_id}/flows" if project_id else f"{base_url}/flows"
    return {"embed_url": embed_url}


@router.patch("/current/canvas", response_model=Workspace)
def set_canvas_project(
    payload: WorkspaceCanvasUpdate,
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> Workspace:
    conn.execute(
        "UPDATE workspaces SET activepieces_project_id = ?, updated_at = ? WHERE id = ?",
        (payload.activepieces_project_id, now_iso(), actor.workspace.id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (actor.workspace.id,)).fetchone()
    return row_to_workspace(row)


@router.get("/current/users", response_model=list[WorkspaceUser])
def list_workspace_users(
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[WorkspaceUser]:
    rows = conn.execute(
        "SELECT * FROM workspace_users WHERE workspace_id = ? ORDER BY created_at",
        (actor.workspace.id,),
    ).fetchall()
    return [WorkspaceUser(**dict(row)) for row in rows]


@router.put("/current/users/{user_id}", response_model=WorkspaceUser)
def upsert_workspace_user(
    user_id: str,
    payload: WorkspaceUserUpsert,
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> WorkspaceUser:
    timestamp = now_iso()
    existing = conn.execute(
        "SELECT * FROM workspace_users WHERE workspace_id = ? AND user_id = ?",
        (actor.workspace.id, user_id),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO workspace_users (id, workspace_id, user_id, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid4()), actor.workspace.id, user_id, payload.role.value, timestamp, timestamp),
        )
    else:
        conn.execute(
            "UPDATE workspace_users SET role = ?, updated_at = ? WHERE id = ?",
            (payload.role.value, timestamp, existing["id"]),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM workspace_users WHERE workspace_id = ? AND user_id = ?",
        (actor.workspace.id, user_id),
    ).fetchone()
    return WorkspaceUser(**dict(row))


@router.delete("/current/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workspace_user(
    user_id: str,
    actor: WorkspaceActor = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_connection),
) -> None:
    existing = conn.execute(
        "SELECT * FROM workspace_users WHERE workspace_id = ? AND user_id = ?",
        (actor.workspace.id, user_id),
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace user not found")
    conn.execute("DELETE FROM workspace_users WHERE id = ?", (existing["id"],))
    conn.commit()
