#!/usr/bin/env python3
"""Download assembled SpecHub specs into the local workspace.

Stateless. The approval code is exchanged in memory, the specs are downloaded
to `.spechub/`, and the token is discarded on exit.
"""

from __future__ import annotations

import argparse

from api import download_specs
from api import exchange_device_code
from common import SpecHubError
from common import ensure_spechub_dir
from common import fail
from common import is_uuid
from common import print_json


def validate_args(args: argparse.Namespace) -> None:
    """Validate the opaque specs-repo reference and the stage UUID."""
    parts = args.specs_repo.split("/")
    if len(parts) != 2 or not all(is_uuid(part) for part in parts):
        raise SpecHubError(
            "Specs Repo must be the opaque SpecHub value in the form {uuid}/{uuid}."
        )
    if not is_uuid(args.stage_id):
        raise SpecHubError("Stage ID must be a UUID.")


def run(args: argparse.Namespace) -> int:
    """Exchange the code, download specs to `.spechub/`, and print the path."""
    validate_args(args)
    token = exchange_device_code(args.approval_code, timeout=args.timeout)[
        "access_token"
    ]
    content = download_specs(
        token, args.specs_repo, args.stage_id, timeout=args.timeout
    )

    destination = ensure_spechub_dir() / f"specs-{args.stage_id[:8]}.md"
    destination.write_bytes(content)

    print_json({"download_path": str(destination), "bytes": len(content)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(description="Download assembled SpecHub specs.")
    parser.add_argument(
        "--approval-code",
        required=True,
        help="Single-use approval code for this download.",
    )
    parser.add_argument(
        "--specs-repo",
        required=True,
        help="Opaque SpecHub specs repo reference: {uuid}/{uuid}.",
    )
    parser.add_argument("--stage-id", required=True, help="Stage UUID.")
    parser.add_argument(
        "--timeout", type=int, default=30, help="HTTP timeout in seconds."
    )
    return parser


def main() -> int:
    """Parse CLI arguments and run the download."""
    args = build_parser().parse_args()
    try:
        return run(args)
    except SpecHubError as err:
        return fail(str(err))


if __name__ == "__main__":
    raise SystemExit(main())
