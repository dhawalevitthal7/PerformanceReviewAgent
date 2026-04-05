"""
Seed script to create demo users for PerformBharat.

Run this script once to create:
  - employee@demo.com  (password: demo123)  Role: Employee
  - manager@demo.com   (password: demo123)  Role: Manager
  - ceo@demo.com       (password: demo123)  Role: CEO

Usage:
    python seed_demo_users.py
"""

import sys
import os
import uuid

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import func as sa_func

from app.db.database import SessionLocal, engine, Base
from app.db.models import User, Profile, UserRole
from app.core.security import get_password_hash

# Demo user definitions
DEMO_USERS = [
    {
        "email": "employee@demo.com",
        "password": "demo123",
        "full_name": "Demo Employee",
        "role": UserRole.EMPLOYEE,
        "department": "Engineering",
        "company_name": "PerformBharat Demo",
        "company_code": "DEMO2024",
    },
    {
        "email": "manager@demo.com",
        "password": "demo123",
        "full_name": "Demo Manager",
        "role": UserRole.MANAGER,
        "department": "Engineering",
        "company_name": "PerformBharat Demo",
        "company_code": "DEMO2024",
    },
    {
        "email": "ceo@demo.com",
        "password": "demo123",
        "full_name": "Demo CEO",
        "role": UserRole.CEO,
        "department": "Demo Department",
        "company_name": "Demo Inc",
        "company_code": "demo.com",
    },
]


def seed_demo_users():
    """Create demo users if they don't already exist."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    created = []
    skipped = []

    try:
        for user_data in DEMO_USERS:
            existing = (
                db.query(User)
                .filter(sa_func.lower(User.email) == user_data["email"].lower())
                .first()
            )
            if existing:
                skipped.append(user_data["email"])
                continue

            # Create user record
            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
            )
            db.add(user)
            db.flush()

            # Create profile record
            profile = Profile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                full_name=user_data["full_name"],
                role=user_data["role"],
                department=user_data["department"],
                company_name=user_data["company_name"],
                company_code=user_data["company_code"],
            )
            db.add(profile)
            created.append(user_data["email"])

        db.commit()

        print("\n[OK] Demo users seeded successfully!")
        if created:
            print(f"   Created : {', '.join(created)}")
        if skipped:
            print(f"   Skipped (already exist): {', '.join(skipped)}")

        print("\nDemo credentials:")
        for u in DEMO_USERS:
            print(f"  Email   : {u['email']}")
            print(f"  Password: {u['password']}")
            print(f"  Role    : {u['role'].value}")
            print()

    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Error seeding demo users: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_users()
