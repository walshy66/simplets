import sqlite3
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, WorkspaceActor, require_admin, require_platform_admin
from app.db import get_connection
from app.schemas import (
    Workspace,
    WorkspaceBrandingUpdate,
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


@router.get("/current", response_model=Workspace)
def current_workspace(workspace: Workspace = Depends(resolve_workspace)) -> Workspace:
    return workspace


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
