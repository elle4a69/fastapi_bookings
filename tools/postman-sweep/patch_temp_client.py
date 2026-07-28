from pathlib import Path

p = Path(r"F:\Projects\fastapi_bookings\tools\postman-sweep\prepare_authenticated_sweep.py")
s = p.read_text(encoding="utf-8")
s = s.replace("from app.core.security import create_access_token", "from app.core.security import create_access_token, get_password_hash")
s = s.replace('TEMP_USER_FILE = TOOL_DIR / ".sweep-temp-user-id"', 'TEMP_USER_FILE = TOOL_DIR / ".sweep-temp-user-id"\nTEMP_CLIENT_FILE = TOOL_DIR / ".sweep-temp-client-id"')
s = s.replace('TEMP_LOGIN = "__postman_sweep_owner__"', 'TEMP_LOGIN = "__postman_sweep_owner__"\nTEMP_CLIENT_EMAIL = "__postman_sweep_client__@example.com"\nTEMP_CLIENT_PASSWORD = "Postman123!"')
old = '''        client = db.query(Client).filter(Client.tenant_id == tenant.id).order_by(Client.id.asc()).first()\n        if client is None:\n            raise RuntimeError("No seeded client is available for client-token tests")\n        admin_token = create_access_token({"sub": str(user.id), "role": user.role})\n        public_token = create_access_token({"sub": tenant.subdomain})\n        client_token = create_access_token({"sub": f"client:{client.id}", "scope": "client"})\n        return admin_token, public_token, client_token, int(user.id)'''
new = '''        stale_clients = db.query(Client).filter(Client.tenant_id == tenant.id, Client.email == TEMP_CLIENT_EMAIL).all()\n        for row in stale_clients:\n            db.delete(row)\n        if stale_clients:\n            db.commit()\n\n        client = Client(\n            tenant_id=tenant.id,\n            name="Postman Sweep Client",\n            email=TEMP_CLIENT_EMAIL,\n            phone="+61400000001",\n            password_hash=get_password_hash(TEMP_CLIENT_PASSWORD),\n            active=True,\n            accepts_marketing=False,\n        )\n        db.add(client)\n        db.commit()\n        db.refresh(client)\n        TEMP_CLIENT_FILE.write_text(str(client.id), encoding="utf-8")\n\n        admin_token = create_access_token({"sub": str(user.id), "role": user.role})\n        public_token = create_access_token({"sub": tenant.subdomain})\n        client_token = create_access_token({"sub": f"client:{client.id}", "scope": "client"})\n        return admin_token, public_token, client_token, int(user.id)'''
if old not in s:
    raise SystemExit("target block not found")
s = s.replace(old, new)
s = s.replace('''        if "company" in payload:\n            payload["company"] = TENANT''', '''        if "company" in payload:\n            payload["company"] = TENANT\n        if request_name == "Login Client":\n            payload["email"] = TEMP_CLIENT_EMAIL\n            payload["password"] = TEMP_CLIENT_PASSWORD''')
p.write_text(s, encoding="utf-8")

p = Path(r"F:\Projects\fastapi_bookings\tools\postman-sweep\cleanup_authenticated_sweep.py")
s = p.read_text(encoding="utf-8")
s = s.replace('from app.models.user import User', 'from app.models.user import User\nfrom app.models.client import Client')
s = s.replace('TEMP_USER_FILE = Path(__file__).resolve().parent / ".sweep-temp-user-id"', 'TEMP_USER_FILE = Path(__file__).resolve().parent / ".sweep-temp-user-id"\nTEMP_CLIENT_FILE = Path(__file__).resolve().parent / ".sweep-temp-client-id"\nTEMP_CLIENT_EMAIL = "__postman_sweep_client__@example.com"')
s = s.replace('''        removed = query.delete(synchronize_session=False)\n        db.commit()\n        print(f"Removed {removed} temporary sweep user(s)")''', '''        removed = query.delete(synchronize_session=False)\n        client_query = db.query(Client).filter(Client.email == TEMP_CLIENT_EMAIL)\n        if TEMP_CLIENT_FILE.exists():\n            try:\n                temp_client_id = int(TEMP_CLIENT_FILE.read_text(encoding="utf-8").strip())\n                client_query = client_query.filter(Client.id == temp_client_id)\n            except ValueError:\n                pass\n        removed_clients = client_query.delete(synchronize_session=False)\n        db.commit()\n        print(f"Removed {removed} temporary sweep user(s)")\n        print(f"Removed {removed_clients} temporary sweep client(s)")''')
s = s.replace('TEMP_USER_FILE.unlink(missing_ok=True)', 'TEMP_USER_FILE.unlink(missing_ok=True)\n        TEMP_CLIENT_FILE.unlink(missing_ok=True)')
p.write_text(s, encoding="utf-8")
