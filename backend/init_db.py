"""
Database initialization script.
Run this script to create/reset all tables in the database.

Usage:
    python init_db.py
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

from app.db.database import engine, Base
from app.core.config import settings
# Import all models to ensure they're registered with Base.metadata
from app.db.models import (
    User, Profile, OKR, KeyResult, CheckIn, 
    Assessment, Review, ProgressHistory, UserRole, CheckInMood, ReviewStatus
)

def init_db():
    """Create all database tables."""
    print("=" * 60)
    print("Database Initialization Script")
    print("=" * 60)
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Database Type: {'SQLite' if settings.DATABASE_URL.startswith('sqlite') else 'PostgreSQL'}")
    print("-" * 60)
    
    try:
        print("\nCreating database tables...")
        print("Tables to create:")
        print("  - users")
        print("  - profiles")
        print("  - okrs")
        print("  - key_results")
        print("  - checkins")
        print("  - assessments")
        print("  - reviews")
        print("  - progress_history")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("\n" + "=" * 60)
        print("[OK] Database tables created successfully!")
        print("=" * 60)
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\nCreated {len(tables)} table(s):")
        for table in sorted(tables):
            print(f"  [OK] {table}")
        
        print("\nDatabase initialization complete!")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"[ERROR] Error creating database tables: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    init_db()
