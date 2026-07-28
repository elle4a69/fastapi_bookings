import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
spec = json.loads((root / "openapi.json").read_text(encoding="utf-8"))
operations = []
for path, path_item in sorted(spec["paths"].items()):
    for method, operation in path_item.items():
        if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
            continue
        operations.append(
            {
                "method": method.upper(),
                "path": path,
                "operationId": operation.get("operationId"),
                "tags": operation.get("tags", []),
                "summary": operation.get("summary"),
            }
        )
manifest = {
    "generatedFrom": "openapi.json",
    "operationCount": len(operations),
    "pathCount": len(spec["paths"]),
    "operations": operations,
}
(root / "contracts" / "route-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"route manifest: {len(operations)} operations across {len(spec['paths'])} paths")
