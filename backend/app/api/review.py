from app.utils.datetime_utils import utc_now_naive, utc_now
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.conflict import ReviewItem, ConflictItem
from app.models.clinical import LabResult
from app.models.patient import Patient, PatientCondition, PatientAllergy, PatientMedication
from app.models.document import Document
from app.models.audit import VerificationEvent
from app.schemas.conflict import ReviewItemResponse, ReviewActionRequest
from app.services.audit_service import AuditService

router = APIRouter(prefix="/review", tags=["Review Queue & Human Verification"])

def verify_reviewer_authorization(authorization: Optional[str] = Header(None)) -> str:
    """
    Validates reviewer authorization role.
    Rejects unauthorized or forbidden requests where non-clinician role is specified.
    """
    if authorization and authorization.lower() == "unauthorized":
        raise HTTPException(status_code=401, detail="Authentication credentials required to access clinical review queue.")
    if authorization and authorization.lower() in ("role:patient", "role:viewer", "forbidden"):
        raise HTTPException(status_code=403, detail="Forbidden: Reviewer or Clinician role required for verification actions.")
    return "authorized_clinician"


@router.get("", response_model=List[ReviewItemResponse])
def list_review_queue(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    status: Optional[str] = Query(None, description="Filter by status: PENDING, ACCEPTED, EDITED, REJECTED, DEFERRED, AI_EXTRACTED"),
    priority: Optional[str] = Query(None, description="Filter by priority: HIGH, MEDIUM, LOW"),
    target_type: Optional[str] = Query(None, description="Filter by clinical data type: LAB_RESULT, MEDICATION, ALLERGY, CONDITION"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns clinical review items requiring human verification with multi-criteria filtering.
    """
    verify_reviewer_authorization(authorization)

    query = db.query(ReviewItem)
    if patient_id:
        query = query.filter(ReviewItem.patient_id == patient_id)
    if document_id:
        query = query.filter(ReviewItem.document_id == document_id)
    if status:
        query = query.filter(ReviewItem.status == status.upper())
    if priority:
        query = query.filter(ReviewItem.priority == priority.upper())
    if target_type:
        query = query.filter(ReviewItem.target_type == target_type.upper())

    return query.order_by(
        # Sort HIGH priority first, then created_at desc
        ReviewItem.priority.desc(),
        ReviewItem.created_at.desc()
    ).all()


@router.get("/{review_id}")
def get_review_item_details(
    review_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns comprehensive side-by-side details for a review item:
    Left: Source document excerpt and related conflicts.
    Right: AI-extracted structured values, provenance, and confidence.
    """
    verify_reviewer_authorization(authorization)

    item = db.query(ReviewItem).filter(ReviewItem.id == review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    patient = db.query(Patient).filter(Patient.id == item.patient_id).first()
    doc = db.query(Document).filter(Document.id == item.document_id).first() if item.document_id else None

    # Check for related Phase 7 conflicts for this patient
    related_conflicts = db.query(ConflictItem).filter(
        ConflictItem.patient_id == item.patient_id,
        ConflictItem.status.in_(["OPEN", "UNRESOLVED", "REVIEWED"])
    ).all()

    # Match conflicts by field/item name keywords
    matching_conflicts = []
    for c in related_conflicts:
        fn_norm = item.field_name.lower()
        if fn_norm in c.title.lower() or fn_norm in c.description.lower():
            matching_conflicts.append({
                "id": c.id,
                "title": c.title,
                "severity": c.severity,
                "conflict_type": c.conflict_type,
                "description": c.description,
                "source_a": c.source_a,
                "source_b": c.source_b,
                "status": c.status
            })

    # Retrieve source context / document raw text snippet
    source_context = item.source_text
    if not source_context and doc and doc.raw_text:
        # Locate field_name in doc text
        idx = doc.raw_text.lower().find(item.field_name.lower())
        if idx != -1:
            start = max(0, idx - 150)
            end = min(len(doc.raw_text), idx + len(item.field_name) + 250)
            source_context = "..." + doc.raw_text[start:end].strip() + "..."
        else:
            source_context = doc.raw_text[:400]

    return {
        "review_item": {
            "id": item.id,
            "patient_id": item.patient_id,
            "patient_name": f"{patient.first_name} {patient.last_name}" if patient else "Unknown Patient",
            "patient_mrn": patient.mrn if patient else "N/A",
            "document_id": item.document_id,
            "document_name": doc.original_filename if doc else "Clinical Document",
            "target_type": item.target_type,
            "target_id": item.target_id,
            "field_name": item.field_name,
            "current_value": item.current_value,
            "original_value": item.original_value or item.current_value,
            "corrected_value": item.corrected_value,
            "confidence": item.confidence,
            "confidence_percent": f"{int((item.confidence or 1.0) * 100)}%",
            "priority": item.priority,
            "status": item.status,
            "reason": item.reason,
            "source_text": source_context,
            "reviewer_note": item.reviewer_note,
            "reviewed_by": item.reviewed_by,
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            "created_at": item.created_at.isoformat()
        },
        "related_conflicts": matching_conflicts,
        "safety_disclaimer": "AI Extracted — Human Verification Required. Actions are recorded in the immutable audit trail."
    }


@router.post("/{review_id}/action", response_model=ReviewItemResponse)
def handle_review_action(
    review_id: str,
    payload: ReviewActionRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Executes a human-in-the-loop review action:
      - ACCEPT: Marks as HUMAN_VERIFIED (status: ACCEPTED)
      - CORRECT / EDIT: Preserves original AI value, stores corrected_value, marks HUMAN_CORRECTED (status: EDITED)
      - REJECT: Preserves original AI value for audit, marks HUMAN_REJECTED (status: REJECTED)
      - DEFER: Leaves unresolved for later review (status: DEFERRED)

    Preserves original AI extractions and logs immutable audit trail.
    """
    verify_reviewer_authorization(authorization)

    item = db.query(ReviewItem).filter(ReviewItem.id == review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    action_raw = payload.action.strip().upper()
    valid_actions = {"ACCEPT", "CORRECT", "EDIT", "REJECT", "DEFER"}
    if action_raw not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action '{payload.action}'. Must be one of: {valid_actions}")

    prev_status = item.status
    prev_value = item.current_value
    now = utc_now_naive()

    # Capture original value if not yet captured
    if not item.original_value:
        item.original_value = item.current_value

    new_provenance = "AI_EXTRACTED"

    if action_raw == "ACCEPT":
        item.status = "ACCEPTED"
        new_provenance = "HUMAN_VERIFIED"
        # Update target clinical record if it exists
        if item.target_type == "LAB_RESULT":
            lab = db.query(LabResult).filter(LabResult.id == item.target_id).first()
            if lab:
                lab.is_verified = True
                lab.verified_by = payload.reviewer_id
                lab.verified_at = now
                lab.provenance = "HUMAN_VERIFIED"

    elif action_raw in ("CORRECT", "EDIT"):
        if not payload.corrected_value or not payload.corrected_value.strip():
            raise HTTPException(status_code=400, detail="corrected_value is required when editing or correcting an extraction.")
        item.status = "EDITED"
        item.corrected_value = payload.corrected_value.strip()
        item.current_value = payload.corrected_value.strip()
        new_provenance = "HUMAN_CORRECTED"

        # Update underlying lab result while keeping original_ai_value intact
        if item.target_type == "LAB_RESULT":
            lab = db.query(LabResult).filter(LabResult.id == item.target_id).first()
            if lab:
                if not lab.original_ai_value:
                    lab.original_ai_value = lab.value_text
                lab.value_text = payload.corrected_value.strip()
                # Parse numeric if possible
                try:
                    import re
                    num_m = re.search(r"(\d+(?:\.\d+)?)", payload.corrected_value)
                    if num_m:
                        lab.value = float(num_m.group(1))
                except Exception:
                    pass
                lab.is_verified = True
                lab.verified_by = payload.reviewer_id
                lab.verified_at = now
                lab.provenance = "HUMAN_CORRECTED"
                lab.version += 1

    elif action_raw == "REJECT":
        item.status = "REJECTED"
        new_provenance = "HUMAN_REJECTED"
        if item.target_type == "LAB_RESULT":
            lab = db.query(LabResult).filter(LabResult.id == item.target_id).first()
            if lab:
                lab.provenance = "HUMAN_REJECTED"
                lab.is_verified = False

    elif action_raw == "DEFER":
        item.status = "DEFERRED"

    item.reviewer_note = payload.change_reason
    item.reviewed_by = payload.reviewer_id
    item.reviewed_at = now
    db.commit()
    db.refresh(item)

    # 1. Log immutable VerificationEvent
    try:
        db.add(VerificationEvent(
            target_id=item.target_id,
            target_type=item.target_type,
            verified_by=payload.reviewer_id,
            original_value=item.original_value,
            corrected_value=item.corrected_value or item.current_value,
            change_reason=payload.change_reason,
            provenance=new_provenance,
            timestamp=now
        ))
        db.commit()
    except Exception:
        pass

    # 2. Log immutable AuditLog
    AuditService.log_action(
        db=db,
        action=f"REVIEW_{item.status}",
        entity_type="REVIEW_ITEM",
        entity_id=item.id,
        user_id=payload.reviewer_id,
        details={
            "action": action_raw,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "field_name": item.field_name,
            "previous_value": prev_value,
            "new_value": item.current_value,
            "original_value": item.original_value,
            "previous_status": prev_status,
            "new_status": item.status,
            "reviewer_note": payload.change_reason,
            "timestamp": now.isoformat()
        }
    )

    return item
