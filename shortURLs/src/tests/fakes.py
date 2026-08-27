import asyncio
import re
import uuid
from types import SimpleNamespace

from pymongo.errors import AutoReconnect, DuplicateKeyError


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, branch) for branch in expected):
                return False
            continue
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if (
                "$regex" in expected
                and re.search(expected["$regex"], str(actual or "")) is None
            ):
                return False
            continue
        if actual != expected:
            return False
    return True


def _project(document: dict, projection: dict | None) -> dict:
    if not projection:
        return dict(document)
    included = {key for key, enabled in projection.items() if enabled}
    result = {key: value for key, value in document.items() if key in included}
    if projection.get("_id", 1) and "_id" in document:
        result["_id"] = document["_id"]
    return result


class FakeAsyncCursor:
    def __init__(self, documents: list[dict]):
        self.documents = [dict(document) for document in documents]
        self.limit_count: int | None = None
        self.position = 0

    def limit(self, limit: int):
        self.limit_count = limit
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        limit = self.limit_count
        if length is not None:
            limit = min(limit, length) if limit is not None else length
        documents = self.documents if limit is None else self.documents[:limit]
        return [dict(document) for document in documents]

    def __aiter__(self):
        self.position = 0
        return self

    async def __anext__(self):
        limit = (
            self.limit_count if self.limit_count is not None else len(self.documents)
        )
        if self.position >= min(limit, len(self.documents)):
            raise StopAsyncIteration
        document = dict(self.documents[self.position])
        self.position += 1
        return document


class FakeCollection:
    def __init__(self):
        self.documents: list[dict] = []
        self.fail_long_urls: set[str] = set()
        self.indexes = {
            "_id_": {"key": [("_id", 1)]},
        }
        self.lock = asyncio.Lock()

    async def find_one_and_update(self, filter_query, update, upsert, return_document):
        del return_document
        async with self.lock:
            long_url = filter_query["long_url"]
            if long_url in self.fail_long_urls:
                raise AutoReconnect("simulated storage outage")
            for document in self.documents:
                if _matches(document, filter_query):
                    return dict(document)
            if not upsert:
                return None
            new_document = dict(update["$setOnInsert"])
            for unique_field in ("long_url", "short_url", "short_code"):
                value = new_document.get(unique_field)
                if value and any(
                    doc.get(unique_field) == value for doc in self.documents
                ):
                    raise DuplicateKeyError(f"duplicate {unique_field}")
            new_document["_id"] = uuid.uuid4().hex
            new_document.setdefault("access_count", 0)
            self.documents.append(new_document)
            return dict(new_document)

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if _matches(document, query):
                return _project(document, projection)
        return None

    def find(self, query, projection=None):
        return FakeAsyncCursor(
            [
                _project(document, projection)
                for document in self.documents
                if _matches(document, query)
            ]
        )

    async def update_one(self, query, update):
        for document in self.documents:
            if not _matches(document, query):
                continue
            before = dict(document)
            for key, value in update.get("$set", {}).items():
                document[key] = value
            for key, value in update.get("$inc", {}).items():
                document[key] = document.get(key, 0) + value
            return SimpleNamespace(modified_count=int(document != before))
        return SimpleNamespace(modified_count=0)

    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query):
        original_count = len(self.documents)
        self.documents = [
            document for document in self.documents if not _matches(document, query)
        ]
        return SimpleNamespace(deleted_count=original_count - len(self.documents))

    async def aggregate(self, pipeline):
        field = pipeline[0]["$group"]["_id"].removeprefix("$")
        grouped: dict[object, list[dict]] = {}
        for document in self.documents:
            grouped.setdefault(document.get(field), []).append(document)
        duplicates = [
            {
                "_id": value,
                "count": len(documents),
                "docs": [dict(document) for document in documents],
            }
            for value, documents in grouped.items()
            if len(documents) > 1
        ]
        return FakeAsyncCursor(duplicates)

    async def create_index(self, field, unique=False):
        name = f"{field}_1"
        existing = self.indexes.get(name)
        if existing and existing.get("unique") != unique:
            raise RuntimeError("Index options conflict")
        self.indexes[name] = {"key": [(field, 1)], "unique": unique}
        return name

    async def index_information(self):
        return {name: dict(definition) for name, definition in self.indexes.items()}

    async def drop_index(self, name):
        self.indexes.pop(name)


class FakeDatabase:
    def __init__(self):
        self.collection = FakeCollection()

    def __getitem__(self, _name):
        return self.collection
