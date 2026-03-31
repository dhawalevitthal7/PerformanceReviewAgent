"""
Authentication endpoints: signup, signin, current-user, company-departments,
and demo-user provisioning.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import timedelta
import uuid

from app.db.database import get_db
from app.db.models import User, Profile, UserRole, Department
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.api.v1.dependencies import get_current_user

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_department_name(name: str) -> str:
    """Strip and title-case a department name for consistent storage."""
    return name.strip().title() if name else ""


def _company_code_from_email(email: str) -> str:
    """Derive a company code from the email domain (part after @)."""
    return email.split("@")[-1].lower()


def _ensure_department_link_for_profile(
    profile: Profile, db: Session, email: str
) -> None:
    """
    Make sure profile.department_id is populated and is_setup_done is True
    for employees who already typed a department name during signup.
    Uses case-insensitive matching.
    """
    if profile.department_id and profile.is_setup_done:
        return  # already linked

    dept_text = _normalize_department_name(profile.department or "")
    if not dept_text:
        return  # nothing to link

    company_code = _company_code_from_email(email)

    dept = (
        db.query(Department)
        .filter(
            Department.company_code == company_code,
            sa_func.lower(Department.name) == dept_text.lower(),
        )
        .first()
    )

    if dept:
        profile.department_id = dept.id
        profile.department = dept.name  # normalise casing
        profile.is_setup_done = True
        db.commit()
        db.refresh(profile)
    elif profile.role == UserRole.EMPLOYEE:
        # Employee typed a department that doesn't exist yet — auto-create it
        dept = Department(
            id=str(uuid.uuid4()),
            name=dept_text,
            company_code=company_code,
            created_by=profile.user_id,
        )
        db.add(dept)
        db.flush()
        profile.department_id = dept.id
        profile.is_setup_done = True
        db.commit()
        db.refresh(profile)


def _link_profile_by_department_id(
    profile: Profile, department_id: str, db: Session
) -> None:
    """Directly link a profile to a known department row."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return
    profile.department_id = dept.id
    profile.department = dept.name
    profile.is_setup_done = True
    db.commit()
    db.refresh(profile)


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole
    department: str = ""
    department_id: Optional[str] = None
    company_name: str
    company_code: str = ""  # optional — derived from email if blank


class UserSignIn(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str

    class Config:
        from_attributes = True


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    role: UserRole
    department: str
    company_name: str
    company_code: str
    department_id: Optional[str] = None
    is_setup_done: bool = False

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    user: UserResponse
    profile: ProfileResponse
    token: Token


class DepartmentItem(BaseModel):
    id: str
    name: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignUp, db: Session = Depends(get_db)):
    """Register a new user with optional department linking."""
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    company_code = (
        user_data.company_code.strip()
        if user_data.company_code and user_data.company_code.strip()
        else _company_code_from_email(user_data.email)
    )
    dept_text = _normalize_department_name(user_data.department)

    # Validation: employee must have either department_id or department text
    if user_data.role == UserRole.EMPLOYEE and not user_data.department_id and not dept_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department is required for employees.",
        )

    # Create user
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user_data.password)
    user = User(id=user_id, email=user_data.email, hashed_password=hashed_password)
    db.add(user)
    db.flush()

    # Create profile
    profile_id = str(uuid.uuid4())
    profile = Profile(
        id=profile_id,
        user_id=user_id,
        full_name=user_data.full_name,
        role=user_data.role,
        department=dept_text,
        company_name=user_data.company_name,
        company_code=company_code,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    db.refresh(profile)

    # Link department
    if user_data.department_id:
        _link_profile_by_department_id(profile, user_data.department_id, db)
    elif dept_text:
        _ensure_department_link_for_profile(profile, db, user_data.email)

    # Create access token
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return AuthResponse(
        user=UserResponse.model_validate(user),
        profile=ProfileResponse.model_validate(profile),
        token=Token(access_token=access_token),
    )


@router.post("/signin", response_model=AuthResponse)
async def signin(credentials: UserSignIn, db: Session = Depends(get_db)):
    """Authenticate and return token. Auto-links department on the fly."""
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    # Back-fill department link for legacy profiles
    _ensure_department_link_for_profile(profile, db, user.email)

    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return AuthResponse(
        user=UserResponse.model_validate(user),
        profile=ProfileResponse.model_validate(profile),
        token=Token(access_token=access_token),
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user information."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    access_token = create_access_token(
        data={"sub": current_user.id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return AuthResponse(
        user=UserResponse.model_validate(current_user),
        profile=ProfileResponse.model_validate(profile),
        token=Token(access_token=access_token),
    )


@router.get("/company-departments", response_model=List[DepartmentItem])
async def company_departments(
    email_domain: str = Query(..., description="Email domain, e.g. acme.com"),
    db: Session = Depends(get_db),
):
    """
    Public endpoint: returns departments for a given email domain.
    Used during employee signup to show a dropdown.
    """
    depts = (
        db.query(Department)
        .filter(Department.company_code == email_domain.lower())
        .order_by(Department.name)
        .all()
    )
    return [DepartmentItem(id=d.id, name=d.name) for d in depts]


@router.post("/demo-setup")
async def demo_setup(db: Session = Depends(get_db)):
    """Create demo employee + manager if they don't already exist."""
    created = []
    for role_str, name in [("employee", "Demo Employee"), ("manager", "Demo Manager")]:
        email = f"{role_str}@demo.com"
        if db.query(User).filter(User.email == email).first():
            continue
        uid = str(uuid.uuid4())
        user = User(
            id=uid,
            email=email,
            hashed_password=get_password_hash("demo123"),
        )
        db.add(user)
        db.flush()
        profile = Profile(
            id=str(uuid.uuid4()),
            user_id=uid,
            full_name=name,
            role=UserRole(role_str),
            department="Demo Department",
            company_name="Demo Inc",
            company_code="demo.com",
            is_setup_done=True,
        )
        db.add(profile)
        created.append(email)
    db.commit()
    return {"created": created, "message": "Demo users ready"}
