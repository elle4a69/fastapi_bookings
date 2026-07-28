from pathlib import Path
import re

app_path = Path(__file__).with_name("app.py")
text = app_path.read_text(encoding="utf-8-sig")

text = text.replace("import secrets\n", "")
text = text.replace(
    "from fastapi import Depends, FastAPI, Header, HTTPException, Query, status",
    "from fastapi import FastAPI, HTTPException, Query",
)
text = text.replace('KEY_FILE = STATE_DIR / "runner-api-key.txt"\n', "")

text = re.sub(
    r"\ndef load_or_create_api_key\(\) -> str:\n.*?\nAPI_KEY = load_or_create_api_key\(\)\n",
    "\n",
    text,
    flags=re.S,
)
text = re.sub(
    r"\ndef require_api_key\(.*?\n        raise HTTPException\(status_code=status\.HTTP_401_UNAUTHORIZED, detail=\"Invalid runner API key\"\)\n",
    "\n",
    text,
    flags=re.S,
)
text = text.replace(", dependencies=[Depends(require_api_key)]", "")

app_path.write_text(text, encoding="utf-8")
key_file = Path(__file__).with_name("state") / "runner-api-key.txt"
if key_file.exists():
    key_file.unlink()

print("Runner authentication removed")
