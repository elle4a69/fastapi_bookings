"""Export the authoritative OpenAPI document and optionally check drift."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


OPENAPI_PATH = ROOT / "openapi.json"
MANIFEST_PATH = ROOT / "contracts" / "route-manifest.json"


def rendered_openapi() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def manifest_paths(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from manifest_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from manifest_paths(child)
    elif isinstance(value, str) and value.startswith("/"):
        yield value


def check_manifest() -> list[str]:
    schema_paths = set(app.openapi()["paths"])
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return sorted({path for path in manifest_paths(manifest) if "{" in path or path.startswith("/api")} - schema_paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = rendered_openapi()
    missing = check_manifest()
    if missing:
        print("Route manifest paths missing from OpenAPI:", *missing, sep="\n- ")
        return 1
    if args.check:
        if not OPENAPI_PATH.exists() or OPENAPI_PATH.read_text(encoding="utf-8") != content:
            print("openapi.json is stale; run tools/export_openapi.py")
            return 1
        return 0
    OPENAPI_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
