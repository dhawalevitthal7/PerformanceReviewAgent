"""
Test database connection and verify tables exist.
Run this script to verify your database is properly set up.
"""
import sys
import os
import codecs

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import engine, SessionLocal
from app.core.config import settings
from sqlalchemy import text, inspect

def test_database():
    """Test database connection and verify tables."""
    print("=" * 80)
    print("DATABASE CONNECTION TEST")
    print("=" * 80)
    print(f"\nDatabase URL: {settings.DATABASE_URL}")
    print(f"Database Type: {'SQLite' if settings.DATABASE_URL.startswith('sqlite') else 'PostgreSQL'}")
    print("-" * 80)
    
    # Test connection
    print("\n1. Testing database connection...")
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1")).scalar()
        db.close()
        print("   [OK] Database connection successful!")
    except Exception as e:
        print(f"   [ERROR] Database connection failed: {e}")
        return False
    
    # Check tables
    print("\n2. Checking database tables...")
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            "users", "profiles", "okrs", "key_results",
            "checkins", "assessments", "reviews", "progress_history"
        ]
        
        print(f"   Found {len(tables)} table(s):")
        for table in sorted(tables):
            status = "[OK]" if table in expected_tables else "[?]"
            print(f"   {status} {table}")
        
        # Check for missing tables
        missing_tables = [t for t in expected_tables if t not in tables]
        if missing_tables:
            print(f"\n   [WARNING] Missing tables: {', '.join(missing_tables)}")
            print("   Run 'python init_db.py' to create missing tables.")
            return False
        else:
            print("\n   [OK] All expected tables exist!")
        
    except Exception as e:
        print(f"   [ERROR] Error checking tables: {e}")
        return False
    
    # Test table structure
    print("\n3. Verifying table structures...")
    try:
        inspector = inspect(engine)
        
        # Check users table
        if "users" in tables:
            users_columns = [col["name"] for col in inspector.get_columns("users")]
            required_columns = ["id", "email", "hashed_password"]
            missing = [col for col in required_columns if col not in users_columns]
            if missing:
                print(f"   [ERROR] Users table missing columns: {', '.join(missing)}")
            else:
                print("   [OK] Users table structure OK")
        
        # Check profiles table
        if "profiles" in tables:
            profiles_columns = [col["name"] for col in inspector.get_columns("profiles")]
            required_columns = ["id", "user_id", "full_name", "role", "department", "company_code"]
            missing = [col for col in required_columns if col not in profiles_columns]
            if missing:
                print(f"   [ERROR] Profiles table missing columns: {', '.join(missing)}")
            else:
                print("   [OK] Profiles table structure OK")
        
    except Exception as e:
        print(f"   [ERROR] Error verifying table structures: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("[OK] Database test completed successfully!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
