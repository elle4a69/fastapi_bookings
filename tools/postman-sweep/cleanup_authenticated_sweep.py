from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.models.user import User
from app.models.client import Client

TEMP_USER_FILE = Path(__file__).resolve().parent / ".sweep-temp-user-id"
TEMP_CLIENT_FILE = Path(__file__).resolve().parent / ".sweep-temp-client-id"
TEMP_CLIENT_EMAIL = "__postman_sweep_client__@example.com"
TEMP_LOGIN = "__postman_sweep_owner__"


def main() -> None:
    db = SessionLocal()
    try:
        query = db.query(User).filter(User.login == TEMP_LOGIN)
        if TEMP_USER_FILE.exists():
            try:
                temp_id = int(TEMP_USER_FILE.read_text(encoding="utf-8").strip())
                query = query.filter(User.id == temp_id)
            except ValueError:
                pass
        removed = query.delete(synchronize_session=False)
        client_query = db.query(Client).filter(Client.email == TEMP_CLIENT_EMAIL)
        if TEMP_CLIENT_FILE.exists():
            try:
                temp_client_id = int(TEMP_CLIENT_FILE.read_text(encoding="utf-8").strip())
                client_query = client_query.filter(Client.id == temp_client_id)
            except ValueError:
                pass
        removed_clients = client_query.delete(synchronize_session=False)
        db.commit()
        print(f"Removed {removed} temporary sweep user(s)")
        print(f"Removed {removed_clients} temporary sweep client(s)")
    finally:
        db.close()
        TEMP_USER_FILE.unlink(missing_ok=True)
        TEMP_CLIENT_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
