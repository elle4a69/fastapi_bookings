"""Offline-only JSON CLI for persisted platform-owner authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.db.database import SessionLocal
from app.services.auth.platform_owner_authority import (
    MAX_INT32_ID,
    PlatformOwnerAuthorityError,
    REASON_CODES,
    get_platform_owner_status,
    preview_platform_owner_change,
    set_platform_owner,
)


EXIT_INVALID = 2
EXIT_NOT_FOUND = 3
EXIT_LAST_OWNER = 4
EXIT_TRANSACTION = 5


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        _write_error("invalid_arguments", "unknown")
        raise SystemExit(EXIT_INVALID)


def _positive_int32(value: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a decimal integer") from exc
    if not 1 <= parsed <= MAX_INT32_ID:
        raise argparse.ArgumentTypeError("must be a positive 32-bit integer")
    return parsed


def _write_json(payload: dict[str, object], *, stream) -> None:
    stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _write_error(code: str, operation: str) -> None:
    _write_json({"code": code, "ok": False, "operation": operation}, stream=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="manage_platform_owner.py")
    commands = parser.add_subparsers(dest="operation", required=True)

    status_parser = commands.add_parser("status")
    status_parser.add_argument("--tenant-id", required=True, type=_positive_int32)
    status_parser.add_argument("--user-id", required=True, type=_positive_int32)

    for operation in ("grant", "revoke"):
        command = commands.add_parser(operation)
        command.add_argument("--tenant-id", required=True, type=_positive_int32)
        command.add_argument("--user-id", required=True, type=_positive_int32)
        command.add_argument("--reason-code", required=True, choices=sorted(REASON_CODES))
        command.add_argument("--change-ref")
        command.add_argument("--apply", action="store_true")
        command.add_argument("--confirm")
    return parser


def _success_payload(operation: str, result) -> dict[str, object]:
    return {
        "active": result.active,
        "applied": result.applied,
        "changed": result.changed,
        "is_platform_owner": result.is_platform_owner,
        "ok": True,
        "operation": operation,
        "tenant_id": result.tenant_id,
        "user_id": result.user_id,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    operation: str = args.operation

    if operation in {"grant", "revoke"}:
        if args.change_ref is not None:
            from app.services.auth.platform_owner_authority import _CHANGE_REF_RE

            if _CHANGE_REF_RE.fullmatch(args.change_ref) is None:
                _write_error("invalid_change_ref", operation)
                return EXIT_INVALID
        if args.apply:
            verb = operation.upper()
            expected = f"{verb} PLATFORM OWNER {args.tenant_id}:{args.user_id}"
            if args.confirm != expected:
                _write_error("confirmation_mismatch", operation)
                return EXIT_INVALID

    try:
        with SessionLocal() as session:
            if operation == "status":
                result = get_platform_owner_status(
                    session, tenant_id=args.tenant_id, user_id=args.user_id
                )
            elif not args.apply:
                result = preview_platform_owner_change(
                    session,
                    tenant_id=args.tenant_id,
                    user_id=args.user_id,
                    grant=operation == "grant",
                )
            else:
                result = set_platform_owner(
                    session,
                    tenant_id=args.tenant_id,
                    user_id=args.user_id,
                    grant=operation == "grant",
                    reason_code=args.reason_code,
                    change_ref=args.change_ref,
                )
    except PlatformOwnerAuthorityError as exc:
        _write_error(exc.code, operation)
        if exc.code == "target_not_found":
            return EXIT_NOT_FOUND
        if exc.code == "last_active_platform_owner":
            return EXIT_LAST_OWNER
        if exc.code.startswith("invalid_") or exc.code == "transaction_already_active":
            return EXIT_INVALID
        return EXIT_TRANSACTION
    except Exception:
        _write_error("transaction_failed", operation)
        return EXIT_TRANSACTION

    _write_json(_success_payload(operation, result), stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
