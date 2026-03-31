"""
Team endpoints.
Managers see all profiles in the same company.
Employees see colleagues in the same department.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.db.database import get_db
from app.db.models import User, Profile, OKR, KeyResult, UserRole
from app.api.v1.dependencies import get_current_user

router = APIRouter()


class TeamMemberResponse(BaseModel):
    id: str
    name: str
    role: str
    department: str
    overall_progress: float
    okr_count: int

    class Config:
        from_attributes = True


def _calculate_progress(db: Session, user_id: str) -> tuple[float, int]:
    """Return (overall_progress_percent, okr_count) for a given user."""
    okrs = db.query(OKR).filter(OKR.user_id == user_id).all()
    okr_count = len(okrs)

    total_progress = 0.0
    progress_count = 0

    for okr in okrs:
        if not okr.key_results:
            continue
        kr_progresses = []
        for kr in okr.key_results:
            if kr.target > 0:
                if "reduce" in kr.title.lower() or "downtime" in kr.title.lower():
                    prog = min(100, max(0, (kr.target / kr.current) * 100)) if kr.current > 0 else 0
                else:
                    prog = min(100, max(0, (kr.current / kr.target) * 100))
                kr_progresses.append(prog)
        if kr_progresses:
            total_progress += sum(kr_progresses) / len(kr_progresses)
            progress_count += 1

    overall = total_progress / progress_count if progress_count > 0 else 0
    return round(overall, 1), okr_count


@router.get("", response_model=List[TeamMemberResponse])
async def get_team_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get team members.
    - Managers: all profiles in the same company (excluding self).
    - Employees: colleagues in the same department (using department_id).
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    query = db.query(Profile).filter(
        Profile.company_code == profile.company_code,
        Profile.user_id != current_user.id,
    )

    if profile.role == UserRole.EMPLOYEE:
        # Employees only see people in their department
        if profile.department_id:
            query = query.filter(Profile.department_id == profile.department_id)
        else:
            # Fallback to text match if department_id not linked yet
            query = query.filter(Profile.department == profile.department)

    team_profiles = query.all()

    team_members = []
    for tp in team_profiles:
        overall_progress, okr_count = _calculate_progress(db, tp.user_id)
        team_members.append(
            TeamMemberResponse(
                id=tp.user_id,
                name=tp.full_name,
                role=tp.role.value if hasattr(tp.role, "value") else str(tp.role),
                department=tp.department or "",
                overall_progress=overall_progress,
                okr_count=okr_count,
            )
        )

    return team_members


@router.get("/{user_id}", response_model=TeamMemberResponse)
async def get_team_member(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific team member's details."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    team_profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not team_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    # Permission check: same company, and if employee same department
    if team_profile.company_code != profile.company_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in your company")

    if profile.role == UserRole.EMPLOYEE:
        same_dept = (
            (profile.department_id and profile.department_id == team_profile.department_id)
            or profile.department == team_profile.department
        )
        if not same_dept:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in your department")

    overall_progress, okr_count = _calculate_progress(db, user_id)

    return TeamMemberResponse(
        id=team_profile.user_id,
        name=team_profile.full_name,
        role=team_profile.role.value if hasattr(team_profile.role, "value") else str(team_profile.role),
        department=team_profile.department or "",
        overall_progress=overall_progress,
        okr_count=okr_count,
    )
