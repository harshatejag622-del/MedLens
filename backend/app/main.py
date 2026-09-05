from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.demo_data.seeder import seed_database
import app.models # Register all models

# Import Routers
from app.api.health import router as health_router
from app.api.patients import router as patients_router
from app.api.stats import router as stats_router
from app.api.conflicts import router as conflicts_router
from app.api.review import router as review_router
from app.api.documents import router as documents_router
from app.api.audit import router as audit_router
from app.api.timeline import router as timeline_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    Base.metadata.create_all(bind=engine)
    if settings.DEMO_MODE:
        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
    yield
    # Shutdown logic (if any)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "MedLens is an AI-assisted clinical information organization and understanding platform. "
        "It transforms fragmented medical reports into structured, traceable, reviewable records. "
        "MedLens does NOT diagnose or prescribe treatment."
    ),
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG or settings.DEMO_MODE else None,
    redoc_url="/redoc" if settings.DEBUG or settings.DEMO_MODE else None
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG or settings.DEMO_MODE else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(health_router)
app.include_router(stats_router, prefix=settings.API_V1_STR)
app.include_router(patients_router, prefix=settings.API_V1_STR)
app.include_router(conflicts_router, prefix=settings.API_V1_STR)
app.include_router(review_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(timeline_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "status": "OPERATIONAL",
        "disclaimer": "MedLens is an information organization tool. It does not provide medical diagnosis or treatment recommendations."
    }
