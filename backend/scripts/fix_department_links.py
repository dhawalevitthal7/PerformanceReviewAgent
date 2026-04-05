"""
Utility script to ensure a manager manages a department and an employee
is linked to that same department by department_id.

Usage (examples):
  python scripts/fix_department_links.py --manager "riya" --employee "shreyansh" --department "Marketing"

Looks up profiles by case-insensitive full_name. Operates within the current
database configured for the backend.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Optional, Tuple

from sqlalchemy import func as sa_func

from app.db.database import SessionLocal
from app.db.models import Department, Profile


def normalize_department(name: str) -> str:
    return name.strip().title()


def find_profile_by_name(db, name: str) -> Optional[Profile]:
    return (
        db.query(Profile)
        .filter(sa_func.lower(Profile.full_name) == name.strip().lower())
        .first()
    )


def ensure_department(
    db,
    company_code: str,
    dept_name: str,
) -> Department:
    dept = (
        db.query(Department)
        .filter(
            Department.company_code == company_code,
            sa_func.lower(Department.name) == dept_name.lower(),
        )
        .first()
    )
    if dept:
        return dept
    dept = Department(
        id=str(uuid.uuid4()),
        name=dept_name,
        company_code=company_code,
    )
    db.add(dept)
    db.flush()
    return dept


def link_manager_and_employee(
    manager_name: str,
    employee_name: str,
    department_name: str,
) -> Tuple[str, str, str]:
    db = SessionLocal()
    try:
        manager = find_profile_by_name(db, manager_name)
        if not manager:
            raise SystemExit(f"Manager profile not found: {manager_name}")

        employee = find_profile_by_name(db, employee_name)
        if not employee:
            raise SystemExit(f"Employee profile not found: {employee_name}")

        if manager.company_code != employee.company_code:
            raise SystemExit("Manager and employee belong to different companies.")

        dept_name = normalize_department(department_name)
        dept = ensure_department(db, manager.company_code, dept_name)

        # Set manager for department
        dept.manager_id = manager.user_id
        db.flush()

        # Link employee (and manager, for completeness) to this department
        employee.department_id = dept.id
        employee.department = dept.name
        employee.is_setup_done = True

        if not manager.department_id:
            manager.department_id = dept.id
        manager.department = dept.name
        manager.is_setup_done = True

        db.commit()

        return manager.user_id, employee.user_id, dept.id
    finally:
        db.close()


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Fix department links for manager and employee.")
    parser.add_argument("--manager", required=True, help="Manager full_name (case-insensitive)")
    parser.add_argument("--employee", required=True, help="Employee full_name (case-insensitive)")
    parser.add_argument("--department", required=True, help="Department name")
    args = parser.parse_args(argv)

    m_id, e_id, d_id = link_manager_and_employee(args.manager, args.employee, args.department)
    print(
        {
            "manager_user_id": m_id,
            "employee_user_id": e_id,
            "department_id": d_id,
            "status": "updated",
        }
    )


if __name__ == "__main__":
    main(sys.argv[1:])

