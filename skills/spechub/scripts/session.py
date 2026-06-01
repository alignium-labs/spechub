#!/usr/bin/env python3
"""Manage a reusable SpecHub chat session for multi-round conversations.

Lifecycle:
  session.py start --approval-code CODE      # exchange + persist; prints the path
  agent_chat.py --session-file PATH ...      # one or more rounds
  session.py end --session-file PATH         # delete the session file

One-shot work (a single question, or sync_specs) does not need this — those
exchange the approval code in memory and never write a file. The session-file
format and its read/write helpers live in session_store.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from api import exchange_device_code
from common import SpecHubError
from common import ensure_spechub_dir
from common import fail
from common import print_json
from session_store import SESSION_FILENAME
from session_store import is_expired
from session_store import read_session
from session_store import write_session


def start(args: argparse.Namespace) -> int:
    """Exchange an approval code and persist a private session file."""
    if args.session_dir:
        directory = Path(args.session_dir).expanduser()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    else:
        directory = ensure_spechub_dir()
    path = directory / SESSION_FILENAME

    # Replace an existing session only if it has already expired; never clobber
    # a live one (the user should end it explicitly).
    if path.exists():
        if is_expired(read_session(path)):
            path.unlink()
        else:
            raise SpecHubError(
                f"A SpecHub session is already active at {path}. Run 'session.py end' first."
            )

    session = exchange_device_code(args.approval_code, timeout=args.timeout)
    write_session(path, session)
    print_json(
        {
            "session_file": str(path),
            "expires_at": session["expires_at"],
            "scope": session["scope"],
        }
    )
    return 0


def end(args: argparse.Namespace) -> int:
    """Delete a valid SpecHub session file."""
    path = Path(args.session_file).expanduser()
    session = read_session(path)
    if not isinstance(session.get("access_token"), str) or not isinstance(
        session.get("expires_at"), str
    ):
        raise SpecHubError(f"Not a SpecHub session file: {path}")
    path.unlink()
    print_json({"ended": str(path)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the session-management command-line interface."""
    parser = argparse.ArgumentParser(
        description="Manage a reusable SpecHub chat session."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser(
        "start", help="Exchange an approval code and persist a session."
    )
    start_parser.add_argument(
        "--approval-code", required=True, help="Single-use approval code."
    )
    start_parser.add_argument("--session-dir", help="Directory for the session file.")
    start_parser.add_argument(
        "--timeout", type=int, default=30, help="HTTP timeout in seconds."
    )
    start_parser.set_defaults(func=start)

    end_parser = subparsers.add_parser("end", help="Delete the session file.")
    end_parser.add_argument(
        "--session-file", required=True, help="Session file path (printed by 'start')."
    )
    end_parser.set_defaults(func=end)
    return parser


def main() -> int:
    """Parse CLI arguments and run the selected subcommand."""
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except SpecHubError as err:
        return fail(str(err))


if __name__ == "__main__":
    raise SystemExit(main())
