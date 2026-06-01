#!/usr/bin/env python3
"""Send one message to a SpecHub planning agent.

Stateless. Two mutually-exclusive credential inputs:
  --approval-code   one-shot: exchange in memory, send, exit (the default).
  --session-file    reuse a session started by session.py for multi-round chat.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from api import exchange_device_code
from api import send_agent_message
from common import SpecHubError
from common import fail
from common import print_json
from session_store import read_session
from session_store import session_token


def read_message(args: argparse.Namespace) -> str:
    """Read the outgoing chat message from argv or stdin."""
    message = sys.stdin.read() if args.message_stdin else args.message_string
    message = message.strip()
    if not message:
        raise SpecHubError("Message is empty.")
    return message


def resolve_token(args: argparse.Namespace) -> str:
    """Return the bearer token from either a session file or a fresh exchange."""
    if args.session_file:
        return session_token(read_session(Path(args.session_file).expanduser()))
    return exchange_device_code(args.approval_code, timeout=args.timeout)[
        "access_token"
    ]


def run(args: argparse.Namespace) -> int:
    """Resolve the token, send one message, and print the reply."""
    token = resolve_token(args)
    reply = send_agent_message(
        token,
        project_id=args.project_id,
        message=read_message(args),
        model=args.model,
        stage_id=args.stage_id,
        timeout=args.timeout,
    )
    print_json(reply)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Send a message to a SpecHub planning agent."
    )
    parser.add_argument("--project-id", required=True, help="Project UUID.")
    parser.add_argument(
        "--stage-id", help="Optional stage UUID for a stage-specific planning agent."
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=("fast", "balanced", "frontier"),
        help="Model class.",
    )

    credential = parser.add_mutually_exclusive_group(required=True)
    credential.add_argument(
        "--approval-code", help="Single-use approval code (one-shot message)."
    )
    credential.add_argument(
        "--session-file",
        help="Session file from 'session.py start' (multi-round chat).",
    )

    message = parser.add_mutually_exclusive_group(required=True)
    message.add_argument("--message-string", help="Message body to send.")
    message.add_argument(
        "--message-stdin", action="store_true", help="Read the message body from stdin."
    )

    parser.add_argument(
        "--timeout", type=int, default=120, help="HTTP timeout in seconds."
    )
    return parser


def main() -> int:
    """Parse CLI arguments and send the message."""
    args = build_parser().parse_args()
    try:
        return run(args)
    except SpecHubError as err:
        return fail(str(err))


if __name__ == "__main__":
    raise SystemExit(main())
