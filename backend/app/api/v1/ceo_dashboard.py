"""CEO read-only dashboards and org alignment tree."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any, List, Optional

from app.db.database import get_db
from app.db.models import (
    User,
    Profile,
    Department,
    DepartmentOKR,
    OrganizationOKR,
    OKR,
    KeyResult,
    Review,
    UserRole,
)
from app.api.v1.dependencies import require_ceo
from app.api.v1.team import _calculate_progress

router = APIRouter()


class CEOOverviewResponse(BaseModel):
    total_employees: int
    total_departments: int
    avg_okr_progress_percent: float


class CEODepartmentRow(BaseModel):
    department_id: str
    name: str
    manager_name: Optional[str]
    employee_count: int
    avg_employee_okr_progress_percent: float


class CEOEmployeeRow(BaseModel):
    user_id: str
    full_name: str
    department: str
    okr_count: int
    okr_progress_percent: float
    latest_review_score: Optional[float]


def _avg_company_employee_okr_progress(db: Session, company_code: str) -> float:
    employee_ids = [
        p.user_id
        for p in db.query(Profile).filter(
            Profile.company_code == company_code,
            Profile.role == UserRole.EMPLOYEE,
        ).all()
    ]
    if not employee_ids:
        return 0.0
    total = 0.0
    n = 0
    for uid in employee_ids:
        prog, _ = _calculate_progress(db, uid)
        total += prog
        n += 1
    return round(total / n, 1) if n else 0.0


@router.get("/overview", response_model=CEOOverviewResponse)
async def ceo_overview(
    current_user: User = Depends(require_ceo),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    code = profile.company_code
    total_employees = (
        db.query(Profile)
        .filter(Profile.company_code == code, Profile.role == UserRole.EMPLOYEE)
        .count()
    )
    total_departments = db.query(Department).filter(Department.company_code == code).count()
    avg_okr = _avg_company_employee_okr_progress(db, code)

    return CEOOverviewResponse(
        total_employees=total_employees,
        total_departments=total_departments,
        avg_okr_progress_percent=avg_okr,
    )


@router.get("/departments", response_model=List[CEODepartmentRow])
async def ceo_departments(
    current_user: User = Depends(require_ceo),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    code = profile.company_code
    depts = db.query(Department).filter(Department.company_code == code).all()
    rows: list[CEODepartmentRow] = []

    for d in depts:
        mgr_name = None
        if d.manager_id:
            mp = db.query(Profile).filter(Profile.user_id == d.manager_id).first()
            mgr_name = mp.full_name if mp else None

        emp_ids = [
            p.user_id
            for p in db.query(Profile).filter(
                Profile.company_code == code,
                Profile.role == UserRole.EMPLOYEE,
                Profile.department_id == d.id,
            ).all()
        ]
        if emp_ids:
            total = sum(_calculate_progress(db, uid)[0] for uid in emp_ids)
            avg = round(total / len(emp_ids), 1)
        else:
            avg = 0.0

        rows.append(
            CEODepartmentRow(
                department_id=d.id,
                name=d.name,
                manager_name=mgr_name,
                employee_count=len(emp_ids),
                avg_employee_okr_progress_percent=avg,
            )
        )

    rows.sort(key=lambda r: r.name.lower())
    return rows


@router.get("/employees", response_model=List[CEOEmployeeRow])
async def ceo_employees(
    current_user: User = Depends(require_ceo),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    code = profile.company_code
    employees = (
        db.query(Profile)
        .filter(Profile.company_code == code, Profile.role == UserRole.EMPLOYEE)
        .all()
    )
    out: list[CEOEmployeeRow] = []

    for ep in employees:
        prog, okr_count = _calculate_progress(db, ep.user_id)
        latest = (
            db.query(Review)
            .filter(Review.user_id == ep.user_id)
            .order_by(Review.created_at.desc())
            .first()
        )
        out.append(
            CEOEmployeeRow(
                user_id=ep.user_id,
                full_name=ep.full_name,
                department=ep.department or "",
                okr_count=okr_count,
                okr_progress_percent=prog,
                latest_review_score=latest.score if latest else None,
            )
        )

    out.sort(key=lambda r: r.full_name.lower())
    return out


@router.get("/org-alignment")
async def ceo_org_alignment(
    current_user: User = Depends(require_ceo),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Org OKR → department OKRs (linked via parent_org_okr_id) → personal OKRs (parent_dept_okr_id).
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    code = profile.company_code
    org_rows = (
        db.query(OrganizationOKR)
        .filter(OrganizationOKR.company_code == code)
        .order_by(OrganizationOKR.created_at.desc())
        .all()
    )

    company_department_ids = [
        d.id for d in db.query(Department).filter(Department.company_code == code).all()
    ]

    tree: list[dict[str, Any]] = []

    for o in org_rows:
        org_krs = [
            {
                "id": kr.id,
                "title": kr.title,
                "target": kr.target,
                "unit": kr.unit,
                "due_date": kr.due_date.isoformat() if kr.due_date else None,
            }
            for kr in (o.key_results or [])
        ]

        dq = db.query(DepartmentOKR).filter(DepartmentOKR.parent_org_okr_id == o.id)
        if company_department_ids:
            dq = dq.filter(DepartmentOKR.department_id.in_(company_department_ids))
        dept_okrs = dq.all()

        dept_blocks: list[dict[str, Any]] = []
        for d_okr in dept_okrs:
            dept = db.query(Department).filter(Department.id == d_okr.department_id).first()
            dkrs = [
                {
                    "id": kr.id,
                    "title": kr.title,
                    "target": kr.target,
                    "unit": kr.unit,
                }
                for kr in (d_okr.key_results or [])
            ]
            personal = db.query(OKR).filter(OKR.parent_dept_okr_id == d_okr.id).all()
            personal_blocks = []
            for p_okr in personal:
                owner = db.query(Profile).filter(Profile.user_id == p_okr.user_id).first()
                personal_blocks.append(
                    {
                        "id": p_okr.id,
                        "user_id": p_okr.user_id,
                        "owner_name": owner.full_name if owner else None,
                        "objective": p_okr.objective,
                        "assigned_by": p_okr.assigned_by,
                        "key_results": [
                            {
                                "id": kr.id,
                                "title": kr.title,
                                "target": kr.target,
                                "current": kr.current,
                                "unit": kr.unit,
                            }
                            for kr in (p_okr.key_results or [])
                        ],
                    }
                )

            dept_blocks.append(
                {
                    "department_id": d_okr.department_id,
                    "department_name": dept.name if dept else "",
                    "dept_okr": {
                        "id": d_okr.id,
                        "objective": d_okr.objective,
                        "quarter": d_okr.quarter,
                        "due_date": d_okr.due_date.isoformat() if d_okr.due_date else None,
                        "key_results": dkrs,
                    },
                    "personal_okrs": personal_blocks,
                }
            )

        tree.append(
            {
                "org_okr": {
                    "id": o.id,
                    "objective": o.objective,
                    "quarter": o.quarter,
                    "due_date": o.due_date.isoformat() if o.due_date else None,
                    "key_results": org_krs,
                },
                "department_okrs": dept_blocks,
            }
        )

    return {"company_code": code, "tree": tree}
