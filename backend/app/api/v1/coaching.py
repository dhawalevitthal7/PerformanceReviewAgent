from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from app.api.v1.dependencies import get_current_user
from app.db.models import User

router = APIRouter()


class CoachingTip(BaseModel):
    title: str
    description: str
    category: str


class CoachingTipsResponse(BaseModel):
    tips: List[CoachingTip]


@router.get("", response_model=CoachingTipsResponse)
async def get_coaching_tips(
    current_user: User = Depends(get_current_user)
):
    """Get personalized coaching tips."""
    # Default coaching tips - in production, use AI to generate personalized tips
    tips = [
        CoachingTip(
            title="Break large goals into weekly milestones",
            description="Instead of aiming for 500 units by quarter-end, set weekly targets of 125 units. This makes progress feel achievable and helps you catch problems early.",
            category="Goal Setting"
        ),
        CoachingTip(
            title="Document one process improvement per week",
            description="Small improvements compound. Write down one thing you improved each week — it builds your track record and helps during reviews.",
            category="Continuous Improvement"
        ),
        CoachingTip(
            title="Ask for feedback before your review",
            description="Don't wait for the formal review. Ask your manager or peers for quick feedback weekly. It helps you course-correct faster.",
            category="Communication"
        ),
    ]
    
    return CoachingTipsResponse(tips=tips)
