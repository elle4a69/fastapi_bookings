"""Canonical payload fingerprints for tenant-scoped idempotent requests."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class IdempotencyKeyConflictError(RuntimeError):
    """Raised when a request key is reused with a different canonical payload."""


def payload_hash(payload: dict[str, Any]) -> str:
    """Hash canonical JSON without retaining a second copy of request content."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_matching_payload(*, stored_hash: str | None, incoming_hash: str) -> None:
    """Fail closed if historical key metadata is absent or does not match."""
    if not stored_hash or stored_hash != incoming_hash:
        raise IdempotencyKeyConflictError("The request key has already been used with a different payload.")
