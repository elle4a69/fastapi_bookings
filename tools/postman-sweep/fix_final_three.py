from pathlib import Path

root = Path(__file__).resolve().parents[2]

# Hold confirmation: convert provider/time uniqueness collisions to 409.
p = root / "app/api/routers/holds.py"
s = p.read_text(encoding="utf-8")
if "from sqlalchemy.exc import IntegrityError" not in s:
    s = s.replace("from sqlalchemy.orm import Session\n", "from sqlalchemy.exc import IntegrityError\nfrom sqlalchemy.orm import Session\n")
s = s.replace(
    "    db.add(booking)\n    db.delete(hold)\n    db.commit()\n",
    "    db.add(booking)\n"
    "    db.delete(hold)\n"
    "    try:\n"
    "        db.commit()\n"
    "    except IntegrityError as exc:\n"
    "        db.rollback()\n"
    "        raise HTTPException(status_code=409, detail=\"The selected provider and time are no longer available\") from exc\n",
    1,
)
p.write_text(s, encoding="utf-8")

# Public tip arithmetic: preserve Decimal throughout.
p = root / "app/api/routers/checkout.py"
s = p.read_text(encoding="utf-8")
if "from decimal import Decimal" not in s:
    s = s.replace("from datetime import", "from decimal import Decimal\nfrom datetime import", 1)
s = s.replace(
    "    invoice.tip_total += float(payload.amount)\n    invoice.total += float(payload.amount)\n",
    "    tip_amount = Decimal(str(payload.amount))\n"
    "    invoice.tip_total = (invoice.tip_total or Decimal(\"0\")) + tip_amount\n"
    "    invoice.total = (invoice.total or Decimal(\"0\")) + tip_amount\n",
    1,
)
p.write_text(s, encoding="utf-8")

# Sweep query normalisation: force callback URLs after placeholder replacement.
p = root / "tools/postman-sweep/prepare_authenticated_sweep.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "        value = replacements.get(value, value)\n        if value.startswith(\":\"):\n",
    "        value = replacements.get(value, value)\n"
    "        if key in {\"success_url\", \"cancel_url\"}:\n"
    "            value = \"https://example.com/callback\"\n"
    "        if value.startswith(\":\"):\n",
    1,
)
p.write_text(s, encoding="utf-8")

print("final three patched")
