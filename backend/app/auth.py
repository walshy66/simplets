import os
import sqlite3
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.db import get_connection
from app.models import WorkspaceRole
from app.schemas import Workspace
from app.tenancy import resolve_workspace

DEV_USER_HEADER = "x-sts-user"


def auth_mode() -> str:
    return os.environ.get("STS_AUTH_MODE", "dev").lower()


def platform_admin_ids() -> set[str]:
    raw = os.environ.get("STS_PLATFORM_ADMINS", "platform-admin")
    return {value.strip() for value in raw.split(",") if value.strip()}


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    is_platform_admin: bool


def get_current_user(request: Request) -> CurrentUser:
    """Resolve the authenticated user.

    Dev mode trusts the X-STS-User header so local demos and tests can act as
    named users. Production mode is wired to Clerk session verification
    (COA-274); requests without a verifiable identity always get 401.
    """
    if auth_mode() == "dev":
        user_id = (request.headers.get(DEV_USER_HEADER) or "").strip()
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        return CurrentUser(user_id=user_id, is_platform_admin=user_id in platform_admin_ids())

    from app.clerk import verify_clerk_request  # imported lazily so dev mode never needs Clerk config

    return verify_clerk_request(request)


def require_platform_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="platform admin access required")
    return user


@dataclass(frozen=True)
class WorkspaceActor:
    user: CurrentUser
    workspace: Workspace
    role: WorkspaceRole | None  # None for platform admins acting without a membership


def membership_role(conn: sqlite3.Connection, workspace_id: str, user_id: str) -> WorkspaceRole | None:
    row = conn.execute(
        "SELECT role FROM workspace_users WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return WorkspaceRole(row["role"])


def require_workspace_role(*allowed: WorkspaceRole):
    """Dependency factory: the current user must hold one of the allowed roles
    in the request's resolved workspace. Platform admins always pass.

    Role is read from the database on every request, so role changes take
    effect immediately without re-login.
    """

    def dependency(
        user: CurrentUser = Depends(get_current_user),
        workspace: Workspace = Depends(resolve_workspace),
        conn: sqlite3.Connection = Depends(get_connection),
    ) -> WorkspaceActor:
        if user.is_platform_admin:
            return WorkspaceActor(user=user, workspace=workspace, role=None)
        role = membership_role(conn, workspace.id, user.user_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a member of this workspace")
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"requires one of: {', '.join(allowed)}")
        return WorkspaceActor(user=user, workspace=workspace, role=role)

    return dependency


require_any_staff = require_workspace_role(WorkspaceRole.ADMIN, WorkspaceRole.REVIEWER, WorkspaceRole.OPERATOR)
require_reviewer = require_workspace_role(WorkspaceRole.ADMIN, WorkspaceRole.REVIEWER)
require_admin = require_workspace_role(WorkspaceRole.ADMIN)
