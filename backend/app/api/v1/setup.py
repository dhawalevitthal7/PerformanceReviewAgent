"""
First-Login Setup API
=====================
Handles first-login onboarding for both roles.

Manager flow:
  - Creates departments (via /departments endpoint)
  - Optionally uploads KPI CSV (via /kpi/upload endpoint)
  - Calls POST /setup/manager to mark setup as done

Employee flow:
  - Calls POST /setup/employee with their chosen department_id
  - This assigns the department and marks setup as done

Endpoints:
  GET  /setup/status     - Check if current user has completed setup
  POST /setup/manager    - Manager marks their setup as complete
  POST /setup/employee   - Employee selects department + completes setup
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Profile, Department, User, UserRole
from app.api.v1.dependencies import get_current_user

router = APIRouter()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class EmployeeSetupRequest(BaseModel):
    department_id: str


class SetupStatusResponse(BaseModel):
    is_setup_done: bool
    role: str
    department_id: str | None = None
    department_name: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the setup status for the currently logged-in user.
    Frontend uses this to decide whether to redirect to the setup page.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    dept_name = None
    if profile.department_id:
        dept = db.query(Department).filter(Department.id == profile.department_id).first()
        dept_name = dept.name if dept else None

    return SetupStatusResponse(
        is_setup_done=bool(profile.is_setup_done),
        role=profile.role.value,
        department_id=profile.department_id,
        department_name=dept_name,
    )


@router.post("/manager")
async def complete_manager_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manager calls this after completing the setup wizard
    (creating departments, optionally uploading CSV).
    Sets is_setup_done = True on their profile.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    if profile.role != UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers use this endpoint",
        )

    profile.is_setup_done = True
    db.commit()
    return {"message": "Manager setup complete", "is_setup_done": True}


@router.post("/employee")
async def complete_employee_setup(
    data: EmployeeSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Employee selects their department on first login.
    Validates that the department belongs to the same company,
    then assigns it and marks setup as done.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    if profile.role != UserRole.EMPLOYEE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employees use this endpoint",
        )

    # Verify the department exists and belongs to the same company
    dept = db.query(Department).filter(
        Department.id == data.department_id,
        Department.company_code == profile.company_code,
    ).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found in your company",
        )

    # Assign department and mark setup complete
    profile.department_id = dept.id
    profile.department = dept.name   # keep text field in sync for display
    profile.is_setup_done = True
    db.commit()
    db.refresh(profile)

    return {
        "message": f"Department '{dept.name}' selected. Setup complete.",
        "department_id": dept.id,
        "department_name": dept.name,
        "is_setup_done": True,
    }
