from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "fastapi_bookings.db"

TARGETS = [
    ("clients", "email in ('test','<string>') or phone in ('test','<string>')"),
    ("providers", "name='<string>' and email='<string>'"),
    ("locations", "name='<string>' and address='<string>'"),
    ("notification_templates", "code='<string>' and name='<string>'"),
    ("categories", "name='<string>'"),
    ("tax_rates", "name='<string>'"),
    ("payment_processor_configs", "provider='<string>'"),
    ("plugin_states", "name='<string>'"),
]


def main() -> None:
    conn = sqlite3.connect(DB)
    try:
        removed: dict[str, int] = {}
        for table, where_clause in TARGETS:
            cursor = conn.execute(f"DELETE FROM {table} WHERE {where_clause}")
            removed[table] = cursor.rowcount
        conn.commit()
        print(json.dumps(removed, sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
