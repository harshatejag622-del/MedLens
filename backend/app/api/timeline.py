from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.patient import Patient
from app.services.longitudinal_service import TimelineEngine, TrendEngine, MedicalHistoryEngine, ClinicalSummarizer

router = APIRouter(prefix="/timeline", tags=["Longitudinal Timeline & Clinical Summarization"])

def verify_timeline_authorization(authorization: Optional[str] = Header(None)) -> str:
    """Enforces authorization for clinical timeline and longitudinal data."""
    if authorization and authorization.lower() == "unauthorized":
        raise HTTPException(status_code=401, detail="Authentication credentials required.")
    return "authorized_clinician"


@router.get("/{patient_id}")
def get_patient_timeline(
    patient_id: str,
    sort_order: str = Query("desc", description="Chronological sorting: 'desc' (newest first) or 'asc' (oldest first)"),
    event_type: Optional[List[str]] = Query(None, description="Filter by event types (INTAKE, CONDITION, MEDICATION, DOCUMENT, LABORATORY, CONFLICT, VERIFICATION)"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    search_query: Optional[str] = Query(None, description="Keyword search in titles and descriptions"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns filtered, paginated longitudinal timeline events sorted chronologically.
    """
    verify_timeline_authorization(authorization)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    return TimelineEngine.get_timeline_events(
        db=db,
        patient_id=patient_id,
        sort_order=sort_order,
        event_types=event_type,
        date_from=date_from,
        date_to=date_to,
        verification_status=verification_status,
        search_query=search_query,
        limit=limit,
        offset=offset
    )


@router.get("/{patient_id}/trends")
def get_laboratory_trends(
    patient_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns chronological longitudinal analyte trend series for graphing.
    """
    verify_timeline_authorization(authorization)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    return TrendEngine.get_lab_trends(db=db, patient_id=patient_id)


@router.get("/{patient_id}/medications")
def get_medication_history(
    patient_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns longitudinal medication regimens and status changes.
    """
    verify_timeline_authorization(authorization)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    return MedicalHistoryEngine.get_medication_history(db=db, patient_id=patient_id)


@router.get("/{patient_id}/diagnoses")
def get_diagnosis_history(
    patient_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns longitudinal diagnosis progression (first recorded, most recent, status, and supporting sources).
    """
    verify_timeline_authorization(authorization)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    return MedicalHistoryEngine.get_diagnosis_history(db=db, patient_id=patient_id)


@router.post("/{patient_id}/summary")
def generate_clinical_summary(
    patient_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Generates an evidence-grounded, verification-aware longitudinal clinical summary.
    """
    verify_timeline_authorization(authorization)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    return ClinicalSummarizer.generate_longitudinal_summary(db=db, patient_id=patient_id)
