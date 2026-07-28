from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
openapi = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
known = set(openapi["paths"])
pattern = re.compile(r"[\"'`](/api/(?:admin|public|forms|v1)[^\"'`?]*)")


def canonical(route: str) -> str:
    route = re.sub(r"\$\{[^}]+\}", "{param}", route)
    return re.sub(r"\{[^}]+\}", "{param}", route)


known_canonical = {canonical(path) for path in known}
missing: list[tuple[str, int, str]] = []

for path in sorted((ROOT / "mapbox").rglob("*.ts*")):
    if "node_modules" in path.parts or "dist" in path.parts:
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in pattern.finditer(line):
            route = match.group(1)
            if canonical(route) not in known_canonical:
                missing.append((str(path.relative_to(ROOT)), lineno, route))

for file_name, lineno, route in missing:
    print(f"{file_name}:{lineno}: {route}")
print(f"missing={len(missing)}")
raise SystemExit(1 if missing else 0)
