import argparse
import asyncio
import json
import re
from typing import Any

from pymongo import AsyncMongoClient

from app.core.config import settings
from app.services.url_service import URLShortener


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_short_code(short_url: str) -> str:
    normalized = str(short_url or "").rstrip("/")
    return normalized.split("/")[-1] if normalized else ""


def _select_long_url_canonical(docs: list[dict]) -> dict:
    def created_at(doc: dict) -> int:
        return _safe_int(doc.get("created_at"), 2**63 - 1)

    def access_count(doc: dict) -> int:
        return _safe_int(doc.get("access_count"), 0)

    return min(docs, key=lambda d: (created_at(d), -access_count(d), str(d.get("_id"))))


def _select_short_code_canonical(docs: list[dict]) -> dict:
    def created_at(doc: dict) -> int:
        return _safe_int(doc.get("created_at"), 2**63 - 1)

    def access_count(doc: dict) -> int:
        return _safe_int(doc.get("access_count"), 0)

    return max(docs, key=lambda d: (access_count(d), -created_at(d), str(d.get("_id"))))


async def _find_duplicates(collection, field: str) -> list[dict]:
    pipeline = [
        {
            "$group": {
                "_id": f"${field}",
                "count": {"$sum": 1},
                "docs": {
                    "$push": {
                        "_id": "$_id",
                        "long_url": "$long_url",
                        "short_url": "$short_url",
                        "short_code": "$short_code",
                        "created_at": "$created_at",
                        "access_count": "$access_count",
                    }
                },
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]
    cursor = await collection.aggregate(pipeline)
    return await cursor.to_list(length=None)


async def _find_short_code_inconsistencies(collection) -> list[dict]:
    issues = []
    cursor = collection.find({}, {"short_url": 1, "short_code": 1})
    async for doc in cursor:
        expected = _extract_short_code(doc.get("short_url", ""))
        if expected and doc.get("short_code") != expected:
            issues.append(
                {
                    "_id": doc["_id"],
                    "short_url": doc.get("short_url"),
                    "current_short_code": doc.get("short_code"),
                    "expected_short_code": expected,
                }
            )
    return issues


async def _short_code_exists(collection, short_code: str) -> bool:
    suffix_pattern = f"/{re.escape(short_code)}$"
    doc = await collection.find_one(
        {
            "$or": [
                {"short_code": short_code},
                {"short_url": {"$regex": suffix_pattern}},
            ]
        },
        {"_id": 1},
    )
    return doc is not None


async def _generate_unique_short_url(
    collection,
    shortener: URLShortener,
    max_attempts: int,
) -> tuple[str, str]:
    for _ in range(max_attempts):
        short_code = shortener.generate_short_code()
        if not await _short_code_exists(collection, short_code):
            return shortener.build_short_url(short_code), short_code
    raise RuntimeError("Failed to generate a unique short code after retries.")


async def _rebuild_short_code_index(collection) -> bool:
    index_information = await collection.index_information()
    for name, definition in index_information.items():
        if definition.get("key") != [("short_code", 1)]:
            continue
        if definition.get("unique") is True:
            return False
        await collection.drop_index(name)
    await collection.create_index("short_code", unique=True)
    return True


async def _synchronize_short_codes(collection) -> int:
    synchronized = 0
    code_issues = await _find_short_code_inconsistencies(collection)
    for issue in code_issues:
        result = await collection.update_one(
            {"_id": issue["_id"]},
            {"$set": {"short_code": issue["expected_short_code"]}},
        )
        synchronized += result.modified_count
    return synchronized


async def _reassign_duplicate_short_codes(
    collection,
    shortener: URLShortener,
    max_attempts: int,
) -> int:
    reassigned = 0
    duplicate_groups = await _find_duplicates(collection, "short_code")
    for group in duplicate_groups:
        docs = group["docs"]
        canonical = _select_short_code_canonical(docs)
        for doc in docs:
            if doc["_id"] == canonical["_id"]:
                continue
            new_short_url, new_short_code = await _generate_unique_short_url(
                collection,
                shortener,
                max_attempts,
            )
            result = await collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "short_url": new_short_url,
                        "short_code": new_short_code,
                    }
                },
            )
            reassigned += result.modified_count
    return reassigned


async def _build_report(collection) -> dict[str, Any]:
    long_dups = await _find_duplicates(collection, "long_url")
    short_url_dups = await _find_duplicates(collection, "short_url")
    short_code_dups = await _find_duplicates(collection, "short_code")
    code_issues = await _find_short_code_inconsistencies(collection)
    return {
        "long_url_duplicates": long_dups,
        "short_url_duplicates": short_url_dups,
        "short_code_duplicates": short_code_dups,
        "short_code_inconsistencies": code_issues,
        "actions": {
            "long_url_groups": len(long_dups),
            "short_url_groups": len(short_url_dups),
            "short_code_groups": len(short_code_dups),
            "long_url_deleted": 0,
            "short_code_synchronized": 0,
            "short_code_reassigned": 0,
            "short_code_index_rebuilt": False,
        },
    }


async def _dedupe_long_urls(collection, duplicate_groups: list[dict]) -> int:
    deleted_count = 0
    for group in duplicate_groups:
        docs = group["docs"]
        canonical = _select_long_url_canonical(docs)
        total_access = sum(_safe_int(doc.get("access_count"), 0) for doc in docs)
        min_created = min(
            (_safe_int(doc.get("created_at"), 2**63 - 1) for doc in docs),
            default=_safe_int(canonical.get("created_at"), 2**63 - 1),
        )
        update_fields = {}
        if total_access != _safe_int(canonical.get("access_count"), 0):
            update_fields["access_count"] = total_access
        if min_created != _safe_int(canonical.get("created_at"), 2**63 - 1):
            update_fields["created_at"] = min_created
        if update_fields:
            await collection.update_one(
                {"_id": canonical["_id"]},
                {"$set": update_fields},
            )
        delete_ids = [doc["_id"] for doc in docs if doc["_id"] != canonical["_id"]]
        if delete_ids:
            result = await collection.delete_many({"_id": {"$in": delete_ids}})
            deleted_count += result.deleted_count
    return deleted_count


async def _validate_invariants(collection) -> dict[str, int]:
    return {
        "long_url_duplicate_groups": len(
            await _find_duplicates(collection, "long_url")
        ),
        "short_url_duplicate_groups": len(
            await _find_duplicates(collection, "short_url")
        ),
        "short_code_duplicate_groups": len(
            await _find_duplicates(collection, "short_code")
        ),
        "short_code_inconsistencies": len(
            await _find_short_code_inconsistencies(collection)
        ),
    }


async def _apply_cleanup(
    collection,
    report: dict[str, Any],
    shortener: URLShortener,
    max_attempts: int,
    rebuild_indexes: bool,
) -> None:
    actions = report["actions"]
    actions["long_url_deleted"] = await _dedupe_long_urls(
        collection,
        report["long_url_duplicates"],
    )
    actions["short_code_synchronized"] = await _synchronize_short_codes(collection)
    actions["short_code_reassigned"] = await _reassign_duplicate_short_codes(
        collection,
        shortener,
        max_attempts,
    )
    report["validation"] = await _validate_invariants(collection)
    if not rebuild_indexes:
        return
    if any(report["validation"].values()):
        raise RuntimeError(
            "Data validation failed; the short_code index was not rebuilt."
        )
    actions["short_code_index_rebuilt"] = await _rebuild_short_code_index(collection)


def _normalize_report(obj: Any):
    if isinstance(obj, dict):
        return {key: _normalize_report(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_normalize_report(value) for value in obj]
    if hasattr(obj, "__str__") and str(type(obj)).endswith("ObjectId'>"):
        return str(obj)
    return obj


def _export_report(report: dict[str, Any], export_path: str) -> None:
    with open(export_path, "w", encoding="utf-8") as report_file:
        json.dump(
            _normalize_report(report),
            report_file,
            ensure_ascii=False,
            indent=2,
        )


async def scan_and_dedupe(
    apply_changes: bool,
    export_path: str | None,
    max_attempts: int,
    rebuild_indexes: bool = False,
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")
    if rebuild_indexes and not apply_changes:
        raise ValueError("--rebuild-indexes requires --apply.")

    client = AsyncMongoClient(
        settings.database_url,
        serverSelectionTimeoutMS=settings.database_server_selection_timeout_ms,
    )
    try:
        db = client[settings.database_name]
        collection = db[settings.database_collection_name]
        shortener = URLShortener(base_url=settings.short_base_url)
        report = await _build_report(collection)
        if apply_changes:
            await _apply_cleanup(
                collection,
                report,
                shortener,
                max_attempts,
                rebuild_indexes,
            )
        if export_path:
            _export_report(report, export_path)
        return report
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="Scan and dedupe URL records.")
    parser.add_argument(
        "--apply", action="store_true", help="Apply changes to the database."
    )
    parser.add_argument(
        "--export", type=str, default=None, help="Export report to JSON file."
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=10,
        help="Max attempts for short code regeneration.",
    )
    parser.add_argument(
        "--rebuild-indexes",
        action="store_true",
        help="Replace a legacy non-unique short_code index after validation.",
    )
    args = parser.parse_args()

    report = asyncio.run(
        scan_and_dedupe(
            args.apply,
            args.export,
            args.max_attempts,
            rebuild_indexes=args.rebuild_indexes,
        )
    )
    print(json.dumps(report["actions"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
