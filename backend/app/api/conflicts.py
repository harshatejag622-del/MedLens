from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.conflict import ConflictItem
from app.models.patient import Patient
from app.schemas.conflict import ConflictResponse, ConflictResolveRequest
from app.services.audit_service import AuditService
from app.services.conflict_detector import ConflictDetector

router = APIRouter(prefix="/conflicts", tags=["Conflicts & Inconsistencies"])

@router.get("", response_model=List[ConflictResponse])
def list_conflicts(
    patient_id: Optional[str] = Query(None, description="Filter conflicts by Patient ID"),
    status: Optional[str] = Query(None, description="Filter by status: OPEN, REVIEWED, RESOLVED, DISMISSED, UNRESOLVED"),
    db: Session = Depends(get_db)
):
    """
    Returns clinical conflicts and inconsistencies with optional patient and status filters.
    """
    query = db.query(ConflictItem)
    if patient_id:
        query = query.filter(ConflictItem.patient_id == patient_id)
    if status:
        query = query.filter(ConflictItem.status == status.upper())
    return query.order_by(ConflictItem.created_at.desc()).all()


@router.post("/detect/{patient_id}", response_model=List[ConflictResponse])
def run_conflict_detection(
    patient_id: str,
    db: Session = Depends(get_db)
):
    """
    Triggers automated clinical data consistency and contradiction analysis for a patient.
    Evaluates medication discrepancies, allergy contraindications, diagnosis conflicts,
    laboratory anomalies, and demographic mismatches.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    conflicts = ConflictDetector.detect_all_conflicts(db, patient_id)

    AuditService.log_action(
        db=db,
        action="CONFLICT_DETECTION_RUN",
        entity_type="PATIENT",
        entity_id=patient_id,
        user_id="clinician_user",
        details={"conflicts_count": len(conflicts)}
    )

    return conflicts


@router.post("/{conflict_id}/resolve", response_model=ConflictResponse)
def resolve_conflict(
    conflict_id: str,
    payload: ConflictResolveRequest,
    db: Session = Depends(get_db)
):
    """
    Allows an authorized clinician to review, resolve, or dismiss a detected conflict.
    Logs an immutable audit trail entry with previous and new status.
    Does NOT modify the underlying source data.
    """
    conflict = db.query(ConflictItem).filter(ConflictItem.id == conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict item not found")

    prev_status = conflict.status
    new_status = payload.new_status.upper()
    if new_status not in ("OPEN", "REVIEWED", "RESOLVED", "DISMISSED"):
        new_status = "RESOLVED"

    conflict.status = new_status
    conflict.resolution_notes = payload.resolution_notes
    conflict.resolved_by = payload.resolved_by
    conflict.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(conflict)

    AuditService.log_action(
        db=db,
        action="CONFLICT_STATUS_UPDATED",
        entity_type="CONFLICT",
        entity_id=conflict.id,
        user_id=payload.resolved_by,
        details={
            "previous_status": prev_status,
            "new_status": conflict.status,
            "reviewer_notes": payload.resolution_notes
        }
    )

    return conflict
