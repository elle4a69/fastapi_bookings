"""Safe Asset Importer for Approved Intent Examples.

Imports approved procedural conversation style examples into MessageStyleExample.
Guarantees:
- Cryptographic SHA-256 verification of the source dataset.
- Streamed JSONL ingestion with fail-closed safety classification.
- Idempotency via deterministic (intent, client_message) hashing.
- Complete isolation: imported examples NEVER enter CuratedMemory (factual store).
- Support for platform-default or tenant/provider-scoped imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.curated_memory import CuratedMemory
from app.models.message_style_example import MessageStyleExample, compute_style_example_hash
from app.services.knowledge.classifier import (
    SafetyDecision,
    classify_style_example,
)

logger = logging.getLogger(__name__)

DEFAULT_APPROVED_EXAMPLES_PATH = r"F:\Projects\assistant-ui\backend\data\approved_intent_examples.jsonl"
EXPECTED_SHA256 = "F0C80D93EAB23D7772B7454C81F38027D23D1C6D6E88D4F1EF1314E5B54303A6"
EXPECTED_LINE_COUNT = 180


@dataclass
class ImportReport:
    """Detailed summary of the asset import process."""
    total_scanned: int = 0
    imported_count: int = 0
    skipped_duplicate: int = 0
    rejected_count: int = 0
    sha256_verified: bool = False
    source_path: str = ""
    computed_sha256: str = ""
    errors: List[str] = field(default_factory=list)


def compute_file_sha256(file_path: str) -> str:
    """Compute the uppercase hex SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def verify_asset_file(
    file_path: str = DEFAULT_APPROVED_EXAMPLES_PATH,
    expected_hash: str = EXPECTED_SHA256,
) -> Tuple[bool, str, str]:
    """Verify that the target asset exists and matches the expected SHA-256 hash.

    Returns:
        (is_valid, computed_hash, error_message)
    """
    if not os.path.exists(file_path):
        msg = f"Asset file not found at path: {file_path}"
        logger.error(msg)
        return False, "", msg

    computed = compute_file_sha256(file_path)
    if computed != expected_hash.upper():
        msg = (
            f"SHA-256 fingerprint mismatch for asset file: '{file_path}'. "
            f"Expected {expected_hash.upper()}, got {computed}"
        )
        logger.error(msg)
        return False, computed, msg

    return True, computed, ""


def import_approved_style_examples(
    db: Session,
    file_path: str = DEFAULT_APPROVED_EXAMPLES_PATH,
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    enforce_sha: bool = True,
    expected_hash: str = EXPECTED_SHA256,
) -> ImportReport:
    """Import approved intent examples safely and idempotently into MessageStyleExample.

    Args:
        db: Active SQLAlchemy database session.
        file_path: Path to the JSONL dataset.
        tenant_id: Optional tenant ID (None for platform-wide defaults).
        provider_id: Optional provider ID (None for tenant-wide or platform defaults).
        enforce_sha: Whether to halt on SHA-256 mismatch.
        expected_hash: Expected SHA-256 digest.

    Returns:
        ImportReport containing counts and verification status.

    Raises:
        ValueError: If enforce_sha is True and the file does not match expected SHA-256.
        AssertionError: If CuratedMemory table is mutated during import.
    """
    report = ImportReport(source_path=file_path)

    # 1. Cryptographic SHA-256 Fingerprint Verification
    is_valid, computed_hash, err = verify_asset_file(file_path, expected_hash)
    report.computed_sha256 = computed_hash
    if not is_valid:
        report.errors.append(err)
        if enforce_sha:
            raise ValueError(f"Asset importer halted due to SHA-256 verification failure: {err}")
        return report

    report.sha256_verified = True

    # 2. Invariant Baseline: CuratedMemory must not be touched
    initial_curated_count = db.query(CuratedMemory).count()

    # Ensure table exists in current database schema
    MessageStyleExample.__table__.create(bind=db.bind, checkfirst=True)

    # 3. Stream JSONL line by line
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            report.total_scanned += 1
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                msg = f"Line {line_num}: Invalid JSON - {e}"
                logger.warning(msg)
                report.rejected_count += 1
                report.errors.append(msg)
                continue

            primary_intent = (
                data.get("primary_intent")
                or data.get("intent")
                or "general_conversation"
            )
            client_msg = (data.get("incoming") or "").strip()
            assistant_reply = (data.get("reply") or "").strip()
            placeholders = data.get("placeholders", [])
            intents = data.get("intents", [primary_intent])
            category = data.get("category", "procedural")

            # 4. Pass pair through Safety Classifier
            classification = classify_style_example(
                client_msg,
                assistant_reply,
                is_approved_source=True,
            )
            if not classification.is_safe or classification.decision != SafetyDecision.ACCEPT:
                msg = f"Line {line_num} rejected by classifier: {classification.reason}"
                logger.warning(msg)
                report.rejected_count += 1
                report.errors.append(msg)
                continue

            # 5. Deterministic Idempotency Match on (intent, client_message)
            content_hash = compute_style_example_hash(primary_intent, client_msg)

            # Check if this example already exists in the requested scope
            query = db.query(MessageStyleExample).filter(
                MessageStyleExample.content_hash == content_hash,
            )
            if tenant_id is None:
                query = query.filter(MessageStyleExample.tenant_id.is_(None))
            else:
                query = query.filter(MessageStyleExample.tenant_id == tenant_id)

            if provider_id is None:
                query = query.filter(MessageStyleExample.provider_id.is_(None))
            else:
                query = query.filter(MessageStyleExample.provider_id == provider_id)

            existing = query.first()
            if existing:
                report.skipped_duplicate += 1
                continue

            # Build tag list
            tags = list(intents)
            for p in placeholders:
                if p not in tags:
                    tags.append(p)

            # 6. Store into MessageStyleExample
            example = MessageStyleExample(
                tenant_id=tenant_id,
                provider_id=provider_id,
                intent=primary_intent,
                client_message=client_msg,
                assistant_reply=assistant_reply,
                category=category,
                tags=tags,
                is_approved=True,
                is_active=True,
                source="assistant_ui_import",
                content_hash=content_hash,
            )
            db.add(example)
            report.imported_count += 1

    # Commit all imported examples
    db.commit()

    # 7. Invariant Verification: Prove imported examples NEVER entered CuratedMemory
    final_curated_count = db.query(CuratedMemory).count()
    if final_curated_count != initial_curated_count:
        raise AssertionError(
            f"Invariant violation: CuratedMemory count changed from {initial_curated_count} "
            f"to {final_curated_count} during procedural example import!"
        )

    logger.info(
        f"Approved examples import complete: scanned={report.total_scanned}, "
        f"imported={report.imported_count}, skipped={report.skipped_duplicate}, "
        f"rejected={report.rejected_count}"
    )
    return report
