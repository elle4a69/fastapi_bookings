from pathlib import Path

root=Path(__file__).resolve().parents[2]

# Webhook tenant scoping
p=root/'app/api/routers/webhooks.py'
s=p.read_text(encoding='utf-8')
s=s.replace('    hook = WebhookRegistration(**webhook_in.dict())\n','    hook = WebhookRegistration(tenant_id=current_user.tenant_id, **webhook_in.dict())\n')
p.write_text(s,encoding='utf-8')

# Calendar note: never apply explicit None to non-null fields
p=root/'app/api/routers/calendar_notes.py'
s=p.read_text(encoding='utf-8')
s=s.replace('    for field, value in note_in.dict(exclude_unset=True).items():\n        setattr(note, field, value)\n','    for field, value in note_in.dict(exclude_unset=True).items():\n        if value is None and field in {"date", "text"}:\n            continue\n        setattr(note, field, value)\n')
p.write_text(s,encoding='utf-8')

# Sweep generator: valid URL query values and safe DELETE ids
p=root/'tools/postman-sweep/prepare_authenticated_sweep.py'
s=p.read_text(encoding='utf-8')
s=s.replace('        query.append((key, replacements.get(value, value)))\n','        resolved = replacements.get(value, value)\n        if key in {"success_url", "cancel_url"}:\n            resolved = "https://example.com/callback"\n        query.append((key, resolved))\n')
s=s.replace('        raw = normalise_url(raw, method, path_values)\n','        raw = normalise_url(raw, method, path_values)\n        if method == "DELETE":\n            raw = re.sub(r"/(?:" + "|".join(re.escape(str(v)) for v in set(path_values.values()) if str(v).isdigit()) + r")(?=/|\\?|$)", "/999999", raw)\n')
s=s.replace('        if key == "email":\n            return "postman-sweep@example.com"\n','        if key == "email":\n            return "postman-sweep@example.com"\n        if key == "password":\n            return "Postman123!"\n        if key in {"stripe_session_id", "device_id"}:\n            return "postman-test-id"\n')
p.write_text(s,encoding='utf-8')
print('applied')
