from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.api.v1 import (
    auth, okrs, checkins, assessments, reviews,
    team, progress, coaching,
    departments, kpi, setup,        # NEW routers
    ai_okr,                         # AI OKR generation
)
from app.core.config import settings
from app.db.database import engine, Base, SessionLocal
# Import ALL models so SQLAlchemy registers them with Base.metadata
from app.db.models import (
    User, Profile, OKR, KeyResult, CheckIn,
    Assessment, Review, ProgressHistory,
    # New models
    Department, DepartmentOKR, DepartmentKeyResult,
    KPIDataset, KPIRecord,
    IntegrationConfig, ReviewFeedback,
)


def init_database():
    """Create all tables on startup if they don't exist."""
    print("=" * 60)
    print("Initializing Database...")
    print("=" * 60)
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Database Type: {'SQLite' if settings.DATABASE_URL.startswith('sqlite') else 'PostgreSQL'}")

    try:
        Base.metadata.create_all(bind=engine)
        print("[OK] Database tables created/verified successfully!")

        db = SessionLocal()
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
        print("[WARNING] The application will start, but database operations may fail.")
        print("[WARNING] If using Neon PostgreSQL, the host may be temporarily unreachable.")
        print("[WARNING] Requests that need the database will return 500 until connectivity is restored.")


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
