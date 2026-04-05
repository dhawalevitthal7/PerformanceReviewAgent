from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.db.database import Base


class UserRole(str, enum.Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    CEO = "ceo"


class CheckInMood(str, enum.Enum):
    GREAT = "great"
    GOOD = "good"
    OKAY = "okay"
    STRUGGLING = "struggling"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class SubmissionStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    OVERRIDDEN = "overridden"


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Store role as VARCHAR of enum *values* (employee, manager, ceo) with no SQLite CHECK
# so adding CEO does not require migrating old CHECK constraints on existing dev DBs.
_USER_ROLE_STR = SQLEnum(
    UserRole,
    native_enum=False,
    length=32,
    values_callable=lambda x: [e.value for e in x],
    validate_strings=True,
    create_constraint=False,
)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    profile = relationship("Profile", back_populates="user", uselist=False)
    okrs = relationship(
        "OKR", back_populates="user",
        foreign_keys="OKR.user_id",
        cascade="all, delete-orphan",
    )
    checkins = relationship("CheckIn", back_populates="user", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship(
        "Review", back_populates="user",
        foreign_keys="Review.user_id",
        cascade="all, delete-orphan",
    )


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(_USER_ROLE_STR, nullable=False)
    department = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    company_code = Column(String, nullable=False)
    # New: links employee to a Department row (set on first login)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    # New: tracks whether the user completed first-login setup
    is_setup_done = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profile")
    department_rel = relationship("Department", foreign_keys=[department_id])


class Department(Base):
    """A department within a company, created by a Manager."""
    __tablename__ = "departments"

    id = Column(String, primary_key=True, index=True)
    company_code = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    manager_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dept_okrs = relationship("DepartmentOKR", back_populates="department",
                             cascade="all, delete-orphan")


class OrganizationOKR(Base):
    """Company-level OKR owned by the CEO tier."""
    __tablename__ = "organization_okrs"

    id = Column(String, primary_key=True, index=True)
    company_code = Column(String, nullable=False, index=True)
    objective = Column(Text, nullable=False)
    quarter = Column(String, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    key_results = relationship("OrgKeyResult", back_populates="org_okr",
                               cascade="all, delete-orphan")
    dept_children = relationship("DepartmentOKR", back_populates="parent_org_okr")


class OrgKeyResult(Base):
    __tablename__ = "org_key_results"

    id = Column(String, primary_key=True, index=True)
    org_okr_id = Column(String, ForeignKey("organization_okrs.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    title = Column(String, nullable=False)
    target = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    org_okr = relationship("OrganizationOKR", back_populates="key_results")


class DepartmentOKR(Base):
    """Quarterly OKR defined by a Manager at the department level."""
    __tablename__ = "department_okrs"

    id = Column(String, primary_key=True, index=True)
    department_id = Column(String, ForeignKey("departments.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    objective = Column(Text, nullable=False)
    quarter = Column(String, nullable=False)   # e.g. "Q2-2025"
    due_date = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    parent_org_okr_id = Column(String, ForeignKey("organization_okrs.id"), nullable=True)
    parent_org_okr = relationship("OrganizationOKR", back_populates="dept_children")

    department = relationship("Department", back_populates="dept_okrs")
    key_results = relationship("DepartmentKeyResult", back_populates="dept_okr",
                               cascade="all, delete-orphan")


class DepartmentKeyResult(Base):
    """Key result under a Department OKR."""
    __tablename__ = "department_key_results"

    id = Column(String, primary_key=True, index=True)
    dept_okr_id = Column(String, ForeignKey("department_okrs.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    title = Column(String, nullable=False)
    target = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dept_okr = relationship("DepartmentOKR", back_populates="key_results")


class OKR(Base):
    __tablename__ = "okrs"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    objective = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # New: optional link to a parent Department OKR for cascading
    parent_dept_okr_id = Column(String, ForeignKey("department_okrs.id"), nullable=True)
    assigned_by = Column(String, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="okrs", foreign_keys=[user_id])
    key_results = relationship("KeyResult", back_populates="okr", cascade="all, delete-orphan")
    parent_dept_okr = relationship("DepartmentOKR", foreign_keys=[parent_dept_okr_id])


class KeyResult(Base):
    __tablename__ = "key_results"

    id = Column(String, primary_key=True, index=True)
    okr_id = Column(String, ForeignKey("okrs.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    target = Column(Float, nullable=False)
    current = Column(Float, default=0.0)
    unit = Column(String, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    okr = relationship("OKR", back_populates="key_results")


class CheckIn(Base):
    __tablename__ = "checkins"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    note = Column(Text, nullable=False)
    mood = Column(SQLEnum(CheckInMood), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="checkins")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    self_rating = Column(Integer, nullable=False)
    strengths = Column(Text, nullable=False)
    improvements = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="assessments")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    strengths = Column(Text, nullable=False)        # JSON array stored as text
    improvements = Column(Text, nullable=False)     # JSON array stored as text
    score = Column(Float, nullable=False)
    status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING)
    manager_rating = Column(Float, nullable=True)
    manager_rating_note = Column(Text, nullable=True)
    manager_rated_by = Column(String, ForeignKey("users.id"), nullable=True)
    manager_rated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="reviews", foreign_keys=[user_id])
    feedbacks = relationship("ReviewFeedback", back_populates="review",
                             cascade="all, delete-orphan")


class ReviewFeedback(Base):
    """
    Manager feedback used to trigger AI review regeneration.
    Stored for audit trail — each regeneration creates a new row.
    """
    __tablename__ = "review_feedbacks"

    id = Column(String, primary_key=True, index=True)
    review_id = Column(String, ForeignKey("reviews.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    feedback_text = Column(Text, nullable=False)    # Manager's instruction
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    review = relationship("Review", back_populates="feedbacks")


class KPIDataset(Base):
    """Metadata for an uploaded KPI CSV file."""
    __tablename__ = "kpi_datasets"

    id = Column(String, primary_key=True, index=True)
    company_code = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    records = relationship("KPIRecord", back_populates="dataset",
                           cascade="all, delete-orphan")


class KPIRecord(Base):
    """A single row from an uploaded KPI CSV, parsed into structured columns."""
    __tablename__ = "kpi_records"

    id = Column(String, primary_key=True, index=True)
    dataset_id = Column(String, ForeignKey("kpi_datasets.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    # Employee matched by email (aligned with User.email)
    employee_email = Column(String, nullable=True, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=True)      # numeric KPIs
    metric_text = Column(Text, nullable=True)        # text KPIs (e.g. ratings)
    period = Column(String, nullable=True)           # e.g. "Q1-2025" or "March"
    raw_row = Column(Text, nullable=True)            # original CSV row as JSON string

    dataset = relationship("KPIDataset", back_populates="records")


class ProgressSubmission(Base):
    __tablename__ = "progress_submissions"

    id = Column(String, primary_key=True, index=True)
    key_result_id = Column(String, ForeignKey("key_results.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    submitted_by = Column(String, ForeignKey("users.id"), nullable=False)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    employee_value = Column(Float, nullable=False)
    manager_value = Column(Float, nullable=True)
    employee_note = Column(Text, nullable=True)
    manager_note = Column(Text, nullable=True)
    status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.PENDING_REVIEW)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    key_result = relationship("KeyResult")


class OneOnOneMeeting(Base):
    __tablename__ = "one_on_one_meetings"

    id = Column(String, primary_key=True, index=True)
    manager_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    employee_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    agenda = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    action_items = Column(Text, nullable=True)
    status = Column(SQLEnum(MeetingStatus), default=MeetingStatus.SCHEDULED)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class IntegrationConfig(Base):
    """
    API credentials for an external tool (Jira, BambooHR, etc.)
    scoped to a company. One row per tool per company.
    """
    __tablename__ = "integration_configs"

    id = Column(String, primary_key=True, index=True)
    company_code = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)   # "jira" | "bamboohr"
    base_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ProgressHistory(Base):
    __tablename__ = "progress_history"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    okr_id = Column(String, ForeignKey("okrs.id", ondelete="CASCADE"), nullable=True, index=True)
    progress_percentage = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
