#!/usr/bin/env python3
"""Send one message to a SpecHub planning agent.

Reads the bearer token from a session file created by `session.py start`, so
every chat belongs to an explicit session and can run more rounds. Writes
nothing itself.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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


def run(args: argparse.Namespace) -> int:
    """Read the session token, send one message, and print the reply."""
    token = session_token(read_session(Path(args.session_file).expanduser()))
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
    parser.add_argument(
        "--session-file",
        required=True,
        help="Session file from 'session.py start'.",
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
