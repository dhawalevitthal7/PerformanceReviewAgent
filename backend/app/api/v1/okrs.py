"""
Personal OKR endpoints with cascade linking and quarterly filtering.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from app.db.database import get_db
from app.db.models import (
    OKR,
    KeyResult,
    User,
    DepartmentOKR,
    DepartmentKeyResult,
    Profile,
    UserRole,
)
from app.api.v1.dependencies import get_current_user

router = APIRouter()


# ── Quarter helper ────────────────────────────────────────────────────────────

def _quarter_date_range(quarter: int, year: int):
    """Return (start, end) datetimes for the given quarter."""
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 3
    start = datetime(year, start_month, 1)
    if end_month > 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, end_month, 1)
    return start, end


def _quarter_label_from_date(dt: datetime) -> str:
    """Return quarter label in Qx-YYYY format for a given date."""
    quarter = ((dt.month - 1) // 3) + 1
    return f"Q{quarter}-{dt.year}"


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class KeyResultCreate(BaseModel):
    title: str
    target: float
    unit: str
    due_date: datetime


class KeyResultUpdate(BaseModel):
    current: float


class KeyResultResponse(BaseModel):
    id: str
    title: str
    target: float
    current: float
    unit: str
    due_date: datetime

    class Config:
        from_attributes = True


class OKRCreate(BaseModel):
    objective: str
    due_date: datetime
    parent_dept_okr_id: Optional[str] = None
    key_results: List[KeyResultCreate]


class OKRUpdate(BaseModel):
    objective: Optional[str] = None
    due_date: Optional[datetime] = None


class OKRResponse(BaseModel):
    id: str
    objective: str
    created_at: datetime
    due_date: datetime
    parent_dept_okr_id: Optional[str] = None
    key_results: List[KeyResultResponse]

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[OKRResponse])
async def get_okrs(
    quarter: Optional[int] = Query(None, ge=1, le=4),
    year: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all OKRs for the current user.
    Optionally filter by quarter/year (OKRs whose date range overlaps the quarter).
    """
    query = db.query(OKR).filter(OKR.user_id == current_user.id)

    if quarter and year:
        q_start, q_end = _quarter_date_range(quarter, year)
        # OKR overlaps the quarter if created_at < q_end AND due_date >= q_start
        query = query.filter(OKR.created_at < q_end, OKR.due_date >= q_start)

    return query.order_by(OKR.created_at.desc()).all()


@router.get("/{okr_id}", response_model=OKRResponse)
async def get_okr(
    okr_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific OKR by ID."""
    okr = db.query(OKR).filter(OKR.id == okr_id, OKR.user_id == current_user.id).first()
    if not okr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OKR not found")
    return okr


@router.post("", response_model=OKRResponse, status_code=status.HTTP_201_CREATED)
async def create_okr(
    okr_data: OKRCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new OKR, optionally linked to a department OKR.

    For managers creating a fresh goal (not cascading), mirror the goal to
    department-level OKRs so employees in the same department can cascade it.
    """
    okr_id = str(uuid.uuid4())
    okr = OKR(
        id=okr_id,
        user_id=current_user.id,
        objective=okr_data.objective,
        due_date=okr_data.due_date,
        parent_dept_okr_id=okr_data.parent_dept_okr_id,
    )
    db.add(okr)
    db.flush()

    for kr_data in okr_data.key_results:
        kr_id = str(uuid.uuid4())
        key_result = KeyResult(
            id=kr_id,
            okr_id=okr_id,
            title=kr_data.title,
            target=kr_data.target,
            current=0.0,
            unit=kr_data.unit,
            due_date=kr_data.due_date,
        )
        db.add(key_result)

    # Manager-created goals from "My OKRs" should also appear as department goals.
    # Skip this when the goal is already a cascade from an existing department OKR.
    if not okr_data.parent_dept_okr_id:
        profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
        if profile and profile.role == UserRole.MANAGER and profile.department_id:
            dept_okr_id = str(uuid.uuid4())
            dept_okr = DepartmentOKR(
                id=dept_okr_id,
                department_id=profile.department_id,
                objective=okr_data.objective,
                quarter=_quarter_label_from_date(okr_data.due_date),
                due_date=okr_data.due_date,
                created_by=current_user.id,
            )
            db.add(dept_okr)
            db.flush()

            for kr_data in okr_data.key_results:
                db.add(
                    DepartmentKeyResult(
                        id=str(uuid.uuid4()),
                        dept_okr_id=dept_okr_id,
                        title=kr_data.title,
                        target=kr_data.target,
                        unit=kr_data.unit,
                        due_date=kr_data.due_date,
                    )
                )

    db.commit()
    db.refresh(okr)
    return okr


@router.put("/{okr_id}", response_model=OKRResponse)
async def update_okr(
    okr_id: str,
    okr_data: OKRUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an OKR."""
    okr = db.query(OKR).filter(OKR.id == okr_id, OKR.user_id == current_user.id).first()
    if not okr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OKR not found")

    if okr_data.objective is not None:
        okr.objective = okr_data.objective
    if okr_data.due_date is not None:
        okr.due_date = okr_data.due_date

    db.commit()
    db.refresh(okr)
    return okr


@router.delete("/{okr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_okr(
    okr_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an OKR."""
    okr = db.query(OKR).filter(OKR.id == okr_id, OKR.user_id == current_user.id).first()
    if not okr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OKR not found")
    db.delete(okr)
    db.commit()
    return None


@router.put("/{okr_id}/key-results/{kr_id}", response_model=KeyResultResponse)
async def update_key_result(
    okr_id: str,
    kr_id: str,
    kr_data: KeyResultUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a key result's current value."""
    okr = db.query(OKR).filter(OKR.id == okr_id, OKR.user_id == current_user.id).first()
    if not okr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OKR not found")

    key_result = db.query(KeyResult).filter(KeyResult.id == kr_id, KeyResult.okr_id == okr_id).first()
    if not key_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key result not found")

    key_result.current = kr_data.current
    db.commit()
    db.refresh(key_result)
    return key_result
