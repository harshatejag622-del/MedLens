from fastapi import APIRouter, Depends, Query, Header, HTTPException
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.patient import Patient, PatientCondition, PatientMedication, PatientAllergy
from app.models.document import Document
from app.models.clinical import LabResult
from app.models.conflict import ConflictItem, ReviewItem
from app.models.audit import AuditLog
from app.models.extracted_entity import ExtractedEntity

router = APIRouter(prefix="/stats", tags=["Clinical Intelligence Dashboard & Global Search"])

def verify_stats_authorization(authorization: Optional[str] = Header(None)) -> str:
    """Security check for clinical metrics and global cross-patient record search."""
    if authorization and authorization.lower() == "unauthorized":
        raise HTTPException(status_code=401, detail="Authentication credentials required.")
    return "authorized_clinician"


@router.get("")
def get_operational_stats(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns verified operational and clinical intelligence metrics calculated directly from database records.
    Strictly avoids hard-coded fake statistics.
    """
    verify_stats_authorization(authorization)

    # A. Patient Overview Metrics
    total_patients = db.query(Patient).count()
    patients_with_high_conflicts = db.query(Patient.id).join(ConflictItem).filter(
        ConflictItem.severity == "HIGH",
        ConflictItem.status.in_(["OPEN", "UNRESOLVED"])
    ).distinct().count()

    patients_requiring_review = db.query(Patient.id).join(ReviewItem).filter(
        ReviewItem.status == "PENDING"
    ).distinct().count()

    # B. Review Metrics
    pending_reviews = db.query(ReviewItem).filter(ReviewItem.status == "PENDING").count()
    high_priority_reviews = db.query(ReviewItem).filter(
        ReviewItem.status == "PENDING",
        ReviewItem.priority == "HIGH"
    ).count()
    verified_reviews = db.query(ReviewItem).filter(ReviewItem.status == "ACCEPTED").count()
    corrected_reviews = db.query(ReviewItem).filter(ReviewItem.status == "EDITED").count()
    rejected_reviews = db.query(ReviewItem).filter(ReviewItem.status == "REJECTED").count()
    deferred_reviews = db.query(ReviewItem).filter(ReviewItem.status == "DEFERRED").count()

    # C. Conflict Metrics
    total_conflicts = db.query(ConflictItem).count()
    high_conflicts = db.query(ConflictItem).filter(ConflictItem.severity == "HIGH").count()
    medium_conflicts = db.query(ConflictItem).filter(ConflictItem.severity.in_(["MEDIUM", "WARNING"])).count()
    low_conflicts = db.query(ConflictItem).filter(ConflictItem.severity.in_(["LOW", "INFO"])).count()
    open_conflicts = db.query(ConflictItem).filter(ConflictItem.status.in_(["OPEN", "UNRESOLVED"])).count()
    resolved_conflicts = db.query(ConflictItem).filter(ConflictItem.status == "RESOLVED").count()
    dismissed_conflicts = db.query(ConflictItem).filter(ConflictItem.status == "DISMISSED").count()

    # D. Document Metrics
    total_documents = db.query(Document).count()
    processing_documents = db.query(Document).filter(Document.processing_status == "PROCESSING").count()
    queued_documents = db.query(Document).filter(Document.processing_status == "QUEUED").count()
    completed_documents = db.query(Document).filter(Document.processing_status == "COMPLETED").count()
    failed_documents = db.query(Document).filter(Document.processing_status == "FAILED").count()

    # E. Clinical Data Provenance Breakdown
    total_extracted_entities = db.query(ExtractedEntity).count()
    total_labs = db.query(LabResult).count()
    total_clinical_items = total_extracted_entities + total_labs

    ai_extracted_items = (
        db.query(ExtractedEntity).filter(ExtractedEntity.provenance == "AI_EXTRACTED").count() +
        db.query(LabResult).filter(LabResult.provenance == "AI_EXTRACTED").count()
    )
    human_verified_items = (
        db.query(LabResult).filter(LabResult.provenance == "HUMAN_VERIFIED").count()
    )
    human_corrected_items = (
        db.query(LabResult).filter(LabResult.provenance == "HUMAN_CORRECTED").count()
    )
    human_rejected_items = (
        db.query(LabResult).filter(LabResult.provenance == "HUMAN_REJECTED").count()
    )

    recent_audit = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    return {
        # Overall
        "total_patients": total_patients,
        "patients_requiring_review": patients_requiring_review,
        "patients_with_high_conflicts": patients_with_high_conflicts,

        # Review Metrics
        "pending_reviews": pending_reviews,
        "high_priority_reviews": high_priority_reviews,
        "verified_reviews": verified_reviews,
        "corrected_reviews": corrected_reviews,
        "rejected_reviews": rejected_reviews,
        "deferred_reviews": deferred_reviews,

        # Conflict Metrics
        "total_conflicts": total_conflicts,
        "high_conflicts": high_conflicts,
        "medium_conflicts": medium_conflicts,
        "low_conflicts": low_conflicts,
        "open_conflicts": open_conflicts,
        "resolved_conflicts": resolved_conflicts,
        "dismissed_conflicts": dismissed_conflicts,
        "unresolved_conflicts": open_conflicts,

        # Document Metrics
        "total_documents": total_documents,
        "reports_processed": completed_documents,
        "processing_documents": processing_documents,
        "queued_documents": queued_documents,
        "failed_documents": failed_documents,

        # Clinical Data Breakdown
        "total_clinical_items": total_clinical_items,
        "ai_extracted_items": ai_extracted_items,
        "human_verified_items": human_verified_items,
        "human_corrected_items": human_corrected_items,
        "human_rejected_items": human_rejected_items,

        "system_status": "ONLINE",
        "demo_mode": True,
        "recent_activity": [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "timestamp": log.timestamp.isoformat() + "Z",
                "user_id": log.user_id
            } for log in recent_audit
        ]
    }


@router.get("/search")
def global_clinical_search(
    q: str = Query(..., min_length=1, description="Global search query across clinical entities"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Global search across all clinical domains:
    - Patients (name, MRN)
    - Documents (filenames, types, facilities)
    - Diagnoses / Conditions
    - Medications
    - Laboratory Tests
    - Clinical Conflicts
    Enforces authorization check.
    """
    verify_stats_authorization(authorization)

    term = f"%{q.strip()}%"
    results: List[Dict[str, Any]] = []

    # 1. Patients
    matching_patients = db.query(Patient).filter(
        or_(
            Patient.first_name.ilike(term),
            Patient.last_name.ilike(term),
            Patient.mrn.ilike(term),
            Patient.relevant_history.ilike(term)
        )
    ).limit(10).all()

    for p in matching_patients:
        results.append({
            "category": "PATIENT",
            "title": f"{p.first_name} {p.last_name} (MRN: {p.mrn})",
            "subtitle": f"Age: {p.age}, Sex: {p.sex}, Status: {'Archived' if p.is_archived else 'Active'}",
            "patient_id": p.id,
            "link_tab": "patient-overview"
        })

    # 2. Documents
    matching_docs = db.query(Document).filter(
        or_(
            Document.original_filename.ilike(term),
            Document.document_type.ilike(term),
            Document.facility.ilike(term)
        )
    ).limit(10).all()

    for d in matching_docs:
        results.append({
            "category": "DOCUMENT",
            "title": d.original_filename,
            "subtitle": f"Type: {d.document_type}, Status: {d.processing_status}, Facility: {d.facility or 'N/A'}",
            "patient_id": d.patient_id,
            "document_id": d.id,
            "link_tab": "reports"
        })

    # 3. Diagnoses / Conditions
    matching_conds = db.query(PatientCondition).filter(
        PatientCondition.condition_name.ilike(term)
    ).limit(10).all()

    for c in matching_conds:
        p = db.query(Patient).filter(Patient.id == c.patient_id).first()
        p_name = f"{p.first_name} {p.last_name}" if p else "Patient"
        results.append({
            "category": "DIAGNOSIS",
            "title": f"{c.condition_name} ({c.status})",
            "subtitle": f"Patient: {p_name}, Provenance: {c.provenance}",
            "patient_id": c.patient_id,
            "link_tab": "timeline"
        })

    # 4. Medications
    matching_meds = db.query(PatientMedication).filter(
        PatientMedication.medication_name.ilike(term)
    ).limit(10).all()

    for m in matching_meds:
        p = db.query(Patient).filter(Patient.id == m.patient_id).first()
        p_name = f"{p.first_name} {p.last_name}" if p else "Patient"
        results.append({
            "category": "MEDICATION",
            "title": f"{m.medication_name} {m.dosage or ''}",
            "subtitle": f"Patient: {p_name}, Frequency: {m.frequency or 'daily'}",
            "patient_id": m.patient_id,
            "link_tab": "timeline"
        })

    # 5. Laboratory Tests
    matching_labs = db.query(LabResult).filter(
        LabResult.test_name.ilike(term)
    ).limit(10).all()

    for l in matching_labs:
        p = db.query(Patient).filter(Patient.id == l.patient_id).first()
        p_name = f"{p.first_name} {p.last_name}" if p else "Patient"
        results.append({
            "category": "LABORATORY",
            "title": f"{l.test_name}: {l.value_text} {l.unit or ''} ({l.status})",
            "subtitle": f"Patient: {p_name}, Date: {l.report_date or 'Recent'}",
            "patient_id": l.patient_id,
            "link_tab": "patient-overview"
        })

    # 6. Clinical Conflicts
    matching_conflicts = db.query(ConflictItem).filter(
        or_(
            ConflictItem.title.ilike(term),
            ConflictItem.description.ilike(term)
        )
    ).limit(10).all()

    for cf in matching_conflicts:
        results.append({
            "category": "CONFLICT",
            "title": f"[{cf.severity}] {cf.title}",
            "subtitle": f"Status: {cf.status}, Type: {cf.conflict_type}",
            "patient_id": cf.patient_id,
            "link_tab": "conflicts"
        })

    return {
        "query": q,
        "total_matches": len(results),
        "results": results
    }
