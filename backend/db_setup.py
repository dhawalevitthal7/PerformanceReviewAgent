"""
Database reset and setup script
===============================

Purpose:
- Drop ALL existing tables
- Recreate tables from the current SQLAlchemy models (Base.metadata)

Usage (from the backend directory):
    python db_setup.py

Notes:
- This gives you a clean slate that reflects the current backend logic:
  - Users with roles: ceo, manager, employee
  - Profiles with `role`, `is_setup_done`, optional `department_id`
  - Departments are keyed by `company_code` (email domain), created/configured by CEO
  - Optional integrations (e.g., Jira, BambooHR) are represented via IntegrationConfig
"""

from sqlalchemy import text

from app.db.database import engine, Base, SessionLocal

# Import models to ensure they are registered with Base.metadata
from app.db.models import (  # noqa: F401
    User,
    Profile,
    Department,
    DepartmentOKR,
    DepartmentKeyResult,
    OKR,
    KeyResult,
    Assessment,
    Review,
    ProgressHistory,
    KPIDataset,
    KPIRecord,
    IntegrationConfig,
    OrganizationOKR,
    OrgKeyResult,
    ProgressSubmission,
    OneOnOneMeeting,
)


def reset_and_setup_database() -> None:
    # Drop all existing tables
    Base.metadata.drop_all(bind=engine)

    # Recreate tables based on current models
    Base.metadata.create_all(bind=engine)

    # Optional sanity check: open a session and verify basic connectivity
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        db.commit()


if __name__ == "__main__":
    reset_and_setup_database()
    print("Database has been reset and set up successfully.")

