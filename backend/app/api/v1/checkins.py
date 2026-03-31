from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid
from app.db.database import get_db
from app.db.models import CheckIn, CheckInMood, User, OKR, Assessment
from app.api.v1.dependencies import get_current_user
from app.services.azure_openai_service import AzureOpenAIService
from app.services.srs_workflow_service import compute_okr_progress_metrics

router = APIRouter()


class CheckInCreate(BaseModel):
    date: datetime
    note: str
    mood: CheckInMood


class CheckInResponse(BaseModel):
    id: str
    date: datetime
    note: str
    mood: CheckInMood
    created_at: datetime

    class Config:
        from_attributes = True


class CheckInDraftResponse(BaseModel):
    update: str
    wins: str
    blockers: str
    next_week_goals: str
    cadence: str
    workflow_metadata: dict


@router.get("", response_model=List[CheckInResponse])
async def get_checkins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all check-ins for the current user."""
    checkins = db.query(CheckIn).filter(CheckIn.user_id == current_user.id).order_by(CheckIn.date.desc()).all()
    return checkins


@router.post("/draft", response_model=CheckInDraftResponse)
async def draft_checkin(
    cadence: str = Query("weekly"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate AI-drafted check-in content from OKR and assessment evidence."""
    okrs = db.query(OKR).filter(OKR.user_id == current_user.id).all()
    latest_assessment = db.query(Assessment).filter(Assessment.user_id == current_user.id).order_by(Assessment.created_at.desc()).first()
    recent_checkins = db.query(CheckIn).filter(CheckIn.user_id == current_user.id).order_by(CheckIn.date.desc()).limit(4).all()

    evidence_payload = {
        "okr_metrics": compute_okr_progress_metrics(okrs),
        "latest_assessment": {
            "self_rating": latest_assessment.self_rating,
            "strengths": latest_assessment.strengths,
            "improvements": latest_assessment.improvements,
        } if latest_assessment else None,
        "recent_checkins": [
            {"date": c.date.isoformat(), "mood": c.mood.value, "note": c.note}
            for c in recent_checkins
        ],
    }

    ai_service = AzureOpenAIService()
    draft = ai_service.draft_checkin(evidence_payload=evidence_payload, cadence=cadence)

    return CheckInDraftResponse(
        update=draft.get("update", "Completed planned weekly tasks and tracked progress on goals."),
        wins=draft.get("wins", "Maintained steady progress on assigned objectives."),
        blockers=draft.get("blockers", "No major blockers this period."),
        next_week_goals=draft.get("next_week_goals", "Prioritize pending key results and quality improvements."),
        cadence=cadence,
        workflow_metadata={
            "workflow_model": "SRS_V1_AGENTIC",
            "stages": {
                "data_integration": True,
                "okr_kpi_evidence_analysis": True,
                "continuous_feedback_context_fusion": True,
                "ai_review_generation": False,
            },
        },
    )


@router.post("", response_model=CheckInResponse, status_code=status.HTTP_201_CREATED)
async def create_checkin(
    checkin_data: CheckInCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new check-in."""
    checkin_id = str(uuid.uuid4())
    checkin = CheckIn(
        id=checkin_id,
        user_id=current_user.id,
        date=checkin_data.date,
        note=checkin_data.note,
        mood=checkin_data.mood
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@router.get("/{checkin_id}", response_model=CheckInResponse)
async def get_checkin(
    checkin_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific check-in by ID."""
    checkin = db.query(CheckIn).filter(CheckIn.id == checkin_id, CheckIn.user_id == current_user.id).first()
    if not checkin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check-in not found"
        )
    return checkin
