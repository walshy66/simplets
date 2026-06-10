import os
import re
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status

from app.db import get_connection
from app.models import FeatureKey
from app.schemas import Workspace

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RESERVED_SUBDOMAINS = {"www", "api", "app", "admin", "platform", "portal", "mail"}
DEV_HOSTS = {"localhost", "127.0.0.1", "testserver"}
DEFAULT_DEV_SUBDOMAIN = "coachcw"


def base_domain() -> str:
    return os.environ.get("STS_BASE_DOMAIN", "simplets.com.au").lower()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def row_to_workspace(row: sqlite3.Row) -> Workspace:
    return Workspace(**dict(row))


def validate_subdomain(subdomain: str) -> str:
    clean = subdomain.strip().lower()
    if not SUBDOMAIN_PATTERN.match(clean):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="subdomain must be lowercase letters, digits, or hyphens",
        )
    if clean in RESERVED_SUBDOMAINS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="subdomain is reserved")
    return clean


def workspace_by_subdomain(conn: sqlite3.Connection, subdomain: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM workspaces WHERE subdomain = ?", (subdomain,)).fetchone()


def create_workspace_record(conn: sqlite3.Connection, name: str, subdomain: str) -> sqlite3.Row:
    workspace_id = str(uuid4())
    timestamp = now_iso()
    conn.execute(
        "INSERT INTO workspaces (id, name, subdomain, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (workspace_id, name, subdomain, timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO workspace_feature_flags (workspace_id, feature_key, enabled, updated_at) VALUES (?, ?, 1, ?)",
        (workspace_id, FeatureKey.WORKFLOW_AUTOMATION.value, timestamp),
    )
    conn.commit()
    return conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()


def _host_without_port(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return host.split(":")[0].strip().lower()


def _subdomain_for_host(host: str) -> str | None:
    suffix = "." + base_domain()
    if host.endswith(suffix):
        label = host[: -len(suffix)]
        if label and "." not in label:
            return label
    return None


def resolve_workspace(request: Request, conn: sqlite3.Connection = Depends(get_connection)) -> Workspace:
    """Resolve the request's workspace from the subdomain on the Host header.

    Local development hosts fall back to an auto-provisioned dev workspace so the
    portal works on localhost before wildcard DNS exists. Real subscriber hosts
    must match exactly one provisioned workspace subdomain.
    """
    host = _host_without_port(request)
    subdomain = _subdomain_for_host(host)
    if subdomain is None:
        if host not in DEV_HOSTS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown workspace host")
        subdomain = (
            request.headers.get("x-sts-workspace")
            or os.environ.get("STS_DEV_WORKSPACE", DEFAULT_DEV_SUBDOMAIN)
        ).strip().lower()
        row = workspace_by_subdomain(conn, subdomain)
        if row is None:
            row = create_workspace_record(conn, name=subdomain, subdomain=validate_subdomain(subdomain))
        return row_to_workspace(row)

    row = workspace_by_subdomain(conn, subdomain)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found for host")
    return row_to_workspace(row)
