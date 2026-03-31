"""
Reviews API
===========
AI-powered performance review generation, retrieval, and editing.

Endpoints:
  GET  /reviews                          - List reviews (manager sees all team, employee sees own)
  GET  /reviews/{id}                     - Get a specific review
  POST /reviews/generate                 - Generate AI review for a user
  POST /reviews/{id}/regenerate          - Manager provides feedback → AI regenerates review
  PUT  /reviews/{id}/status              - Manager updates review status
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import json

from app.db.database import get_db
from app.db.models import (
    Review, ReviewStatus, ReviewFeedback,
    User, Profile, OKR, Assessment, CheckIn,
    KPIDataset, KPIRecord,
)
from app.api.v1.dependencies import get_current_user
from app.services.azure_openai_service import AzureOpenAIService
from app.services.srs_workflow_service import (
    build_review_evidence_payload,
    compute_okr_progress_metrics,
)

router = APIRouter()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ReviewResponse(BaseModel):
    id: str
    user_id: str
    summary: str
    strengths: List[str]
    improvements: List[str]
    score: float
    status: ReviewStatus
    workflow_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReviewStatusUpdate(BaseModel):
    status: ReviewStatus


class ReviewRegenerateRequest(BaseModel):
    """Manager provides instructions to guide AI re-generation."""
    feedback: str  # e.g. "Focus more on KPI targets and add improvement suggestions"


class ReviewFeedbackResponse(BaseModel):
    id: str
    feedback_text: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_review(review: Review) -> ReviewResponse:
    """Convert a Review ORM object to a ReviewResponse, safely parsing JSON arrays."""
    return ReviewResponse(
        id=review.id,
        user_id=review.user_id,
        summary=review.summary,
        strengths=json.loads(review.strengths) if isinstance(review.strengths, str) else review.strengths,
        improvements=json.loads(review.improvements) if isinstance(review.improvements, str) else review.improvements,
        score=review.score,
        status=review.status,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _get_kpi_summary(target_user_email: str, company_code: str, db: Session) -> list[dict]:
    """Fetch KPI records for an employee from all company CSV datasets."""
    dataset_ids = [
        d.id for d in db.query(KPIDataset)
        .filter(KPIDataset.company_code == company_code)
        .all()
    ]
    if not dataset_ids:
        return []

    records = db.query(KPIRecord).filter(
        KPIRecord.dataset_id.in_(dataset_ids),
        KPIRecord.employee_email == target_user_email.lower(),
    ).all()

    return [
        {
            "metric": r.metric_name,
            "value": r.metric_value if r.metric_value is not None else r.metric_text,
            "period": r.period,
        }
        for r in records
    ]


# ── List / Get Reviews ────────────────────────────────────────────────────────

@router.get("", response_model=List[ReviewResponse])
async def get_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(None),
):
    """
    Get reviews.
    - Managers: can view all reviews for employees in their company (or filter by user_id).
    - Employees: can only view their own reviews.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    is_manager = profile.role.value == "manager"

    if is_manager and user_id:
        # Verify target is in the same company
        target_profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not target_profile or target_profile.company_code != profile.company_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view reviews for employees in your company",
            )
        reviews = db.query(Review).filter(Review.user_id == user_id).order_by(Review.created_at.desc()).all()

    elif is_manager:
        # All employee reviews in this company
        employee_ids = [
            p.user_id for p in db.query(Profile).filter(
                Profile.company_code == profile.company_code,
                Profile.role == "employee",
            ).all()
        ]
        reviews = (
            db.query(Review)
            .filter(Review.user_id.in_(employee_ids))
            .order_by(Review.created_at.desc())
            .all()
        ) if employee_ids else []

    else:
        reviews = (
            db.query(Review)
            .filter(Review.user_id == current_user.id)
            .order_by(Review.created_at.desc())
            .all()
        )

    return [_parse_review(r) for r in reviews]


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific review by ID with permission checks."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    review = db.query(Review).filter(Review.id == review_id).first()

    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    is_manager = profile.role.value == "manager"

    if not is_manager:
        if review.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    else:
        owner_profile = db.query(Profile).filter(Profile.user_id == review.user_id).first()
        if not owner_profile or owner_profile.company_code != profile.company_code:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return _parse_review(review)


# ── Generate Review ───────────────────────────────────────────────────────────

@router.post("/generate", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def generate_review(
    user_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate an AI-powered performance review.
    - Managers can generate for any employee (pass ?user_id=).
    - Employees can generate for themselves.

    Evidence used: OKRs, assessment, check-in count, KPI CSV data.
    """
    target_user_id = user_id if user_id else current_user.id

    # Permission check
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if user_id and (not profile or profile.role.value != "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can generate reviews for other users",
        )

    # Gather evidence
    okrs = db.query(OKR).filter(OKR.user_id == target_user_id).all()
    assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == target_user_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    checkin_count = db.query(CheckIn).filter(CheckIn.user_id == target_user_id).count()
    okr_metrics = compute_okr_progress_metrics(okrs)

    # Fetch KPI data from CSV for this employee
    target_user = db.query(User).filter(User.id == target_user_id).first()
    target_profile = db.query(Profile).filter(Profile.user_id == target_user_id).first()
    kpi_summary = []
    if target_user and target_profile:
        kpi_summary = _get_kpi_summary(target_user.email, target_profile.company_code, db)

    evidence_payload = build_review_evidence_payload(
        okr_metrics=okr_metrics,
        assessment=assessment,
        checkin_count=checkin_count,
    )
    if kpi_summary:
        evidence_payload["kpi_data"] = kpi_summary

    ai_service = AzureOpenAIService()
    ai_review = ai_service.generate_review(evidence_payload)

    summary = ai_review.get("summary") or (
        f"Performance review based on {okr_metrics['okr_count']} OKR(s) "
        f"with average progress of {okr_metrics['avg_progress']}%."
    )
    strengths = ai_review.get("strengths") or [f"Active engagement with {okr_metrics['okr_count']} OKR(s)"]
    improvements = ai_review.get("improvements") or ["Continue improving execution consistency."]

    # Evidence-driven score
    avg_progress = float(okr_metrics["avg_progress"])
    assessment_score = float(assessment.self_rating) if assessment and assessment.self_rating else 3.0
    score = min(5.0, max(1.0, (avg_progress / 20.0) + (assessment_score / 2.0)))

    review = Review(
        id=str(uuid.uuid4()),
        user_id=target_user_id,
        summary=summary,
        strengths=json.dumps(strengths),
        improvements=json.dumps(improvements),
        score=round(score, 1),
        status=ReviewStatus.PENDING,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    result = _parse_review(review)
    result.workflow_metadata = evidence_payload.get("workflow_metadata")
    return result


# ── Regenerate With Feedback ──────────────────────────────────────────────────

@router.post("/{review_id}/regenerate", response_model=ReviewResponse)
async def regenerate_review_with_feedback(
    review_id: str,
    request: ReviewRegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manager provides feedback instructions → AI regenerates the review.

    The original review is updated in place (same ID, same employee).
    Feedback is stored in review_feedbacks for audit trail.

    Example feedback:
      "Focus more on KPI X achievement and add clearer improvement suggestions."
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role.value != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can regenerate reviews",
        )

    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    # Store feedback for audit trail
    db.add(ReviewFeedback(
        id=str(uuid.uuid4()),
        review_id=review_id,
        feedback_text=request.feedback.strip(),
        created_by=current_user.id,
    ))
    db.flush()

    # Re-gather evidence for the target employee
    target_user_id = review.user_id
    okrs = db.query(OKR).filter(OKR.user_id == target_user_id).all()
    assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == target_user_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    checkin_count = db.query(CheckIn).filter(CheckIn.user_id == target_user_id).count()
    okr_metrics = compute_okr_progress_metrics(okrs)

    target_user = db.query(User).filter(User.id == target_user_id).first()
    target_profile = db.query(Profile).filter(Profile.user_id == target_user_id).first()
    kpi_summary = []
    if target_user and target_profile:
        kpi_summary = _get_kpi_summary(target_user.email, target_profile.company_code, db)

    evidence_payload = build_review_evidence_payload(
        okr_metrics=okr_metrics,
        assessment=assessment,
        checkin_count=checkin_count,
    )

    # Inject KPI data + manager's feedback + prior summary into the evidence
    if kpi_summary:
        evidence_payload["kpi_data"] = kpi_summary
    evidence_payload["manager_feedback"] = request.feedback.strip()
    evidence_payload["previous_summary"] = review.summary

    # Re-run AI with enriched context
    ai_service = AzureOpenAIService()
    ai_review = ai_service.generate_review(evidence_payload)

    new_summary = ai_review.get("summary") or review.summary
    new_strengths = ai_review.get("strengths") or json.loads(review.strengths)
    new_improvements = ai_review.get("improvements") or json.loads(review.improvements)

    # Update review in place (preserves same review ID)
    review.summary = new_summary
    review.strengths = json.dumps(new_strengths)
    review.improvements = json.dumps(new_improvements)
    review.status = ReviewStatus.PENDING

    db.commit()
    db.refresh(review)

    return _parse_review(review)


# ── Get Feedback History ──────────────────────────────────────────────────────

@router.get("/{review_id}/feedbacks", response_model=List[ReviewFeedbackResponse])
async def get_review_feedbacks(
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the feedback/regeneration history for a review. Managers only."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role.value != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers only")

    feedbacks = (
        db.query(ReviewFeedback)
        .filter(ReviewFeedback.review_id == review_id)
        .order_by(ReviewFeedback.created_at.asc())
        .all()
    )
    return feedbacks


# ── Update Review Status ──────────────────────────────────────────────────────

@router.put("/{review_id}/status", response_model=ReviewResponse)
async def update_review_status(
    review_id: str,
    status_data: ReviewStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager updates the status of a review (pending → submitted → completed)."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role.value != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can update review status",
        )

    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    review.status = status_data.status
    db.commit()
    db.refresh(review)

    return _parse_review(review)
