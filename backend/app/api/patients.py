import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.database import get_db
from app.models.patient import (
    Patient,
    PatientCondition,
    PatientAllergy,
    PatientMedication,
    PatientSymptom
)
from app.models.document import Document
from app.models.clinical import LabResult, Summary, Observation
from app.models.conflict import ConflictItem
from app.schemas.patient import (
    PatientResponse,
    PatientCreate,
    PatientUpdate,
    PatientOverviewResponse,
    DocumentOverviewItem,
    LabResultOverviewItem,
    ConflictOverviewItem,
    SummaryOverviewItem,
    TimelineEventOverviewItem
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.get("", response_model=List[PatientResponse])
def list_patients(
    search: Optional[str] = Query(None, description="Search across MRN, first name, last name, notes, history"),
    sex: Optional[str] = Query(None, description="Filter by sex (MALE, FEMALE, OTHER, UNKNOWN)"),
    age_min: Optional[int] = Query(None, ge=0, description="Minimum age filter"),
    age_max: Optional[int] = Query(None, le=130, description="Maximum age filter"),
    status: Optional[str] = Query(None, description="Status: ACTIVE, ARCHIVED, or ALL"),
    include_archived: bool = Query(False, description="Include archived patient records"),
    db: Session = Depends(get_db)
):
    """
    Search and filter patients with multi-criteria support.
    By default excludes archived records unless explicitly requested.
    """
    query = db.query(Patient)

    # Status & archive filtering
    if status:
        stat_upper = status.strip().upper()
        if stat_upper == "ARCHIVED":
            query = query.filter(Patient.is_archived == True)
        elif stat_upper == "ACTIVE":
            query = query.filter(Patient.is_archived == False)
        elif stat_upper == "ALL":
            pass # Return both
    elif not include_archived:
        query = query.filter(Patient.is_archived == False)

    # Demographic filters
    if sex:
        query = query.filter(Patient.sex == sex.strip().upper())
    if age_min is not None:
        query = query.filter(Patient.age >= age_min)
    if age_max is not None:
        query = query.filter(Patient.age <= age_max)

    # Free text search across MRN, name, contact, notes, relevant history, conditions, allergies, medications
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.mrn.ilike(term),
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.notes.ilike(term),
                Patient.relevant_history.ilike(term),
                Patient.contact_phone.ilike(term),
                Patient.contact_email.ilike(term),
                Patient.conditions.any(PatientCondition.condition_name.ilike(term)),
                Patient.allergies.any(PatientAllergy.allergen.ilike(term)),
                Patient.medications.any(PatientMedication.medication_name.ilike(term))
            )
        )

    return query.order_by(Patient.is_archived.asc(), Patient.created_at.desc()).all()


@router.get("/{patient_id}", response_model=PatientOverviewResponse)
def get_patient_overview(patient_id: str, db: Session = Depends(get_db)):
    """
    Returns the comprehensive patient overview including:
    demographics, conditions, allergies, medications, symptoms,
    documents, lab results with reference ranges, conflicts, summaries,
    and a synthesized chronological clinical timeline.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    # Fetch associated clinical entities
    docs = db.query(Document).filter(Document.patient_id == patient_id).order_by(Document.created_at.desc()).all()
    labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
    conflicts = db.query(ConflictItem).filter(ConflictItem.patient_id == patient_id).order_by(ConflictItem.created_at.desc()).all()
    summaries = db.query(Summary).filter(Summary.patient_id == patient_id).order_by(Summary.created_at.desc()).all()

    # Build chronological timeline events
    timeline_events: List[TimelineEventOverviewItem] = []

    # 1. Intake event
    intake_date_str = patient.created_at.strftime("%Y-%m-%d") if patient.created_at else "Initial"
    timeline_events.append(TimelineEventOverviewItem(
        id=f"evt-intake-{patient.id}",
        date=intake_date_str,
        title="Patient Intake Profile Registered",
        event_type="INTAKE",
        description=f"Demographic registration complete for {patient.first_name} {patient.last_name} (MRN: {patient.mrn}).",
        badge_type="INTAKE",
        source_provenance="USER_PROVIDED"
    ))

    # 2. Conditions
    for c in patient.conditions:
        d_date = c.diagnosed_date or (c.created_at.strftime("%Y-%m-%d") if c.created_at else intake_date_str)
        timeline_events.append(TimelineEventOverviewItem(
            id=f"evt-cond-{c.id}",
            date=d_date,
            title=f"Condition: {c.condition_name}",
            event_type="CONDITION",
            description=f"Status: {c.status}. Notes: {c.notes or 'None recorded.'}",
            badge_type="CONDITION",
            source_provenance=c.provenance or "USER_PROVIDED"
        ))

    # 3. Allergies
    for a in patient.allergies:
        a_date = a.created_at.strftime("%Y-%m-%d") if a.created_at else intake_date_str
        timeline_events.append(TimelineEventOverviewItem(
            id=f"evt-allg-{a.id}",
            date=a_date,
            title=f"Allergy Noted: {a.allergen}",
            event_type="ALLERGY",
            description=f"Reaction: {a.reaction or 'Unspecified'}. Severity: {a.severity}.",
            badge_type="ALLERGY",
            source_provenance=a.provenance or "USER_PROVIDED"
        ))

    # 4. Medications
    for m in patient.medications:
        m_date = m.created_at.strftime("%Y-%m-%d") if m.created_at else intake_date_str
        timeline_events.append(TimelineEventOverviewItem(
            id=f"evt-med-{m.id}",
            date=m_date,
            title=f"Medication: {m.medication_name}",
            event_type="MEDICATION",
            description=f"Dose: {m.dosage or 'N/A'}, {m.frequency or 'N/A'} via {m.route}.",
            badge_type="MEDICATION",
            source_provenance=m.provenance or "USER_PROVIDED"
        ))

    # 5. Documents
    for d in docs:
        doc_date = d.created_at.strftime("%Y-%m-%d") if d.created_at else intake_date_str
        timeline_events.append(TimelineEventOverviewItem(
            id=f"evt-doc-{d.id}",
            date=doc_date,
            title=f"Report Ingestion: {d.original_filename}",
            event_type="DOCUMENT",
            description=f"Facility: {d.facility or 'Medical Center'}. SHA-256: {d.sha256_checksum[:12]}...",
            badge_type="DOCUMENT",
            source_provenance="DOCUMENT_EXTRACTED"
        ))

    # 6. Labs
    for l in labs:
        l_date = l.report_date or (l.created_at.strftime("%Y-%m-%d") if l.created_at else intake_date_str)
        val_str = f"{l.value} {l.unit}" if l.value is not None else (l.value_text or "")
        timeline_events.append(TimelineEventOverviewItem(
            id=f"evt-lab-{l.id}",
            date=l_date,
            title=f"Lab: {l.test_name} ({val_str})",
            event_type="LAB",
            description=f"Status flag: {l.status}. Provenance: {l.provenance}.",
            badge_type="LAB",
            source_provenance=l.provenance or "DOCUMENT_EXTRACTED"
        ))

    # 7. Conflicts
    for cf in conflicts:
        cf_date = cf.created_at.strftime("%Y-%m-%d") if cf.created_at else intake_date_str
        timeline_events.append(TimelineEventOverviewItem(
            id=f"evt-conf-{cf.id}",
            date=cf_date,
            title=f"Discrepancy: {cf.title}",
            event_type="CONFLICT",
            description=f"{cf.description} (Status: {cf.status})",
            badge_type="CONFLICT",
            source_provenance="SYSTEM_CALCULATED"
        ))

    # Sort timeline reverse chronologically
    timeline_events.sort(key=lambda e: e.date, reverse=True)

    # Construct response object
    return PatientOverviewResponse(
        id=patient.id,
        mrn=patient.mrn,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        age=patient.age,
        sex=patient.sex,
        contact_phone=patient.contact_phone,
        contact_email=patient.contact_email,
        relevant_history=patient.relevant_history,
        notes=patient.notes,
        is_archived=patient.is_archived,
        is_synthetic_demo=patient.is_synthetic_demo,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        conditions=patient.conditions,
        allergies=patient.allergies,
        medications=patient.medications,
        symptoms=patient.symptoms,
        documents=[
            DocumentOverviewItem(
                id=d.id,
                filename=d.original_filename,
                file_type=d.file_type,
                file_size_bytes=d.file_size_bytes,
                facility_name=d.facility,
                upload_date=d.created_at,
                processing_status=d.processing_status,
                sha256_checksum=d.sha256_checksum
            ) for d in docs
        ],
        lab_results=[
            LabResultOverviewItem(
                id=l.id,
                test_name=l.test_name,
                category="CHEMISTRY/HEMATOLOGY",
                numerical_value=l.value,
                text_value=l.value_text,
                unit=l.unit,
                flag=l.status,
                reference_low=l.reference_low,
                reference_high=l.reference_high,
                reference_text=l.raw_reference_range,
                collection_date=l.created_at,
                provenance=l.provenance or "AI_EXTRACTED",
                is_verified=l.is_verified or False,
                original_ai_value=l.original_ai_value,
                confidence=l.confidence or 1.0
            ) for l in labs
        ],
        conflicts=[
            ConflictOverviewItem(
                id=cf.id,
                conflict_type=cf.conflict_type,
                severity=cf.severity,
                description=cf.description,
                status=cf.status,
                source_one=cf.source_a,
                source_two=cf.source_b,
                conflicting_values=cf.conflicting_values,
                created_at=cf.created_at
            ) for cf in conflicts
        ],
        summaries=[
            SummaryOverviewItem(
                id=s.id,
                summary_type=s.model_provider or "CLINICAL_SYNTHESIS",
                content=s.summary_text,
                provenance=s.provenance,
                generated_at=s.created_at
            ) for s in summaries
        ],
        timeline=timeline_events
    )


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    """
    Creates a new patient profile with strict validation.
    Enforces provenance: USER_PROVIDED for all manual entries.
    """
    clean_mrn = payload.mrn.strip().upper()
    existing = db.query(Patient).filter(Patient.mrn == clean_mrn).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patient record with MRN '{clean_mrn}' already exists"
        )

    patient = Patient(
        mrn=clean_mrn,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        date_of_birth=payload.date_of_birth,
        age=payload.age,
        sex=payload.sex.upper(),
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        relevant_history=payload.relevant_history,
        notes=payload.notes,
        is_archived=payload.is_archived,
        is_synthetic_demo=payload.is_synthetic_demo
    )
    db.add(patient)
    db.flush()

    # Add clinical conditions (enforcing provenance="USER_PROVIDED")
    for c in payload.conditions:
        db.add(PatientCondition(
            patient_id=patient.id,
            condition_name=c.condition_name.strip(),
            status=c.status,
            diagnosed_date=c.diagnosed_date,
            notes=c.notes,
            provenance="USER_PROVIDED"
        ))

    # Add allergies (enforcing provenance="USER_PROVIDED")
    for a in payload.allergies:
        db.add(PatientAllergy(
            patient_id=patient.id,
            allergen=a.allergen.strip(),
            reaction=a.reaction,
            severity=a.severity,
            provenance="USER_PROVIDED"
        ))

    # Add medications (enforcing provenance="USER_PROVIDED")
    for m in payload.medications:
        db.add(PatientMedication(
            patient_id=patient.id,
            medication_name=m.medication_name.strip(),
            dosage=m.dosage,
            frequency=m.frequency,
            route=m.route,
            provenance="USER_PROVIDED"
        ))

    # Add symptoms (enforcing provenance="USER_PROVIDED")
    for s in payload.symptoms:
        db.add(PatientSymptom(
            patient_id=patient.id,
            symptom=s.symptom.strip(),
            duration=s.duration,
            severity=s.severity,
            provenance="USER_PROVIDED"
        ))

    # Synthesize initial intake summary
    conditions_str = ", ".join(c.condition_name for c in payload.conditions) or "None documented"
    allergies_str = ", ".join(a.allergen for a in payload.allergies) or "No known allergies"
    meds_str = ", ".join(m.medication_name for m in payload.medications) or "None reported"
    summary_text = (
        f"Initial clinical intake for {patient.first_name} {patient.last_name} ({patient.age} y/o {patient.sex}). "
        f"Active conditions: {conditions_str}. Known allergies: {allergies_str}. Current medications: {meds_str}. "
        f"Relevant history: {patient.relevant_history or 'None noted.'}"
    )
    db.add(Summary(
        patient_id=patient.id,
        summary_text=summary_text,
        disclaimer="Non-diagnostic clinical intake synthesis summary.",
        model_provider="manual_intake",
        provenance="USER_PROVIDED"
    ))

    db.commit()
    db.refresh(patient)

    AuditService.log_action(
        db=db,
        action="PATIENT_CREATED",
        entity_type="PATIENT",
        entity_id=patient.id,
        details={"mrn": patient.mrn, "source": "USER_PROVIDED"}
    )

    return patient


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)):
    """
    Updates patient demographics, history, notes, or clinical lists.
    Enforces provenance: USER_PROVIDED for any newly supplied clinical items.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    if payload.first_name is not None:
        patient.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        patient.last_name = payload.last_name.strip()
    if payload.date_of_birth is not None:
        patient.date_of_birth = payload.date_of_birth
    if payload.age is not None:
        patient.age = payload.age
    if payload.sex is not None:
        patient.sex = payload.sex.upper()
    if payload.contact_phone is not None:
        patient.contact_phone = payload.contact_phone
    if payload.contact_email is not None:
        patient.contact_email = payload.contact_email
    if payload.relevant_history is not None:
        patient.relevant_history = payload.relevant_history
    if payload.notes is not None:
        patient.notes = payload.notes
    if payload.is_archived is not None:
        patient.is_archived = payload.is_archived

    patient.updated_at = datetime.utcnow()

    # If sub-entities are provided, update them
    if payload.conditions is not None:
        db.query(PatientCondition).filter(PatientCondition.patient_id == patient.id).delete()
        for c in payload.conditions:
            db.add(PatientCondition(
                patient_id=patient.id,
                condition_name=c.condition_name.strip(),
                status=c.status,
                diagnosed_date=c.diagnosed_date,
                notes=c.notes,
                provenance="USER_PROVIDED"
            ))

    if payload.allergies is not None:
        db.query(PatientAllergy).filter(PatientAllergy.patient_id == patient.id).delete()
        for a in payload.allergies:
            db.add(PatientAllergy(
                patient_id=patient.id,
                allergen=a.allergen.strip(),
                reaction=a.reaction,
                severity=a.severity,
                provenance="USER_PROVIDED"
            ))

    if payload.medications is not None:
        db.query(PatientMedication).filter(PatientMedication.patient_id == patient.id).delete()
        for m in payload.medications:
            db.add(PatientMedication(
                patient_id=patient.id,
                medication_name=m.medication_name.strip(),
                dosage=m.dosage,
                frequency=m.frequency,
                route=m.route,
                provenance="USER_PROVIDED"
            ))

    if payload.symptoms is not None:
        db.query(PatientSymptom).filter(PatientSymptom.patient_id == patient.id).delete()
        for s in payload.symptoms:
            db.add(PatientSymptom(
                patient_id=patient.id,
                symptom=s.symptom.strip(),
                duration=s.duration,
                severity=s.severity,
                provenance="USER_PROVIDED"
            ))

    db.commit()
    db.refresh(patient)

    AuditService.log_action(
        db=db,
        action="PATIENT_UPDATED",
        entity_type="PATIENT",
        entity_id=patient.id,
        details={"mrn": patient.mrn, "source": "USER_PROVIDED"}
    )

    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_200_OK)
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    """
    Deletes patient record and cascades deletion to all associated clinical data.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    patient_mrn = patient.mrn
    db.delete(patient)
    db.commit()

    AuditService.log_action(
        db=db,
        action="PATIENT_DELETED",
        entity_type="PATIENT",
        entity_id=patient_id,
        details={"mrn": patient_mrn}
    )

    return {"success": True, "message": f"Patient record '{patient_mrn}' successfully deleted"}


@router.post("/{patient_id}/archive", response_model=PatientResponse)
def archive_patient(patient_id: str, db: Session = Depends(get_db)):
    """
    Archives a patient record without permanently deleting data.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    patient.is_archived = True
    patient.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(patient)

    AuditService.log_action(
        db=db,
        action="PATIENT_ARCHIVED",
        entity_type="PATIENT",
        entity_id=patient.id,
        details={"mrn": patient.mrn}
    )

    return patient


@router.post("/{patient_id}/unarchive", response_model=PatientResponse)
def unarchive_patient(patient_id: str, db: Session = Depends(get_db)):
    """
    Restores an archived patient record to active status.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    patient.is_archived = False
    patient.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(patient)

    AuditService.log_action(
        db=db,
        action="PATIENT_UNARCHIVED",
        entity_type="PATIENT",
        entity_id=patient.id,
        details={"mrn": patient.mrn}
    )

    return patient

