"""Clerk session-token verification (COA-274).

Active when STS_AUTH_MODE=clerk. Verifies the Authorization bearer token as a
Clerk session JWT (RS256) against the instance JWKS, then maps it to the STS
CurrentUser identity. Workspace membership/roles remain STS-owned (workspace_users).

Required environment:
- CLERK_ISSUER            e.g. https://your-instance.clerk.accounts.dev
- CLERK_AUTHORIZED_PARTIES  comma-separated origins allowed as azp (optional)
- STS_PLATFORM_ADMINS     comma-separated Clerk user IDs with platform access
"""

import os
import time

import httpx
import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

_JWKS_CLIENTS: dict[str, PyJWKClient] = {}
_JWKS_CACHE_TTL_SECONDS = 300


def _issuer() -> str:
    issuer = os.environ.get("CLERK_ISSUER", "").rstrip("/")
    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_ISSUER is not configured",
        )
    return issuer


def _authorized_parties() -> set[str]:
    raw = os.environ.get("CLERK_AUTHORIZED_PARTIES", "")
    return {value.strip() for value in raw.split(",") if value.strip()}


def _jwks_client(issuer: str) -> PyJWKClient:
    client = _JWKS_CLIENTS.get(issuer)
    if client is None:
        client = PyJWKClient(f"{issuer}/.well-known/jwks.json", cache_keys=True, lifespan=_JWKS_CACHE_TTL_SECONDS)
        _JWKS_CLIENTS[issuer] = client
    return client


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return token.strip()


def decode_session_token(token: str):
    issuer = _issuer()
    try:
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
            leeway=5,
        )
    except (jwt.PyJWTError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session token") from exc

    azp = claims.get("azp")
    allowed = _authorized_parties()
    if allowed and azp and azp not in allowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session token")

    nbf = claims.get("nbf")
    if nbf is not None and nbf > time.time() + 5:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session token")

    return claims


def verify_clerk_request(request: Request):
    from app.auth import CurrentUser, platform_admin_ids

    claims = decode_session_token(_bearer_token(request))
    user_id = claims["sub"]
    metadata = claims.get("public_metadata") or {}
    is_platform_admin = bool(metadata.get("platform_admin")) or user_id in platform_admin_ids()
    return CurrentUser(user_id=user_id, is_platform_admin=is_platform_admin)
