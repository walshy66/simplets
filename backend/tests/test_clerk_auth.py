"""COA-274: Clerk session-token verification in front of workspace roles."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import clerk, db
from app.main import app

ISSUER = "https://sts-test.clerk.accounts.dev"
HOST = {"host": "clienta.simplets.com.au"}


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def clerk_mode(monkeypatch, tmp_path, rsa_keys):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "simplets.sqlite3")
    monkeypatch.setenv("STS_AUTH_MODE", "clerk")
    monkeypatch.setenv("CLERK_ISSUER", ISSUER)
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)

    _, public_key = rsa_keys
    fake_client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=public_key))
    monkeypatch.setattr(clerk, "_jwks_client", lambda issuer: fake_client)

    seed_workspace()


def seed_workspace():
    db.init_db()
    timestamp = "2026-01-01T00:00:00+00:00"
    with db.sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO workspaces (id, name, subdomain, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("ws-a", "Client A", "clienta", timestamp, timestamp),
        )
        conn.execute(
            "INSERT INTO workspace_users (id, workspace_id, user_id, role, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("membership-1", "ws-a", "user_rita", "reviewer", timestamp, timestamp),
        )
        conn.commit()


def mint(private_key, *, sub="user_rita", issuer=ISSUER, expires_in=120, azp=None, metadata=None, nbf=None):
    now = int(time.time())
    claims = {"sub": sub, "iss": issuer, "iat": now, "exp": now + expires_in}
    if azp is not None:
        claims["azp"] = azp
    if metadata is not None:
        claims["public_metadata"] = metadata
    if nbf is not None:
        claims["nbf"] = nbf
    return jwt.encode(claims, private_key, algorithm="RS256")


def bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}", **HOST}


def test_valid_clerk_token_authenticates_member(clerk_mode, rsa_keys):
    private_key, _ = rsa_keys
    with TestClient(app) as client:
        response = client.get("/workflow-runs/review-queue", headers=bearer(mint(private_key)))

    assert response.status_code == 200


def test_missing_bearer_token_is_401(clerk_mode):
    with TestClient(app) as client:
        response = client.get("/workflow-runs/review-queue", headers=HOST)

    assert response.status_code == 401


def test_expired_token_is_401(clerk_mode, rsa_keys):
    private_key, _ = rsa_keys
    with TestClient(app) as client:
        response = client.get(
            "/workflow-runs/review-queue", headers=bearer(mint(private_key, expires_in=-300))
        )

    assert response.status_code == 401


def test_wrong_issuer_is_401(clerk_mode, rsa_keys):
    private_key, _ = rsa_keys
    with TestClient(app) as client:
        response = client.get(
            "/workflow-runs/review-queue",
            headers=bearer(mint(private_key, issuer="https://evil.example.com")),
        )

    assert response.status_code == 401


def test_dev_header_is_ignored_in_clerk_mode(clerk_mode):
    with TestClient(app) as client:
        response = client.get("/workflow-runs/review-queue", headers={"x-sts-user": "user_rita", **HOST})

    assert response.status_code == 401


def test_unauthorized_party_is_401(clerk_mode, rsa_keys, monkeypatch):
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://coachcw.simplets.com.au")
    private_key, _ = rsa_keys
    with TestClient(app) as client:
        allowed = client.get(
            "/workflow-runs/review-queue",
            headers=bearer(mint(private_key, azp="https://coachcw.simplets.com.au")),
        )
        denied = client.get(
            "/workflow-runs/review-queue",
            headers=bearer(mint(private_key, azp="https://attacker.example.com")),
        )

    assert allowed.status_code == 200
    assert denied.status_code == 401


def test_clerk_user_without_membership_is_403(clerk_mode, rsa_keys):
    private_key, _ = rsa_keys
    with TestClient(app) as client:
        response = client.get("/workflow-runs/review-queue", headers=bearer(mint(private_key, sub="user_stranger")))

    assert response.status_code == 403


def test_platform_admin_claim_grants_platform_access(clerk_mode, rsa_keys):
    private_key, _ = rsa_keys
    with TestClient(app) as client:
        token = mint(private_key, sub="user_root", metadata={"platform_admin": True})
        response = client.get("/workspaces", headers=bearer(token))

    assert response.status_code == 200
