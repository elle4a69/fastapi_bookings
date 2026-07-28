from pathlib import Path

root = Path(__file__).resolve().parents[2]

# Hold confirmation: protect booking insert from provider/time uniqueness collisions.
p = root / "app/api/routers/holds.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "    # Persist booking\n    db.add(booking)\n    db.commit()\n    db.refresh(booking)\n",
    "    # Persist booking\n"
    "    db.add(booking)\n"
    "    try:\n"
    "        db.commit()\n"
    "    except IntegrityError as exc:\n"
    "        db.rollback()\n"
    "        raise HTTPException(\n"
    "            status_code=status.HTTP_409_CONFLICT,\n"
    "            detail=\"The selected provider and time are no longer available\",\n"
    "        ) from exc\n"
    "    db.refresh(booking)\n",
    1,
)
p.write_text(s, encoding="utf-8")

# Tip rows require tenant context.
p = root / "app/api/routers/checkout.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "    tip = Tip(invoice_id=invoice.id, amount=payload.amount, note=payload.note)\n",
    "    tip = Tip(tenant_id=tenant.id, invoice_id=invoice.id, amount=payload.amount, note=payload.note)\n",
    1,
)
p.write_text(s, encoding="utf-8")

# Stripe deposit test must meet the minimum amount.
p = root / "tools/postman-sweep/prepare_authenticated_sweep.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    '        if key in {"success_url", "cancel_url"}:\n            value = "https://example.com/callback"\n',
    '        if key in {"success_url", "cancel_url"}:\n'
    '            value = "https://example.com/callback"\n'
    '        elif key == "amount_cents":\n'
    '            value = "100"\n',
    1,
)
p.write_text(s, encoding="utf-8")

print("exact final three patched")
