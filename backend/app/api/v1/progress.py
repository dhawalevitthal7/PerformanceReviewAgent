from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.db.database import get_db
from app.db.models import User, OKR, KeyResult, ProgressHistory
from app.api.v1.dependencies import get_current_user

router = APIRouter()


class ProgressDataPoint(BaseModel):
    week: str
    progress: float


class KPIDataPoint(BaseModel):
    day: str
    output: float


class ProgressResponse(BaseModel):
    progress_history: List[ProgressDataPoint]
    kpi_data: List[KPIDataPoint]


@router.get("", response_model=ProgressResponse)
async def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get progress history for the current user."""
    # Get all OKRs
    okrs = db.query(OKR).filter(OKR.user_id == current_user.id).all()
    
    # Calculate overall progress over time (simplified - using current OKRs)
    # In production, you'd track historical progress in ProgressHistory table
    progress_history = []
    if okrs:
        # Simulate 8 weeks of progress
        base_progress = 0
        for okr in okrs:
            if okr.key_results:
                kr_progresses = []
                for kr in okr.key_results:
                    if kr.target > 0:
                        if "reduce" in kr.title.lower() or "downtime" in kr.title.lower():
                            progress = min(100, max(0, (kr.target / kr.current) * 100)) if kr.current > 0 else 0
                        else:
                            progress = min(100, max(0, (kr.current / kr.target) * 100))
                        kr_progresses.append(progress)
                if kr_progresses:
                    okr_progress = sum(kr_progresses) / len(kr_progresses)
                    base_progress += okr_progress
        
        avg_progress = base_progress / len(okrs) if okrs else 0
        
        # Generate weekly progress (simplified)
        for week in range(1, 9):
            week_progress = min(100, avg_progress * (week / 8))
            progress_history.append(ProgressDataPoint(
                week=f"W{week}",
                progress=round(week_progress, 1)
            ))
    else:
        # Default progress if no OKRs
        for week in range(1, 9):
            progress_history.append(ProgressDataPoint(
                week=f"W{week}",
                progress=week * 10
            ))
    
    # Generate KPI data (simplified - in production, use actual data)
    kpi_data = [
        KPIDataPoint(day="Mon", output=92),
        KPIDataPoint(day="Tue", output=105),
        KPIDataPoint(day="Wed", output=88),
        KPIDataPoint(day="Thu", output=110),
        KPIDataPoint(day="Fri", output=95),
    ]
    
    return ProgressResponse(
        progress_history=progress_history,
        kpi_data=kpi_data
    )
