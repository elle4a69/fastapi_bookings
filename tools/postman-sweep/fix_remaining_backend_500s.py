import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]

# Fix create-user response contract.
auth = root / 'app' / 'api' / 'routers' / 'auth.py'
s = auth.read_text(encoding='utf-8')
replacement = '''    return {
        "ok": True,
        "data": {
            "id": user.id,
            "company": tenant.subdomain,
            "login": user.login,
            "role": user.role,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        },
    }'''
s, count = re.subn(r'    return \{"ok": True, "data": user\}\s*$', replacement, s, count=1, flags=re.MULTILINE)
if count != 1:
    raise RuntimeError(f'Expected one create-user return replacement, got {count}')
auth.write_text(s, encoding='utf-8')

# Convert duplicate notification-template update collisions to HTTP 409.
notifications = root / 'app' / 'api' / 'routers' / 'notifications.py'
s = notifications.read_text(encoding='utf-8')
if 'from sqlalchemy.exc import IntegrityError' not in s:
    s = s.replace('from sqlalchemy.orm import Session\n', 'from sqlalchemy.orm import Session\nfrom sqlalchemy.exc import IntegrityError\n')
old = '''    for field, value in template_in.dict(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return {"ok": True, "data": template}'''
new = '''    for field, value in template_in.dict(exclude_unset=True).items():
        setattr(template, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Notification template code already exists",
        )
    db.refresh(template)
    return {"ok": True, "data": template}'''
if old not in s:
    raise RuntimeError('Notification-template update block not found')
s = s.replace(old, new, 1)
notifications.write_text(s, encoding='utf-8')
print('Remaining backend 500 fixes applied')
