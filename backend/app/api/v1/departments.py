"""
Department Management API
=========================
Managers can create departments and define quarterly OKRs at department level.
Both managers and employees can read department data.

Endpoints:
  GET  /departments                   - List all departments in the company
  POST /departments                   - Manager creates a department
  GET  /departments/{id}/okrs         - Get department OKRs (visible to all)
  POST /departments/{id}/okrs         - Manager creates a dept-level OKR
  DELETE /departments/{dept_id}/okrs/{okr_id}  - Manager deletes a dept OKR
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from app.db.database import get_db
from app.db.models import (
    Department,
    DepartmentOKR,
    DepartmentKeyResult,
    OrganizationOKR,
    OKR,
    Profile,
    User,
    UserRole,
)
from app.api.v1.dependencies import get_current_user

router = APIRouter()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str


class DepartmentResponse(BaseModel):
    id: str
    name: str
    company_code: str
    manager_id: Optional[str] = None

    class Config:
        from_attributes = True


class DeptKeyResultCreate(BaseModel):
    title: str
    target: float
    unit: str
    due_date: datetime


class DeptOKRCreate(BaseModel):
    objective: str
    quarter: str        # e.g. "Q2-2025"
    due_date: datetime
    key_results: List[DeptKeyResultCreate]
    parent_org_okr_id: Optional[str] = None


class DeptKeyResultResponse(BaseModel):
    id: str
    title: str
    target: float
    unit: str
    due_date: datetime

    class Config:
        from_attributes = True


class DeptOKRResponse(BaseModel):
    id: str
    department_id: str
    objective: str
    quarter: str
    due_date: datetime
    created_at: datetime
    parent_org_okr_id: Optional[str] = None
    key_results: List[DeptKeyResultResponse]

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_manager_profile(current_user: User, db: Session) -> Profile:
    """Fetch profile; manager or CEO may manage departments."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role not in (UserRole.MANAGER, UserRole.CEO):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers or CEOs can perform this action",
        )
    return profile


def _get_any_profile(current_user: User, db: Session) -> Profile:
    """Fetch profile for any role."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


# ── Department Endpoints ──────────────────────────────────────────────────────

@router.get("", response_model=List[DepartmentResponse])
async def list_departments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all departments in the current user's company. Accessible by all roles."""
    profile = _get_any_profile(current_user, db)
    departments = (
        db.query(Department)
        .filter(Department.company_code == profile.company_code)
        .order_by(Department.created_at)
        .all()
    )
    return departments


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    data: DepartmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager creates a new department for their company."""
    profile = _get_manager_profile(current_user, db)

    # Prevent duplicate department names within the same company
    existing = db.query(Department).filter(
        Department.company_code == profile.company_code,
        Department.name == data.name.strip(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department '{data.name}' already exists",
        )

    dept = Department(
        id=str(uuid.uuid4()),
        company_code=profile.company_code,
        name=data.name.strip(),
        manager_id=current_user.id,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    dept_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager deletes a department (and all its OKRs)."""
    profile = _get_manager_profile(current_user, db)
    dept = db.query(Department).filter(
        Department.id == dept_id,
        Department.company_code == profile.company_code,
    ).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    db.delete(dept)
    db.commit()
    return None


# ── Department OKR Endpoints ──────────────────────────────────────────────────

@router.get("/{dept_id}/okrs", response_model=List[DeptOKRResponse])
async def get_department_okrs(
    dept_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all OKRs for a specific department.
    Visible to both Managers and Employees in the same company.
    """
    profile = _get_any_profile(current_user, db)

    # Verify the department belongs to the same company
    dept = db.query(Department).filter(
        Department.id == dept_id,
        Department.company_code == profile.company_code,
    ).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    okrs = (
        db.query(DepartmentOKR)
        .options(joinedload(DepartmentOKR.key_results))
        .filter(DepartmentOKR.department_id == dept_id)
        .order_by(DepartmentOKR.created_at.desc())
        .all()
    )
    return okrs


@router.post(
    "/{dept_id}/okrs",
    response_model=DeptOKRResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department_okr(
    dept_id: str,
    data: DeptOKRCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager defines a quarterly OKR for a department."""
    profile = _get_manager_profile(current_user, db)

    dept = db.query(Department).filter(
        Department.id == dept_id,
        Department.company_code == profile.company_code,
    ).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    if not data.key_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one key result is required",
        )

    parent_org_id: Optional[str] = None
    if data.parent_org_okr_id:
        org_row = (
            db.query(OrganizationOKR)
            .filter(
                OrganizationOKR.id == data.parent_org_okr_id,
                OrganizationOKR.company_code == profile.company_code,
            )
            .first()
        )
        if not org_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization OKR for this company",
            )
        parent_org_id = data.parent_org_okr_id

    okr_id = str(uuid.uuid4())
    okr = DepartmentOKR(
        id=okr_id,
        department_id=dept_id,
        objective=data.objective.strip(),
        quarter=data.quarter.strip(),
        due_date=data.due_date,
        created_by=current_user.id,
        parent_org_okr_id=parent_org_id,
    )
    db.add(okr)
    db.flush()

    for kr_data in data.key_results:
        db.add(DepartmentKeyResult(
            id=str(uuid.uuid4()),
            dept_okr_id=okr_id,
            title=kr_data.title.strip(),
            target=kr_data.target,
            unit=kr_data.unit.strip(),
            due_date=kr_data.due_date,
        ))

    db.commit()
    # Reload with eager-loaded key_results
    okr = (
        db.query(DepartmentOKR)
        .options(joinedload(DepartmentOKR.key_results))
        .filter(DepartmentOKR.id == okr_id)
        .first()
    )
    return okr


@router.delete(
    "/{dept_id}/okrs/{okr_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_department_okr(
    dept_id: str,
    okr_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager deletes a department OKR."""
    profile = _get_manager_profile(current_user, db)

    okr = db.query(DepartmentOKR).filter(
        DepartmentOKR.id == okr_id,
        DepartmentOKR.department_id == dept_id,
    ).first()
    if not okr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OKR not found")

    db.delete(okr)
    db.commit()
    return None


# ── Employee: My Department OKRs ─────────────────────────────────────────────

class EmployeeDeptKRResponse(BaseModel):
    id: str
    title: str
    target: float
    unit: str
    due_date: datetime

    class Config:
        from_attributes = True


class EmployeeDeptOKRResponse(BaseModel):
    """Department OKR as seen by an employee, with cascade status."""
    id: str
    objective: str
    quarter: str
    due_date: datetime
    department_name: str
    already_cascaded: bool
    key_results: List[EmployeeDeptKRResponse]


@router.get("/my-department-okrs", response_model=List[EmployeeDeptOKRResponse])
async def get_my_department_okrs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Employee endpoint: returns all OKRs for the employee's own department,
    annotated with whether the employee has already cascaded each one.
    """
    profile = _get_any_profile(current_user, db)

    if not profile.department_id:
        return []

    dept = db.query(Department).filter(Department.id == profile.department_id).first()
    if not dept:
        return []

    dept_okrs = (
        db.query(DepartmentOKR)
        .options(joinedload(DepartmentOKR.key_results))
        .filter(DepartmentOKR.department_id == dept.id)
        .order_by(DepartmentOKR.created_at.desc())
        .all()
    )

    # Find which dept OKRs this employee has already cascaded
    cascaded_ids = set(
        row[0]
        for row in db.query(OKR.parent_dept_okr_id)
        .filter(
            OKR.user_id == current_user.id,
            OKR.parent_dept_okr_id.isnot(None),
        )
        .all()
    )

    results = []
    for dokr in dept_okrs:
        results.append(
            EmployeeDeptOKRResponse(
                id=dokr.id,
                objective=dokr.objective,
                quarter=dokr.quarter,
                due_date=dokr.due_date,
                department_name=dept.name,
                already_cascaded=dokr.id in cascaded_ids,
                key_results=[
                    EmployeeDeptKRResponse(
                        id=kr.id,
                        title=kr.title,
                        target=kr.target,
                        unit=kr.unit,
                        due_date=kr.due_date,
                    )
                    for kr in dokr.key_results
                ],
            )
        )

    return results
