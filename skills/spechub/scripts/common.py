#!/usr/bin/env python3
"""Generic helpers for the SpecHub skill scripts.

Stdlib only by design: these scripts run in local agent environments without
pip installs.

Security: bearer token goes only into an in-process Authorization header -
never argv, never printed, never logged.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 120
SPECHUB_DIRNAME = ".spechub"


class SpecHubError(Exception):
    """Expected script-level failure with a user-safe message."""


class SpecHubHTTPError(SpecHubError):
    """HTTP failure from SpecHub with the response status preserved."""

    def __init__(self, status: int, message: str) -> None:
        """Create an HTTP error whose message is safe to display."""
        super().__init__(message)
        self.status = status


# --- Validation -------------------------------------------------------------


def is_uuid(value: str) -> bool:
    """Return True if value parses as a UUID."""
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


# --- HTTP -------------------------------------------------------------------


def redact(text: str, token: str | None = None) -> str:
    """Remove bearer-token material from text before printing errors."""
    if token:
        text = text.replace(token, "[REDACTED_ACCESS_TOKEN]")
    return re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)


def parse_error_body(raw: bytes) -> str:
    """Extract a concise API error message from a response body."""
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(body, dict):
        for key in ("error_description", "detail", "error", "message"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return text


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Send an HTTP request and parse a JSON-object response.

    The bearer token, when provided, is placed only in the in-process
    Authorization header.
    """
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        detail = parse_error_body(err.read())
        message = detail or err.reason or "HTTP request failed"
        raise SpecHubHTTPError(
            err.code, f"{method} {url} failed ({err.code}): {message}"
        ) from None
    except urllib.error.URLError as err:
        raise SpecHubError(f"{method} {url} failed: {err.reason}") from None

    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as err:
        raise SpecHubError(f"{method} {url} returned invalid JSON: {err}") from None
    if not isinstance(parsed, dict):
        raise SpecHubError(f"{method} {url} returned JSON that is not an object")
    return parsed


def request_bytes(
    method: str,
    url: str,
    *,
    token: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Send an authenticated HTTP request and return the raw response body."""
    headers = {
        "Accept": "text/markdown, text/plain, application/octet-stream",
        "Authorization": "Bearer " + token,
    }
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        detail = parse_error_body(err.read())
        message = detail or err.reason or "HTTP request failed"
        raise SpecHubHTTPError(
            err.code, f"{method} {url} failed ({err.code}): {message}"
        ) from None
    except urllib.error.URLError as err:
        raise SpecHubError(f"{method} {url} failed: {err.reason}") from None


# --- Time -------------------------------------------------------------------


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def parse_utc(value: str) -> datetime:
    """Parse an ISO timestamp and normalize it to UTC."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized).astimezone(UTC)


def format_utc(value: datetime) -> str:
    """Format a datetime as an ISO UTC timestamp with a trailing `Z`."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


# --- Workspace + .spechub directory ----------------------------------------


def find_workspace_root(start: Path | None = None) -> Path:
    """Return the nearest Git repo root, or the current directory if none."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def spechub_dir(root: Path | None = None) -> Path:
    """Return the `.spechub/` path for the workspace (without creating it)."""
    return find_workspace_root(root) / SPECHUB_DIRNAME


def ensure_spechub_dir(root: Path | None = None) -> Path:
    """Create `.spechub/` at the workspace root and gitignore it.

    Shared by downloaded specs and the session file.
    """
    workspace = find_workspace_root(root)
    directory = workspace / SPECHUB_DIRNAME
    try:
        st = os.lstat(directory)
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(st.st_mode):
            raise SpecHubError(
                f"Refusing to use symlinked .spechub directory: {directory}"
            )
        if not stat.S_ISDIR(st.st_mode):
            raise SpecHubError(
                f".spechub path exists but is not a directory: {directory}"
            )
    directory.mkdir(mode=0o700, exist_ok=True)
    if (workspace / ".git").exists():
        ensure_gitignored(workspace)
    return directory


def ensure_gitignored(workspace: Path) -> None:
    """Append `.spechub/` to a repo's `.gitignore` if it is not present."""
    gitignore = workspace / ".gitignore"
    existing = ""
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8", errors="replace")
    entries = {line.strip() for line in existing.splitlines()}
    if ".spechub/" in entries or ".spechub" in entries:
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with gitignore.open("a", encoding="utf-8") as handle:
        handle.write(prefix + ".spechub/\n")


# --- Output -----------------------------------------------------------------


def print_json(data: dict[str, Any]) -> None:
    """Print a deterministic JSON object."""
    print(json.dumps(data, indent=2, sort_keys=True))


def fail(message: str, *, token: str | None = None) -> int:
    """Print a redacted error message to stderr and return failure status."""
    print(redact(message, token), file=sys.stderr)
    return 1
