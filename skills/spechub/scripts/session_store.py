#!/usr/bin/env python3
"""SpecHub session file: format plus read/write helpers.

The session file caches a scoped/short-lived capability token for multi-round calls.
It is created and removed only via session.py. The file is a single record:

  {"access_token": "...", "expires_at": "...Z", "scope": "agent:chat"}

Lightweight lstat symlink / regular-file checks guard against a symlink
redirecting a token read or write.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from common import SpecHubError
from common import now_utc
from common import parse_utc

SESSION_FILENAME = "session.json"


def _assert_safe(path: Path) -> None:
    """Reject a session path that exists as a symlink or non-regular file."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(st.st_mode):
        raise SpecHubError(f"Refusing to use symlinked session file: {path}")
    if not stat.S_ISREG(st.st_mode):
        raise SpecHubError(f"Session path is not a regular file: {path}")


def write_session(path: Path, session: dict[str, Any]) -> None:
    """Create a 0600 session file, failing if one already exists.

    Exclusive create (O_CREAT|O_EXCL) is the concurrency control: two parallel
    `start` calls cannot both create the same file.
    """
    _assert_safe(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SpecHubError(
            f"A SpecHub session already exists at {path}. Run 'session.py end' first."
        ) from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(session, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_session(path: Path) -> dict[str, Any]:
    """Read a session record, rejecting symlinked/non-regular files."""
    _assert_safe(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
    except FileNotFoundError:
        raise SpecHubError(
            f"No SpecHub session at {path}. Run 'session.py start' first."
        ) from None
    except json.JSONDecodeError as err:
        raise SpecHubError(f"SpecHub session file is malformed: {err}") from None
    if not isinstance(parsed, dict):
        raise SpecHubError("SpecHub session file is malformed: expected a JSON object")
    return parsed


def is_expired(session: dict[str, Any]) -> bool:
    """Return True if the session is missing/invalid/expired (safe to discard)."""
    expires_at = session.get("expires_at")
    if not isinstance(expires_at, str):
        return True
    try:
        return parse_utc(expires_at) <= now_utc()
    except ValueError:
        return True


def session_token(session: dict[str, Any]) -> str:
    """Return the access token from a session, raising if missing or expired."""
    token = session.get("access_token")
    if not isinstance(token, str) or not token:
        raise SpecHubError(
            "SpecHub session has no access_token. Run 'session.py start' again."
        )
    if is_expired(session):
        raise SpecHubError("SpecHub session has expired. Run 'session.py start' again.")
    return token
