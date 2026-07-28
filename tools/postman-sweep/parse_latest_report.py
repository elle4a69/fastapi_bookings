import base64
import collections
import json
from pathlib import Path

reports = Path(__file__).parent / "reports"
report_dir = max((p for p in reports.glob("run-*") if (p / "authenticated-sweep.json").exists()), key=lambda p: p.name)
report = report_dir / "authenticated-sweep.json"
data = json.loads(report.read_text(encoding="utf-8"))
rows = []
for execution in data["run"]["executions"]:
    code = int(execution["response"]["code"])
    name = execution["item"]["name"]
    stream = execution["response"].get("stream")
    body = ""
    if isinstance(stream, list):
        body = bytes(stream).decode("utf-8", "replace")
    elif isinstance(stream, str):
        try:
            body = base64.b64decode(stream).decode("utf-8", "replace")
        except Exception:
            body = stream
    rows.append((code, name, body[:300].replace("\n", " ")))

print(f"REPORT={report_dir}")
for code, count in sorted(collections.Counter(code for code, _, _ in rows).items()):
    print(f"{code}={count}")
print("---NON-2XX---")
for code, name, body in rows:
    if not 200 <= code < 300:
        print(f"{code}\t{name}\t{body}")
print("---SERVER ERRORS---")
for code, name, body in rows:
    if code >= 500:
        print(f"{code}\t{name}\t{body}")
