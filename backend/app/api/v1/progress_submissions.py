"""Employee progress submissions and manager review workflow."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime, timezone
import uuid

from app.db.database import get_db
from app.db.models import (
    User,
    Profile,
    OKR,
    KeyResult,
    ProgressSubmission,
    SubmissionStatus,
    UserRole,
    Department,
)
from app.api.v1.dependencies import get_current_user, require_manager, require_employee

router = APIRouter()


class ProgressSubmissionCreate(BaseModel):
    key_result_id: str
    employee_value: float
    employee_note: Optional[str] = None


class ProgressSubmissionReview(BaseModel):
    action: Literal["approve", "override"]
    manager_value: Optional[float] = None
    manager_note: Optional[str] = None


class ProgressSubmissionResponse(BaseModel):
    id: str
    key_result_id: str
    submitted_by: str
    reviewed_by: Optional[str]
    employee_value: float
    manager_value: Optional[float]
    employee_note: Optional[str]
    manager_note: Optional[str]
    status: SubmissionStatus
    submitted_at: datetime
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProgressSubmissionWithContext(ProgressSubmissionResponse):
    """Submission plus helpful context for manager views."""
    kr_title: Optional[str] = None
    okr_id: Optional[str] = None
    okr_objective: Optional[str] = None


def _team_employee_ids_for_manager(db: Session, manager_id: str, company_code: str) -> List[str]:
    dept_ids = [
        d.id
        for d in db.query(Department).filter(Department.manager_id == manager_id).all()
    ]
    if not dept_ids:
        return []
    return [
        p.user_id
        for p in db.query(Profile)
        .filter(
            Profile.company_code == company_code,
            Profile.role == UserRole.EMPLOYEE,
            Profile.department_id.in_(dept_ids),
        )
        .all()
    ]


def _can_manager_review_submission(
    db: Session,
    manager_id: str,
    company_code: str,
    submitted_by: str,
    actor_role: UserRole,
) -> bool:
    if actor_role == UserRole.CEO:
        subj = db.query(Profile).filter(Profile.user_id == submitted_by).first()
        return bool(subj and subj.company_code == company_code)
    return submitted_by in _team_employee_ids_for_manager(db, manager_id, company_code)


@router.post("", response_model=ProgressSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_progress(
    body: ProgressSubmissionCreate,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    kr = db.query(KeyResult).filter(KeyResult.id == body.key_result_id).first()
    if not kr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key result not found")

    okr = db.query(OKR).filter(OKR.id == kr.okr_id).first()
    if not okr or okr.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your key result")

    pending = (
        db.query(ProgressSubmission)
        .filter(
            ProgressSubmission.key_result_id == body.key_result_id,
            ProgressSubmission.status == SubmissionStatus.PENDING_REVIEW,
        )
        .first()
    )
    if pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A progress update is already pending review for this key result",
        )

    row = ProgressSubmission(
        id=str(uuid.uuid4()),
        key_result_id=body.key_result_id,
        submitted_by=current_user.id,
        employee_value=body.employee_value,
        employee_note=body.employee_note,
        status=SubmissionStatus.PENDING_REVIEW,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/pending", response_model=List[ProgressSubmissionResponse])
async def list_pending_for_team(
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if profile.role == UserRole.CEO:
        employee_ids = [
            p.user_id
            for p in db.query(Profile).filter(
                Profile.company_code == profile.company_code,
                Profile.role == UserRole.EMPLOYEE,
            ).all()
        ]
    else:
        employee_ids = _team_employee_ids_for_manager(db, current_user.id, profile.company_code)

    if not employee_ids:
        return []

    return (
        db.query(ProgressSubmission)
        .filter(
            ProgressSubmission.submitted_by.in_(employee_ids),
            ProgressSubmission.status == SubmissionStatus.PENDING_REVIEW,
        )
        .order_by(ProgressSubmission.submitted_at.desc())
        .all()
    )


@router.get("/my", response_model=List[ProgressSubmissionResponse])
async def list_my_submissions(
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    return (
        db.query(ProgressSubmission)
        .filter(ProgressSubmission.submitted_by == current_user.id)
        .order_by(ProgressSubmission.submitted_at.desc())
        .all()
    )

@router.get("/by-user/{user_id}", response_model=List[ProgressSubmissionWithContext])
async def list_for_employee(
    user_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """
    Manager/CEO: list all submissions (any status) for a specific employee
    in your company/team. Includes KR/OKR context strings.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    # Authorization: user must be in same company, and if manager must be in their team
    target = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if target.company_code != profile.company_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in your company")

    if profile.role != UserRole.CEO:
        team_ids = _team_employee_ids_for_manager(db, current_user.id, profile.company_code)
        if user_id not in team_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in your team")

    # Fix N+1 query issue by using joins
    results = (
        db.query(ProgressSubmission, KeyResult, OKR)
        .outerjoin(KeyResult, KeyResult.id == ProgressSubmission.key_result_id)
        .outerjoin(OKR, OKR.id == KeyResult.okr_id)
        .filter(ProgressSubmission.submitted_by == user_id)
        .order_by(ProgressSubmission.submitted_at.desc())
        .all()
    )

    out: list[ProgressSubmissionWithContext] = []
    for s, kr, okr in results:
        out.append(
            ProgressSubmissionWithContext(
                id=s.id,
                key_result_id=s.key_result_id,
                submitted_by=s.submitted_by,
                reviewed_by=s.reviewed_by,
                employee_value=s.employee_value,
                manager_value=s.manager_value,
                employee_note=s.employee_note,
                manager_note=s.manager_note,
                status=s.status,
                submitted_at=s.submitted_at,
                reviewed_at=s.reviewed_at,
                kr_title=kr.title if kr else None,
                okr_id=okr.id if okr else None,
                okr_objective=okr.objective if okr else None,
            )
        )
    return out

@router.put("/{submission_id}/review", response_model=ProgressSubmissionResponse)
async def review_submission(
    submission_id: str,
    body: ProgressSubmissionReview,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    sub = db.query(ProgressSubmission).filter(ProgressSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if sub.status != SubmissionStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Submission already reviewed")

    if not _can_manager_review_submission(
        db, current_user.id, profile.company_code, sub.submitted_by, profile.role
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    kr = db.query(KeyResult).filter(KeyResult.id == sub.key_result_id).first()
    if not kr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key result missing")

    now = datetime.now(timezone.utc)
    if body.action == "approve":
        sub.status = SubmissionStatus.APPROVED
        kr.current = sub.employee_value
    else:
        if body.manager_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="manager_value is required for override",
            )
        sub.status = SubmissionStatus.OVERRIDDEN
        sub.manager_value = body.manager_value
        kr.current = body.manager_value

    sub.reviewed_by = current_user.id
    sub.reviewed_at = now
    if body.manager_note is not None:
        sub.manager_note = body.manager_note

    db.commit()
    db.refresh(sub)
    return sub
