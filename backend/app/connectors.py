"""Real connector destination adapters (COA-277 HubSpot, COA-279 Google Drive,
COA-281 PandaDoc, COA-285 Xero).

Each adapter pushes approved, reviewed field values to one destination using the
workspace's stored OAuth access token. Failures raise DestinationError with a
subscriber-readable message; the push framework records them per destination and
retains data until resolved. Token refresh is wired through provider refreshers
backed by the STS developer app credentials (one app per provider, per PRD).
"""

import json
import os
from typing import Any, Callable

import httpx

from app.destinations import DestinationError

DEFAULT_TIMEOUT = 30.0

TOKEN_URLS = {
    "hubspot": "https://api.hubapi.com/oauth/v1/token",
    "google_drive": "https://oauth2.googleapis.com/token",
    "pandadoc": "https://api.pandadoc.com/oauth2/access_token",
    "xero": "https://identity.xero.com/connect/token",
}

AUTHORIZE_URLS = {
    "hubspot": "https://app.hubspot.com/oauth/authorize",
    "google_drive": "https://accounts.google.com/o/oauth2/v2/auth",
    "pandadoc": "https://app.pandadoc.com/oauth2/authorize",
    "xero": "https://login.xero.com/identity/connect/authorize",
}

DEFAULT_SCOPES = {
    "hubspot": "crm.objects.contacts.write crm.objects.deals.write oauth",
    "google_drive": "https://www.googleapis.com/auth/drive.file",
    "pandadoc": "read+write",
    "xero": "offline_access accounting.contacts accounting.transactions",
}


def client_credentials(provider: str) -> tuple[str, str]:
    prefix = f"STS_{provider.upper()}_"
    return os.environ.get(prefix + "CLIENT_ID", ""), os.environ.get(prefix + "CLIENT_SECRET", "")


def build_authorize_url(provider: str, redirect_uri: str, state: str) -> str:
    client_id, _ = client_credentials(provider)
    if not client_id:
        raise DestinationError(f"{provider} developer app credentials are not configured")
    base = AUTHORIZE_URLS[provider]
    scope = DEFAULT_SCOPES[provider]
    params = httpx.QueryParams(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
    )
    if provider == "google_drive":
        params = params.merge({"access_type": "offline", "prompt": "consent"})
    return f"{base}?{params}"


def exchange_authorization_code(
    provider: str,
    code: str,
    redirect_uri: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens. Returns token fields
    ready for connections.upsert_connection."""
    client_id, client_secret = client_credentials(provider)
    if not client_id or not client_secret:
        raise DestinationError(f"{provider} developer app credentials are not configured")
    http = client or httpx.Client(timeout=DEFAULT_TIMEOUT)
    response = http.post(
        TOKEN_URLS[provider],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if response.status_code >= 400:
        raise DestinationError(f"{provider} rejected the authorization code ({response.status_code})")
    payload = response.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "scopes": payload.get("scope"),
    }


def make_refresher(provider: str, client: httpx.Client | None = None) -> Callable[[str], dict] | None:
    """Refresher callable for connections.get_valid_access_token, or None when
    the developer app credentials are not configured."""
    client_id, client_secret = client_credentials(provider)
    if not client_id or not client_secret or provider not in TOKEN_URLS:
        return None
    http = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def refresher(refresh_token: str) -> dict:
        response = http.post(
            TOKEN_URLS[provider],
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        response.raise_for_status()
        payload = response.json()
        from datetime import UTC, datetime, timedelta

        expires_at = None
        if payload.get("expires_in"):
            expires_at = (datetime.now(UTC) + timedelta(seconds=int(payload["expires_in"]))).isoformat()
        return {
            "access_token": payload["access_token"],
            "refresh_token": payload.get("refresh_token", refresh_token),
            "token_expires_at": expires_at,
        }

    return refresher


def _full_name_parts(fields: dict[str, Any]) -> tuple[str, str]:
    full_name = str(fields.get("full_name") or fields.get("name") or "").strip()
    if not full_name:
        return "", ""
    first, _, last = full_name.partition(" ")
    return first, last


class HubSpotAdapter:
    """COA-277: create a HubSpot contact and an associated deal."""

    provider = "hubspot"
    base_url = "https://api.hubapi.com"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def push(self, access_token: str, fields: dict[str, Any], context: dict[str, Any]) -> str:
        headers = {"Authorization": f"Bearer {access_token}"}
        first_name, last_name = _full_name_parts(fields)
        contact = self.client.post(
            f"{self.base_url}/crm/v3/objects/contacts",
            headers=headers,
            json={
                "properties": {
                    "email": fields.get("email", ""),
                    "firstname": first_name,
                    "lastname": last_name,
                    "phone": fields.get("phone", ""),
                    "company": fields.get("business_name", ""),
                }
            },
        )
        if contact.status_code >= 400:
            raise DestinationError(f"HubSpot contact creation failed ({contact.status_code}): {contact.text[:200]}")
        contact_id = contact.json()["id"]

        deal_name = f"{fields.get('full_name', 'New client')} — {fields.get('services_needed', 'engagement')}"[:120]
        deal = self.client.post(
            f"{self.base_url}/crm/v3/objects/deals",
            headers=headers,
            json={
                "properties": {"dealname": deal_name, "dealstage": "appointmentscheduled", "pipeline": "default"},
                "associations": [
                    {
                        "to": {"id": contact_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
                    }
                ],
            },
        )
        if deal.status_code >= 400:
            raise DestinationError(f"HubSpot deal creation failed ({deal.status_code}): {deal.text[:200]}")
        return f"contact:{contact_id},deal:{deal.json()['id']}"


class GoogleDriveAdapter:
    """COA-279: create a named client folder and COA-307 invoice files in Drive."""

    provider = "google_drive"
    base_url = "https://www.googleapis.com"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def upload_file(
        self,
        access_token: str,
        *,
        filename: str,
        content_type: str | None,
        contents: bytes,
        parent_folder_id: str,
    ) -> dict[str, str | None]:
        metadata = {"name": filename, "parents": [parent_folder_id]}
        files = {
            "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
            "file": (filename, contents, content_type or "application/octet-stream"),
        }
        response = self.client.post(
            f"{self.base_url}/upload/drive/v3/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"uploadType": "multipart", "fields": "id,webViewLink"},
            files=files,
        )
        if response.status_code >= 400:
            raise DestinationError(f"Google Drive file upload failed ({response.status_code}): {response.text[:200]}")
        payload = response.json()
        return {"id": payload["id"], "webViewLink": payload.get("webViewLink")}

    def push(self, access_token: str, fields: dict[str, Any], context: dict[str, Any]) -> str:
        folder_name = str(fields.get("full_name") or fields.get("business_name") or "New client").strip()
        body: dict[str, Any] = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        parent_folder = os.environ.get("STS_GOOGLE_DRIVE_PARENT_FOLDER_ID", "").strip()
        if parent_folder:
            body["parents"] = [parent_folder]
        response = self.client.post(
            f"{self.base_url}/drive/v3/files",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        if response.status_code >= 400:
            raise DestinationError(f"Google Drive folder creation failed ({response.status_code}): {response.text[:200]}")
        return f"folder:{response.json()['id']}"


class PandaDocAdapter:
    """COA-281: generate the onboarding document from the configured template."""

    provider = "pandadoc"
    base_url = "https://api.pandadoc.com"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def push(self, access_token: str, fields: dict[str, Any], context: dict[str, Any]) -> str:
        template_id = os.environ.get("STS_PANDADOC_TEMPLATE_ID", "").strip()
        if not template_id:
            raise DestinationError("PandaDoc onboarding template is not configured (STS_PANDADOC_TEMPLATE_ID)")
        first_name, last_name = _full_name_parts(fields)
        response = self.client.post(
            f"{self.base_url}/public/v1/documents",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": f"Onboarding — {fields.get('full_name', 'New client')}",
                "template_uuid": template_id,
                "recipients": [
                    {
                        "email": fields.get("email", ""),
                        "first_name": first_name,
                        "last_name": last_name,
                        "role": "Client",
                    }
                ],
                "tokens": [
                    {"name": key, "value": str(value)} for key, value in fields.items() if value is not None
                ],
            },
        )
        if response.status_code >= 400:
            raise DestinationError(f"PandaDoc document creation failed ({response.status_code}): {response.text[:200]}")
        return f"document:{response.json()['id']}"


class XeroAdapter:
    """COA-285: create a Xero contact and a draft invoice.

    Requires the Xero tenant id, captured at connection time and stored on the
    connection's external_account_label.
    """

    provider = "xero"
    base_url = "https://api.xero.com"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def push(self, access_token: str, fields: dict[str, Any], context: dict[str, Any]) -> str:
        tenant_id = (context.get("connection") or {}).get("external_account_label") or ""
        if not tenant_id:
            raise DestinationError("Xero organisation (tenant id) is not configured on this connection")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-tenant-id": tenant_id,
            "Accept": "application/json",
        }
        contact = self.client.post(
            f"{self.base_url}/api.xro/2.0/Contacts",
            headers=headers,
            json={
                "Contacts": [
                    {
                        "Name": fields.get("full_name") or fields.get("business_name") or "New client",
                        "EmailAddress": fields.get("email", ""),
                        "Phones": [{"PhoneType": "MOBILE", "PhoneNumber": fields.get("phone", "")}],
                    }
                ]
            },
        )
        if contact.status_code >= 400:
            raise DestinationError(f"Xero contact creation failed ({contact.status_code}): {contact.text[:200]}")
        contact_id = contact.json()["Contacts"][0]["ContactID"]

        invoice = self.client.post(
            f"{self.base_url}/api.xro/2.0/Invoices",
            headers=headers,
            json={
                "Invoices": [
                    {
                        "Type": "ACCREC",
                        "Status": "DRAFT",
                        "Contact": {"ContactID": contact_id},
                        "LineItems": [
                            {
                                "Description": fields.get("services_needed", "Professional services engagement"),
                                "Quantity": 1.0,
                                "UnitAmount": float(fields.get("engagement_fee", 0) or 0),
                                "AccountCode": os.environ.get("STS_XERO_SALES_ACCOUNT_CODE", "200"),
                            }
                        ],
                    }
                ]
            },
        )
        if invoice.status_code >= 400:
            raise DestinationError(f"Xero invoice creation failed ({invoice.status_code}): {invoice.text[:200]}")
        invoice_id = invoice.json()["Invoices"][0]["InvoiceID"]
        return f"contact:{contact_id},invoice:{invoice_id}"


def register_default_adapters() -> None:
    from app.destinations import register_adapter

    register_adapter(HubSpotAdapter())
    register_adapter(GoogleDriveAdapter())
    register_adapter(PandaDocAdapter())
    register_adapter(XeroAdapter())
