from pathlib import Path
p = Path(__file__).resolve().parents[2] / 'app' / 'api' / 'routers' / 'auth.py'
s = p.read_text(encoding='utf-8')
s = s.replace(
    '    return {"ok": True, "data": user}\n',
    '    return {\n        "ok": True,\n        "data": {\n            "id": user.id,\n            "company": tenant.subdomain,\n            "login": user.login,\n            "role": user.role,\n            "created_at": user.created_at,\n            "updated_at": user.updated_at,\n        },\n    }\n',
    1,
)
p.write_text(s, encoding='utf-8')
print('Create user response fixed')
