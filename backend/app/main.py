from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.api.v1 import (
    auth, okrs, checkins, assessments, reviews,
    team, progress, coaching,
    departments, kpi, setup,
    ai_okr,
    org_okrs,
    progress_submissions,
    one_on_ones,
    ceo_dashboard,
)
from app.core.config import settings
from app.db.database import engine, Base, SessionLocal, switch_to_sqlite
from app.db.sqlite_migrate import migrate_sqlite_profiles_role_if_needed
# Import ALL models so SQLAlchemy registers them with Base.metadata
from app.db.models import (
    User, Profile, OKR, KeyResult, CheckIn,
    Assessment, Review, ProgressHistory,
    Department, DepartmentOKR, DepartmentKeyResult,
    KPIDataset, KPIRecord,
    IntegrationConfig, ReviewFeedback,
    OrganizationOKR, OrgKeyResult,
    ProgressSubmission, OneOnOneMeeting,
)


def init_database():
    """
    Create all tables on startup.

    If the configured PostgreSQL engine fails during DDL (e.g. transient DNS
    failure after the initial probe), the module engine is swapped to SQLite
    so the app remains fully functional for local development.
    """
    from app.db import database as _db_module  # re-import to get live engine ref

    print("=" * 60)
    print("Initializing Database...")
    print("=" * 60)

    current_engine = _db_module.engine
    db_url = str(current_engine.url)
    print(f"Database URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"Database Type: {'SQLite' if db_url.startswith('sqlite') else 'PostgreSQL'}")

    try:
        Base.metadata.create_all(bind=current_engine)
        migrate_sqlite_profiles_role_if_needed(current_engine)
        print("[OK] Database tables created/verified successfully!")

        db = _db_module.SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db.commit()
            print("[OK] Database connection verified!")
        except Exception as e:
            print(f"[WARNING] Database connection test failed: {e}")
        finally:
            db.close()

    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
        if not db_url.startswith("sqlite"):
            # PostgreSQL failed after the initial probe — fall back to SQLite
            switch_to_sqlite()
            sqlite_engine = _db_module.engine
            try:
                Base.metadata.create_all(bind=sqlite_engine)
                migrate_sqlite_profiles_role_if_needed(sqlite_engine)
                print("[OK] SQLite fallback database ready.")
            except Exception as sqlite_err:
                print(f"[ERROR] SQLite fallback also failed: {sqlite_err}")
        else:
            print("[WARNING] The application will start, but database operations may fail.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    init_database()
    yield


app = FastAPI(
    title="PerformBharat API",
    description="Backend API for PerformBharat – OKRs & AI Performance Reviews",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/v1/auth",        tags=["Authentication"])
app.include_router(setup.router,       prefix="/api/v1/setup",       tags=["Setup"])
app.include_router(departments.router, prefix="/api/v1/departments",  tags=["Departments"])
app.include_router(okrs.router,        prefix="/api/v1/okrs",         tags=["OKRs"])
app.include_router(kpi.router,         prefix="/api/v1/kpi",          tags=["KPI Data"])
app.include_router(checkins.router,    prefix="/api/v1/checkins",     tags=["Check-ins"])
app.include_router(assessments.router, prefix="/api/v1/assessments",  tags=["Assessments"])
app.include_router(reviews.router,     prefix="/api/v1/reviews",      tags=["Reviews"])
app.include_router(team.router,        prefix="/api/v1/team",         tags=["Team"])
app.include_router(progress.router,    prefix="/api/v1/progress",     tags=["Progress"])
app.include_router(coaching.router,    prefix="/api/v1/coaching",     tags=["Coaching"])
app.include_router(ai_okr.router,      prefix="/api/v1/ai",            tags=["AI OKR"])
app.include_router(org_okrs.router,    prefix="/api/v1/org-okrs",      tags=["Organization OKRs"])
app.include_router(
    progress_submissions.router,
    prefix="/api/v1/progress-submissions",
    tags=["Progress submissions"],
)
app.include_router(one_on_ones.router, prefix="/api/v1/one-on-ones",   tags=["1:1 Meetings"])
app.include_router(ceo_dashboard.router, prefix="/api/v1/ceo",        tags=["CEO Dashboard"])


# ── Health Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "PerformBharat API", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
async def db_health_check():
    """Database health check with table list."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1")).scalar()
            db.close()
            db_url_display = (
                settings.DATABASE_URL.split("@")[-1]
                if "@" in settings.DATABASE_URL
                else settings.DATABASE_URL
            )
            return {
                "status": "healthy",
                "database": "connected",
                "database_url": db_url_display,
                "tables": list(Base.metadata.tables.keys()),
            }
        except Exception as e:
            return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
