"""Database Parity Verification Script.

Compares source PostgreSQL database (port 5432) against dedicated database (port 5433)
to verify schema and row count parity without exposing credentials or PII.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from urllib.parse import urlparse, urlunparse
from sqlalchemy import create_engine, inspect, text
from app.core.config import settings


def get_destination_url(source_url: str, dest_port: int = 5433) -> str:
    parsed = urlparse(source_url)
    # Replace netloc host:port
    netloc_parts = parsed.netloc.split("@")
    if len(netloc_parts) == 2:
        auth, host_port = netloc_parts
        host = host_port.split(":")[0]
        new_netloc = f"{auth}@{host}:{dest_port}"
    else:
        host = parsed.netloc.split(":")[0]
        new_netloc = f"{host}:{dest_port}"
    return urlunparse(parsed._replace(netloc=new_netloc))


def verify_parity() -> bool:
    source_url = settings.DATABASE_URL
    dest_url = get_destination_url(source_url, 5433)

    print("Initiating DB parity check between source (port 5432) and target (port 5433)...")
    src_engine = create_engine(source_url)
    dst_engine = create_engine(dest_url)

    src_inspector = inspect(src_engine)
    dst_inspector = inspect(dst_engine)

    src_tables = sorted(src_inspector.get_table_names())
    dst_tables = sorted(dst_inspector.get_table_names())

    all_matched = True

    # Check tables
    missing_in_dst = set(src_tables) - set(dst_tables)
    missing_in_src = set(dst_tables) - set(src_tables)

    if missing_in_dst:
        print(f"[-] Tables missing in target (5433): {sorted(missing_in_dst)}")
        all_matched = False
    if missing_in_src:
        print(f"[-] Tables extra in target (5433): {sorted(missing_in_src)}")
        all_matched = False

    common_tables = sorted(set(src_tables).intersection(set(dst_tables)))
    print(f"[+] Found {len(common_tables)} common tables to compare.")

    with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
        for table in common_tables:
            # Check columns
            src_cols = {c["name"]: str(c["type"]) for c in src_inspector.get_columns(table)}
            dst_cols = {c["name"]: str(c["type"]) for c in dst_inspector.get_columns(table)}

            cols_diff = False
            if set(src_cols.keys()) != set(dst_cols.keys()):
                print(f"[-] Table '{table}' column set mismatch:")
                print(f"    Missing in target: {set(src_cols.keys()) - set(dst_cols.keys())}")
                print(f"    Extra in target:   {set(dst_cols.keys()) - set(src_cols.keys())}")
                cols_diff = True
                all_matched = False

            # Check row count
            try:
                src_count = src_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                dst_count = dst_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                if src_count != dst_count:
                    print(f"[-] Table '{table}' row count mismatch: Source={src_count}, Target={dst_count}")
                    all_matched = False
                else:
                    if not cols_diff:
                        print(f"    OK: '{table}' ({src_count} rows, {len(src_cols)} columns)")
            except Exception as e:
                print(f"[-] Error querying table '{table}': {e}")
                all_matched = False

    src_engine.dispose()
    dst_engine.dispose()

    if all_matched:
        print("[SUCCESS] 100% Schema and Row Parity Verified between Source and Target DB!")
    else:
        print("[FAILURE] Discrepancies detected between Source and Target DB.")

    return all_matched


if __name__ == "__main__":
    success = verify_parity()
    sys.exit(0 if success else 1)
