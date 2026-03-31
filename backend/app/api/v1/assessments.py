from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
from app.db.database import get_db
from app.db.models import Assessment, User
from app.api.v1.dependencies import get_current_user

router = APIRouter()


class AssessmentCreate(BaseModel):
    self_rating: int
    strengths: str
    improvements: str
    notes: Optional[str] = None


class AssessmentUpdate(BaseModel):
    self_rating: Optional[int] = None
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    notes: Optional[str] = None


class AssessmentResponse(BaseModel):
    id: str
    self_rating: int
    strengths: str
    improvements: str
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("", response_model=list[AssessmentResponse])
async def get_assessments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all assessments for the current user."""
    assessments = db.query(Assessment).filter(Assessment.user_id == current_user.id).order_by(Assessment.created_at.desc()).all()
    return assessments


@router.get("/latest", response_model=AssessmentResponse)
async def get_latest_assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the latest assessment for the current user."""
    assessment = db.query(Assessment).filter(Assessment.user_id == current_user.id).order_by(Assessment.created_at.desc()).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assessment found"
        )
    return assessment


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    assessment_data: AssessmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new assessment."""
    if not (1 <= assessment_data.self_rating <= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self rating must be between 1 and 5"
        )
    
    assessment_id = str(uuid.uuid4())
    assessment = Assessment(
        id=assessment_id,
        user_id=current_user.id,
        self_rating=assessment_data.self_rating,
        strengths=assessment_data.strengths,
        improvements=assessment_data.improvements,
        notes=assessment_data.notes
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.put("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: str,
    assessment_data: AssessmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an assessment."""
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id, Assessment.user_id == current_user.id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment_data.self_rating is not None:
        if not (1 <= assessment_data.self_rating <= 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Self rating must be between 1 and 5"
            )
        assessment.self_rating = assessment_data.self_rating
    if assessment_data.strengths is not None:
        assessment.strengths = assessment_data.strengths
    if assessment_data.improvements is not None:
        assessment.improvements = assessment_data.improvements
    if assessment_data.notes is not None:
        assessment.notes = assessment_data.notes
    
    db.commit()
    db.refresh(assessment)
    return assessment
