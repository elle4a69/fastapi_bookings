from pathlib import Path

root = Path(__file__).resolve().parents[2]

# 1. User create response must include schema-required company.
p = root / "app/api/routers/auth.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    '    return {"ok": True, "data": user}\n',
    '    return {\n'
    '        "ok": True,\n'
    '        "data": {\n'
    '            "id": user.id,\n'
    '            "company": tenant.subdomain,\n'
    '            "login": user.login,\n'
    '            "role": user.role,\n'
    '            "created_at": user.created_at,\n'
    '            "updated_at": user.updated_at,\n'
    '        },\n'
    '    }\n',
    1,
)
p.write_text(s, encoding="utf-8")

# 2. Duplicate product SKU should be a controlled conflict, not a 500.
p = root / "app/api/routers/products.py"
s = p.read_text(encoding="utf-8")
s = s.replace("from sqlalchemy.orm import Session\n", "from sqlalchemy.exc import IntegrityError\nfrom sqlalchemy.orm import Session\n")
s = s.replace(
    "    db.add(product)\n    db.commit()\n    db.refresh(product)\n",
    "    db.add(product)\n"
    "    try:\n"
    "        db.commit()\n"
    "    except IntegrityError as exc:\n"
    "        db.rollback()\n"
    "        raise HTTPException(status_code=409, detail=f\"Product SKU '{product_in.sku}' already exists\") from exc\n"
    "    db.refresh(product)\n",
    1,
)
p.write_text(s, encoding="utf-8")

# 3. Do not null a required special-day date during partial updates.
p = root / "app/api/routers/admin_schedule.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "    for field, value in special_in.dict(exclude_unset=True).items():\n        setattr(day, field, value)\n",
    "    for field, value in special_in.dict(exclude_unset=True).items():\n"
    "        if field == \"date\" and value is None:\n"
    "            continue\n"
    "        setattr(day, field, value)\n",
    1,
)
p.write_text(s, encoding="utf-8")

# 4. Every invoice line must carry tenant context.
p = root / "app/api/routers/checkout.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    '        db.add(InvoiceLine(invoice_id=invoice.id, line_type=line["line_type"], item_id=line.get("item_id"), description=line["description"], quantity=line["quantity"], unit_price=line["unit_price"], amount=line["amount"]))\n',
    '        db.add(InvoiceLine(tenant_id=tenant.id, invoice_id=invoice.id, line_type=line["line_type"], item_id=line.get("item_id"), description=line["description"], quantity=line["quantity"], unit_price=line["unit_price"], amount=line["amount"]))\n',
    1,
)
p.write_text(s, encoding="utf-8")

# 5. Improve sweep values: URLs, string IDs, and uniqueness-sensitive fields.
p = root / "tools/postman-sweep/prepare_authenticated_sweep.py"
s = p.read_text(encoding="utf-8")
# Ensure special string IDs are handled before generic *_id numeric handling.
s = s.replace(
    '    if value in exact:\n        if key and key.endswith("_id"):\n',
    '    if value in exact:\n'
    '        if key in {"stripe_session_id", "device_id"}:\n'
    '            return "postman-test-id"\n'
    '        if key and key.endswith("_id"):\n',
    1,
)
s = s.replace(
    '    if key and key.endswith("_id") and isinstance(value, str):\n',
    '    if key in {"stripe_session_id", "device_id"}:\n'
    '        return "postman-test-id"\n'
    '    if key and key.endswith("_id") and isinstance(value, str):\n',
    1,
)
# Always force callback query parameters to valid absolute URLs.
s = s.replace(
    '        if key in {"success_url", "cancel_url"}:\n            resolved = "https://example.com/callback"\n',
    '        if key in {"success_url", "cancel_url"}:\n            resolved = "https://example.com/callback"\n',
)
# Make repeated-run unique fields deterministic per request name.
s = s.replace(
    '        if payload.get("code") == "postman-sweep-code":\n            payload["code"] = "postman-" + re.sub(r"[^a-z0-9]+", "-", request_name.lower()).strip("-")\n',
    '        slug = re.sub(r"[^a-z0-9]+", "-", request_name.lower()).strip("-")\n'
    '        if payload.get("code") == "postman-sweep-code":\n'
    '            payload["code"] = "postman-" + slug\n'
    '        if payload.get("sku") in {"test", "<string>"}:\n'
    '            payload["sku"] = "postman-" + slug\n',
    1,
)
p.write_text(s, encoding="utf-8")

print("remaining defects patched")
