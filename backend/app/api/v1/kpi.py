"""
KPI Data API
============
Handles CSV upload and retrieval of KPI records.
Only managers can upload; managers can query any employee, employees query own data.

Endpoints:
  POST /kpi/upload                       - Manager uploads a KPI CSV
  GET  /kpi/datasets                     - List all uploaded datasets for company
  GET  /kpi/datasets/{dataset_id}        - Get records for a specific dataset
  GET  /kpi/employee/{email}             - Get all KPI records for a specific employee
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from app.db.database import get_db
from app.db.models import KPIDataset, KPIRecord, Profile, User, UserRole
from app.api.v1.dependencies import get_current_user
from app.services.csv_parser import parse_kpi_csv

router = APIRouter()

MAX_CSV_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class KPIDatasetResponse(BaseModel):
    id: str
    filename: str
    company_code: str
    uploaded_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class KPIRecordResponse(BaseModel):
    id: str
    employee_email: Optional[str] = None
    metric_name: str
    metric_value: Optional[float] = None
    metric_text: Optional[str] = None
    period: Optional[str] = None

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_manager(current_user: User, db: Session) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role != UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can perform this action",
        )
    return profile


def _get_company_dataset_ids(company_code: str, db: Session) -> list[str]:
    """Return all dataset IDs that belong to a company."""
    datasets = db.query(KPIDataset).filter(
        KPIDataset.company_code == company_code
    ).all()
    return [d.id for d in datasets]


# ── Upload Endpoint ───────────────────────────────────────────────────────────

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_kpi_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manager uploads a KPI CSV file.
    The file is parsed automatically using smart column detection.

    Supported CSV headers (flexible naming):
      employee_email | metric_name | metric_value | period

    Returns the number of rows parsed.
    """
    profile = _require_manager(current_user, db)

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted",
        )

    content = await file.read()

    if len(content) > MAX_CSV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5 MB.",
        )

    # Create the dataset metadata record first
    dataset_id = str(uuid.uuid4())
    dataset = KPIDataset(
        id=dataset_id,
        company_code=profile.company_code,
        filename=file.filename or "upload.csv",
        uploaded_by=current_user.id,
    )
    db.add(dataset)
    db.flush()

    # Parse the CSV into structured records
    try:
        records = parse_kpi_csv(content, dataset_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV parsing failed: {exc}",
        )

    # Bulk-insert all records
    for rec in records:
        db.add(KPIRecord(**rec))

    db.commit()

    return {
        "message": "KPI CSV uploaded and parsed successfully",
        "dataset_id": dataset_id,
        "filename": file.filename,
        "rows_parsed": len(records),
    }


# ── Dataset Listing ───────────────────────────────────────────────────────────

@router.get("/datasets", response_model=List[KPIDatasetResponse])
async def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all KPI datasets uploaded for the current user's company."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    datasets = (
        db.query(KPIDataset)
        .filter(KPIDataset.company_code == profile.company_code)
        .order_by(KPIDataset.created_at.desc())
        .all()
    )
    return datasets


@router.get("/datasets/{dataset_id}", response_model=List[KPIRecordResponse])
async def get_dataset_records(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all KPI records for a specific dataset. Managers only."""
    _require_manager(current_user, db)

    records = (
        db.query(KPIRecord)
        .filter(KPIRecord.dataset_id == dataset_id)
        .all()
    )
    return records


# ── Per-Employee KPI Query ────────────────────────────────────────────────────

@router.get("/employee/{email:path}", response_model=List[KPIRecordResponse])
async def get_kpi_for_employee(
    email: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all KPI records for a specific employee email.
    - Managers can query any employee in their company.
    - Employees can only query their own email.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    current_user_record = db.query(User).filter(User.id == current_user.id).first()

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    is_manager = profile.role == UserRole.MANAGER

    # Employees can only view their own KPI data
    if not is_manager and current_user_record.email.lower() != email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own KPI data",
        )

    dataset_ids = _get_company_dataset_ids(profile.company_code, db)
    if not dataset_ids:
        return []

    records = (
        db.query(KPIRecord)
        .filter(
            KPIRecord.dataset_id.in_(dataset_ids),
            KPIRecord.employee_email == email.lower(),
        )
        .order_by(KPIRecord.period)
        .all()
    )
    return records
