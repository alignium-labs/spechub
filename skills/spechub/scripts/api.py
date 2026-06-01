#!/usr/bin/env python3
"""Encapsulated SpecHub API calls.

Each function maps one-to-one to a SpecHub endpoint.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from common import DEFAULT_TIMEOUT_SECONDS
from common import SpecHubError
from common import format_utc
from common import now_utc
from common import request_bytes
from common import request_json

# Production is the only target — hardcoded on purpose. Users never choose a URL,
# and there is no env var or flag to point the scripts (and a live token) at a
# different host.
API_BASE_URL = "https://api.spechub.ai"
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


def api_url(path: str) -> str:
    """Build a full SpecHub API URL from a relative path."""
    if not path.startswith("/"):
        path = "/" + path
    return API_BASE_URL + path


def exchange_device_code(
    approval_code: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> dict[str, Any]:
    """Exchange a single-use approval code for a session record.

    The returned record — `{access_token, expires_at, scope}` — is exactly what
    `session.py` persists for sessioned chat.
    """
    resp = request_json(
        "POST",
        api_url("/oauth/token"),
        payload={"grant_type": DEVICE_CODE_GRANT, "device_code": approval_code.strip()},
        timeout=timeout,
    )
    token = resp.get("access_token")
    if not isinstance(token, str) or not token:
        raise SpecHubError("Token exchange did not return an access_token.")
    token_type = str(resp.get("token_type") or "Bearer")
    if token_type.lower() != "bearer":
        raise SpecHubError(f"Unsupported token_type from SpecHub: {token_type}")
    expires_in = resp.get("expires_in")
    if not isinstance(expires_in, int) or expires_in <= 0:
        raise SpecHubError("Token exchange did not return a positive expires_in.")
    return {
        "access_token": token,
        "expires_at": format_utc(now_utc() + timedelta(seconds=expires_in)),
        "scope": resp.get("scope") or "",
    }


def download_specs(
    token: str,
    specs_repo: str,
    stage_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Download a stage's assembled spec markdown."""
    return request_bytes(
        "GET",
        api_url(f"/spec-access/specs/{specs_repo}/stages/{stage_id}/content"),
        token=token,
        timeout=timeout,
    )


def send_agent_message(
    token: str,
    *,
    project_id: str,
    message: str,
    model: str,
    stage_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Send one message to the planning agent and return its reply."""
    body: dict[str, Any] = {
        "project_id": project_id,
        "message": message,
        "model_class": model,
    }
    if stage_id:
        body["stage_id"] = stage_id
    return request_json(
        "POST", api_url("/agent/agent-chat"), payload=body, token=token, timeout=timeout
    )
