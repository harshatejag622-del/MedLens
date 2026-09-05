from app.utils.datetime_utils import utc_now_naive, utc_now
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings

router = APIRouter(tags=["Health & Monitoring"])

@router.get("/health")
def health_check():
    """
    Liveness probe: verifies the MedLens API process is running.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": utc_now_naive().isoformat() + "Z"
    }

@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe: verifies database connectivity and core service readiness.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "ai_provider": settings.AI_PROVIDER,
            "demo_mode": settings.DEMO_MODE,
            "timestamp": utc_now_naive().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: Database connection failed. Error: {str(e)}"
        )
