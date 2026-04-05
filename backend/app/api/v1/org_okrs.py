"""Organization-level OKRs (CEO create; managers and CEO can list)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid

from app.db.database import get_db
from app.db.models import User, Profile, OrganizationOKR, OrgKeyResult
from app.api.v1.dependencies import require_ceo, get_current_user

router = APIRouter()


class OrgKeyResultCreate(BaseModel):
    title: str
    target: float
    unit: str
    due_date: datetime


class OrgKeyResultResponse(BaseModel):
    id: str
    title: str
    target: float
    unit: str
    due_date: datetime

    class Config:
        from_attributes = True


class OrganizationOKRCreate(BaseModel):
    objective: str
    quarter: str
    due_date: datetime
    key_results: List[OrgKeyResultCreate]


class OrganizationOKRResponse(BaseModel):
    id: str
    company_code: str
    objective: str
    quarter: str
    due_date: datetime
    created_by: str
    created_at: datetime
    key_results: List[OrgKeyResultResponse]

    class Config:
        from_attributes = True


def _assert_same_company(profile: Profile, company_code: str) -> None:
    if profile.company_code != company_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization OKR belongs to another company",
        )


@router.post("", response_model=OrganizationOKRResponse, status_code=status.HTTP_201_CREATED)
async def create_org_okr(
    body: OrganizationOKRCreate,
    current_user: User = Depends(require_ceo),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    okr_id = str(uuid.uuid4())
    row = OrganizationOKR(
        id=okr_id,
        company_code=profile.company_code,
        objective=body.objective,
        quarter=body.quarter,
        due_date=body.due_date,
        created_by=current_user.id,
    )
    db.add(row)
    db.flush()
    for kr in body.key_results:
        db.add(
            OrgKeyResult(
                id=str(uuid.uuid4()),
                org_okr_id=okr_id,
                title=kr.title,
                target=kr.target,
                unit=kr.unit,
                due_date=kr.due_date,
            )
        )
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=List[OrganizationOKRResponse])
async def list_org_okrs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    from sqlalchemy.orm import joinedload
    rows = (
        db.query(OrganizationOKR)
        .options(joinedload(OrganizationOKR.key_results))
        .filter(OrganizationOKR.company_code == profile.company_code)
        .order_by(OrganizationOKR.created_at.desc())
        .all()
    )
    return rows


@router.delete("/{okr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_okr(
    okr_id: str,
    current_user: User = Depends(require_ceo),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    row = db.query(OrganizationOKR).filter(OrganizationOKR.id == okr_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization OKR not found")
    _assert_same_company(profile, row.company_code)
    db.delete(row)
    db.commit()
    return None
