import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.db.database import SessionLocal
from scripts.seed_clean_numbered_data import seed_numbered_mock_data

def run():
    db = SessionLocal()
    try:
        print("Seeding fresh clean numbered demo environment...")
        result = seed_numbered_mock_data(db=db, reset_existing=True)
        print(f"Database fully seeded with clean numbered entities: {result}")
        return result
    except Exception as e:
        print(f"Error during seeding: {e}", file=sys.stderr)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run()
    sys.exit(0)
