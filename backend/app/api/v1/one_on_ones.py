"""1:1 meeting scheduling and notes (manager creates/updates; both can view)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from app.db.database import get_db
from app.db.models import User, Profile, OneOnOneMeeting, MeetingStatus, UserRole, Department
from app.api.v1.dependencies import get_current_user, require_manager

router = APIRouter()


class OneOnOneCreate(BaseModel):
    employee_id: str
    scheduled_at: datetime
    agenda: Optional[str] = None


class OneOnOneUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    agenda: Optional[str] = None
    notes: Optional[str] = None
    action_items: Optional[str] = None
    status: Optional[MeetingStatus] = None


class OneOnOneResponse(BaseModel):
    id: str
    manager_id: str
    employee_id: str
    scheduled_at: datetime
    agenda: Optional[str]
    notes: Optional[str]
    action_items: Optional[str]
    status: MeetingStatus
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


def _can_manager_run_one_on_one(db: Session, manager_id: str, employee_profile: Profile) -> bool:
    if not employee_profile.department_id:
        return False
    dept = db.query(Department).filter(Department.id == employee_profile.department_id).first()
    return bool(dept and dept.manager_id == manager_id)


@router.post("", response_model=OneOnOneResponse, status_code=status.HTTP_201_CREATED)
async def schedule_one_on_one(
    body: OneOnOneCreate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    mgr_profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    emp_profile = db.query(Profile).filter(Profile.user_id == body.employee_id).first()
    if not mgr_profile or not emp_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    if emp_profile.company_code != mgr_profile.company_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee not in your company")
    if emp_profile.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target must be an employee")

    if mgr_profile.role == UserRole.MANAGER and not _can_manager_run_one_on_one(
        db, current_user.id, emp_profile
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only schedule 1:1s with employees you manage",
        )

    row = OneOnOneMeeting(
        id=str(uuid.uuid4()),
        manager_id=current_user.id,
        employee_id=body.employee_id,
        scheduled_at=body.scheduled_at,
        agenda=body.agenda,
        status=MeetingStatus.SCHEDULED,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=List[OneOnOneResponse])
async def list_one_on_ones(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if profile.role in (UserRole.MANAGER, UserRole.CEO):
        rows = (
            db.query(OneOnOneMeeting)
            .filter(OneOnOneMeeting.manager_id == current_user.id)
            .order_by(OneOnOneMeeting.scheduled_at.desc())
            .all()
        )
    elif profile.role == UserRole.EMPLOYEE:
        rows = (
            db.query(OneOnOneMeeting)
            .filter(OneOnOneMeeting.employee_id == current_user.id)
            .order_by(OneOnOneMeeting.scheduled_at.desc())
            .all()
        )
    else:
        rows = []

    return rows


@router.get("/{meeting_id}", response_model=OneOnOneResponse)
async def get_one_on_one(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(OneOnOneMeeting).filter(OneOnOneMeeting.id == meeting_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    if row.manager_id != current_user.id and row.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return row


@router.put("/{meeting_id}", response_model=OneOnOneResponse)
async def update_one_on_one(
    meeting_id: str,
    body: OneOnOneUpdate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    row = db.query(OneOnOneMeeting).filter(OneOnOneMeeting.id == meeting_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if row.manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if body.scheduled_at is not None:
        row.scheduled_at = body.scheduled_at
    if body.agenda is not None:
        row.agenda = body.agenda
    if body.notes is not None:
        row.notes = body.notes
    if body.action_items is not None:
        row.action_items = body.action_items
    if body.status is not None:
        row.status = body.status

    db.commit()
    db.refresh(row)
    return row


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_one_on_one(
    meeting_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    row = db.query(OneOnOneMeeting).filter(OneOnOneMeeting.id == meeting_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if row.manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    db.delete(row)
    db.commit()
    return None
