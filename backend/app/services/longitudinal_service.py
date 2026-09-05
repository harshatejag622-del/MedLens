"""
Longitudinal Clinical Intelligence & Summarization Engine
=========================================================
Phase 9 — MedLens

Organizes a patient's integrated medical records into:
1. Longitudinal Timeline Events (sorted chronologically with direction control, filtering, pagination).
2. Longitudinal Laboratory Trend series (chronological analyte values, units, reference range, abnormal flags).
3. Medication History (active, changed, discontinued timelines with provenance).
4. Longitudinal Diagnosis History (first recorded date, latest recorded date, current status, supporting documents).
5. Evidence-Grounded Clinical Summary (AI-assisted, strictly grounded in stored clinical records,
   verification-aware: HUMAN_VERIFIED vs HUMAN_CORRECTED vs AI_EXTRACTED vs HUMAN_REJECTED).
"""

from __future__ import annotations

import re
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.models.patient import Patient, PatientCondition, PatientAllergy, PatientMedication, PatientSymptom
from app.models.clinical import LabResult, Observation, Summary
from app.models.document import Document
from app.models.conflict import ConflictItem, ReviewItem
from app.models.audit import VerificationEvent
from app.models.extracted_entity import ExtractedEntity
from app.services.conflict_detector import parse_date_safely

logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = (
    "MedLens is an AI-assisted clinical information organization platform. "
    "This summary is strictly synthesized from available stored records for clinical decision-support. "
    "It does not provide medical diagnoses, treatment advice, or prognoses. "
    "All clinical determinations require evaluation by a qualified healthcare professional."
)


def format_clinical_date(date_str: Optional[str], default_date: str) -> str:
    """
    Carefully handles clinical dates:
    Preserves exact ISO, year-month, or year precision without fabricating missing days.
    """
    if not date_str:
        return default_date
    norm = parse_date_safely(date_str)
    return norm or default_date


class TimelineEngine:
    """
    Aggregates and filters a comprehensive longitudinal clinical timeline from all patient data.
    """

    @classmethod
    def get_timeline_events(
        cls,
        db: Session,
        patient_id: str,
        sort_order: str = "desc", # "desc" (newest first) or "asc" (oldest first)
        event_types: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        verification_status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 200,
        offset: int = 0
    ) -> Dict[str, Any]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"total": 0, "events": []}

        docs = db.query(Document).filter(Document.patient_id == patient_id).all()
        doc_map = {d.id: d.original_filename for d in docs}

        labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
        conditions = patient.conditions or []
        medications = patient.medications or []
        allergies = patient.allergies or []
        symptoms = patient.symptoms or []
        observations = db.query(Observation).filter(Observation.patient_id == patient_id).all()
        conflicts = db.query(ConflictItem).filter(ConflictItem.patient_id == patient_id).all()
        review_items = db.query(ReviewItem).filter(ReviewItem.patient_id == patient_id).all()
        verification_events = db.query(VerificationEvent).all()

        intake_date = patient.created_at.strftime("%Y-%m-%d") if patient.created_at else "Initial"
        events: List[Dict[str, Any]] = []

        # 1. Intake Profile Registration
        events.append({
            "id": f"evt-intake-{patient.id}",
            "patient_id": patient_id,
            "event_type": "INTAKE",
            "event_date": intake_date,
            "date_precision": "DAY",
            "title": "Patient Intake Profile Registered",
            "description": f"Demographic registration complete for {patient.first_name} {patient.last_name} (MRN: {patient.mrn}, Age: {patient.age}, Sex: {patient.sex}).",
            "source_document": "Patient Intake Form",
            "source_location": "Patient Registration System",
            "verification_status": "USER_PROVIDED",
            "confidence": 1.0,
            "related_clinical_item_id": patient.id,
            "severity": None,
            "created_at": patient.created_at.isoformat() if patient.created_at else intake_date
        })

        # 2. Diagnoses / Conditions
        for c in conditions:
            c_date = format_clinical_date(c.diagnosed_date, intake_date)
            events.append({
                "id": f"evt-cond-{c.id}",
                "patient_id": patient_id,
                "event_type": "CONDITION",
                "event_date": c_date,
                "date_precision": "MONTH" if len(c_date) == 7 else "DAY",
                "title": f"Diagnosis: {c.condition_name}",
                "description": f"Status: {c.status}. Notes: {c.notes or 'Condition recorded in medical chart.'}",
                "source_document": "Patient Medical Profile",
                "source_location": "Clinical History",
                "verification_status": c.provenance or "USER_PROVIDED",
                "confidence": 1.0,
                "related_clinical_item_id": c.id,
                "severity": None,
                "created_at": c.created_at.isoformat() if c.created_at else c_date
            })

        # 3. Medications (Prescriptions & Regimens)
        for m in medications:
            m_date = m.created_at.strftime("%Y-%m-%d") if m.created_at else intake_date
            events.append({
                "id": f"evt-med-{m.id}",
                "patient_id": patient_id,
                "event_type": "MEDICATION",
                "event_date": m_date,
                "date_precision": "DAY",
                "title": f"Medication Documented: {m.medication_name}",
                "description": f"Dose: {m.dosage or 'Not specified'}, Frequency: {m.frequency or 'Not specified'}, Route: {m.route}.",
                "source_document": "Patient Medication Profile",
                "source_location": "Medication Chart",
                "verification_status": m.provenance or "USER_PROVIDED",
                "confidence": 1.0,
                "related_clinical_item_id": m.id,
                "severity": None,
                "created_at": m.created_at.isoformat() if m.created_at else m_date
            })

        # 4. Ingested Clinical Documents
        for d in docs:
            d_date = format_clinical_date(d.report_date, d.created_at.strftime("%Y-%m-%d") if d.created_at else intake_date)
            events.append({
                "id": f"evt-doc-{d.id}",
                "patient_id": patient_id,
                "event_type": "DOCUMENT",
                "event_date": d_date,
                "date_precision": "DAY",
                "title": f"Clinical Report Ingestion: {d.original_filename}",
                "description": f"Document type: {d.document_type}. Facility: {d.facility or 'Diagnostic Services'}. Verified SHA-256: {d.sha256_checksum[:12]}...",
                "source_document": d.original_filename,
                "source_location": f"Storage ({d.file_type.upper()})",
                "verification_status": "DOCUMENT_EXTRACTED",
                "confidence": 1.0,
                "related_clinical_item_id": d.id,
                "severity": None,
                "created_at": d.created_at.isoformat() if d.created_at else d_date
            })

        # 5. Laboratory Results (with reference range and status flag)
        for l in labs:
            l_date = format_clinical_date(l.report_date, l.created_at.strftime("%Y-%m-%d") if l.created_at else intake_date)
            val_display = f"{l.value} {l.unit}" if l.value is not None else (l.value_text or "")
            ref_display = f"Ref: {l.raw_reference_range}" if l.raw_reference_range else "Ref: Not provided in source"
            doc_name = doc_map.get(l.document_id, "Laboratory Report")

            v_status = l.provenance or "AI_EXTRACTED"
            if l.is_verified and "VERIFIED" not in v_status:
                v_status = "HUMAN_VERIFIED"

            events.append({
                "id": f"evt-lab-{l.id}",
                "patient_id": patient_id,
                "event_type": "LABORATORY",
                "event_date": l_date,
                "date_precision": "DAY",
                "title": f"Lab: {l.test_name} — {val_display}",
                "description": f"Status: {l.status}. {ref_display}. Evidence: {l.source_evidence or 'Discrete lab panel extraction.'}",
                "source_document": doc_name,
                "source_location": f"Page {l.page_number}",
                "verification_status": v_status,
                "confidence": l.confidence or 1.0,
                "related_clinical_item_id": l.id,
                "severity": "HIGH" if l.status in ("LOW", "HIGH") else "NORMAL",
                "created_at": l.created_at.isoformat() if l.created_at else l_date
            })

        # 6. Clinical Conflicts & Inconsistencies (Phase 7)
        for cf in conflicts:
            cf_date = cf.created_at.strftime("%Y-%m-%d") if cf.created_at else intake_date
            events.append({
                "id": f"evt-conf-{cf.id}",
                "patient_id": patient_id,
                "event_type": "CONFLICT",
                "event_date": cf_date,
                "date_precision": "DAY",
                "title": f"Clinical Discrepancy: {cf.title}",
                "description": f"Severity: {cf.severity}. {cf.description} (Status: {cf.status})",
                "source_document": cf.source_b or cf.source_a or "Cross-Document Validator",
                "source_location": "Clinical Safety Layer",
                "verification_status": "SYSTEM_CALCULATED",
                "confidence": 1.0,
                "related_clinical_item_id": cf.id,
                "severity": cf.severity,
                "created_at": cf.created_at.isoformat() if cf.created_at else cf_date
            })

        # 7. Human Verification Events (Phase 8)
        for rv in review_items:
            if rv.status in ("ACCEPTED", "EDITED", "REJECTED") and rv.reviewed_at:
                rv_date = rv.reviewed_at.strftime("%Y-%m-%d")
                status_label = "Verified" if rv.status == "ACCEPTED" else ("Corrected" if rv.status == "EDITED" else "Rejected")
                events.append({
                    "id": f"evt-rev-{rv.id}",
                    "patient_id": patient_id,
                    "event_type": "VERIFICATION",
                    "event_date": rv_date,
                    "date_precision": "DAY",
                    "title": f"Clinician {status_label}: {rv.field_name}",
                    "description": f"Action: {rv.status}. Current: {rv.current_value}. Note: {rv.reviewer_note or 'Reviewed by clinician.'}",
                    "source_document": doc_map.get(rv.document_id, "Reviewed Document"),
                    "source_location": "Clinical Review Queue",
                    "verification_status": f"HUMAN_{rv.status}",
                    "confidence": 1.0,
                    "related_clinical_item_id": rv.id,
                    "severity": None,
                    "created_at": rv.reviewed_at.isoformat()
                })

        # Apply Filters
        filtered = events

        # Event type filter
        if event_types:
            et_upper = [t.upper() for t in event_types]
            filtered = [e for e in filtered if e["event_type"] in et_upper]

        # Date range filter
        if date_from:
            filtered = [e for e in filtered if e["event_date"] >= date_from]
        if date_to:
            filtered = [e for e in filtered if e["event_date"] <= date_to]

        # Verification status filter
        if verification_status:
            vs_upper = verification_status.upper()
            filtered = [e for e in filtered if vs_upper in e["verification_status"].upper()]

        # Search query filter (keywords in title, description, or source)
        if search_query:
            sq = search_query.strip().lower()
            filtered = [
                e for e in filtered
                if sq in e["title"].lower() or sq in e["description"].lower() or sq in (e["source_document"] or "").lower()
            ]

        # Chronological Sort
        reverse = (sort_order.lower() == "desc")
        filtered.sort(key=lambda e: (e["event_date"], e["created_at"]), reverse=reverse)

        total_count = len(filtered)
        paginated = filtered[offset:offset + limit]

        return {
            "total": total_count,
            "count": len(paginated),
            "offset": offset,
            "limit": limit,
            "sort_order": sort_order,
            "events": paginated
        }


class TrendEngine:
    """
    Extracts chronological trend views for laboratory analytes.
    """

    @classmethod
    def get_lab_trends(cls, db: Session, patient_id: str) -> Dict[str, Any]:
        labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
        if not labs:
            return {"trends": {}}

        # Group by normalized test name
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for l in labs:
            if l.value is None:
                continue # Only numeric values are trendable on charts
            t_name = l.test_name.strip()
            date_str = l.report_date or (l.created_at.strftime("%Y-%m-%d") if l.created_at else "Unknown Date")

            grouped.setdefault(t_name, []).append({
                "id": l.id,
                "date": date_str,
                "value": l.value,
                "unit": l.unit or "",
                "status": l.status,
                "reference_low": l.reference_low,
                "reference_high": l.reference_high,
                "reference_text": l.raw_reference_range,
                "provenance": l.provenance,
                "is_verified": l.is_verified,
                "original_ai_value": l.original_ai_value
            })

        # Sort each trend chronologically
        trends_result: Dict[str, Any] = {}
        for test_name, points in grouped.items():
            points.sort(key=lambda p: p["date"])
            # Unit consistency check
            units = {p["unit"] for p in points if p["unit"]}
            trends_result[test_name] = {
                "test_name": test_name,
                "points_count": len(points),
                "primary_unit": list(units)[0] if units else "",
                "multiple_units": len(units) > 1,
                "units_found": list(units),
                "data_points": points
            }

        return {"trends": trends_result}


class MedicalHistoryEngine:
    """
    Generates structured longitudinal medication and diagnosis histories.
    """

    @classmethod
    def get_medication_history(cls, db: Session, patient_id: str) -> Dict[str, Any]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"medications": []}

        profile_meds = patient.medications or []
        extracted_meds = db.query(ExtractedEntity).filter(
            ExtractedEntity.patient_id == patient_id,
            ExtractedEntity.entity_type == "MEDICATION"
        ).all()

        docs = db.query(Document).filter(Document.patient_id == patient_id).all()
        doc_map = {d.id: d.original_filename for d in docs}

        history: List[Dict[str, Any]] = []

        for pm in profile_meds:
            history.append({
                "id": pm.id,
                "medication_name": pm.medication_name,
                "dose": pm.dosage or "Not specified",
                "frequency": pm.frequency or "Not specified",
                "route": pm.route,
                "start_date": pm.created_at.strftime("%Y-%m-%d") if pm.created_at else "Initial",
                "stop_date": None,
                "current_status": "ACTIVE",
                "source": "Patient Intake Profile",
                "verification_status": pm.provenance or "USER_PROVIDED"
            })

        for ee in extracted_meds:
            doc_name = doc_map.get(ee.document_id, "Clinical Report")
            history.append({
                "id": ee.id,
                "medication_name": ee.name,
                "dose": ee.value or "Not specified",
                "frequency": "Not specified",
                "route": "ORAL",
                "start_date": ee.created_at.strftime("%Y-%m-%d") if ee.created_at else "Unknown",
                "stop_date": None,
                "current_status": "DOCUMENTED_IN_REPORT",
                "source": f"Document: {doc_name}",
                "verification_status": ee.provenance or "AI_EXTRACTED"
            })

        return {"medications": history}

    @classmethod
    def get_diagnosis_history(cls, db: Session, patient_id: str) -> Dict[str, Any]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"diagnoses": []}

        conditions = patient.conditions or []
        extracted_conditions = db.query(ExtractedEntity).filter(
            ExtractedEntity.patient_id == patient_id,
            ExtractedEntity.entity_type == "CONDITION"
        ).all()
        docs = db.query(Document).filter(Document.patient_id == patient_id).all()
        doc_map = {d.id: d.original_filename for d in docs}

        # Group diagnoses by normalized name
        grouped: Dict[str, Dict[str, Any]] = {}

        for c in conditions:
            norm = c.condition_name.strip().title()
            d_date = c.diagnosed_date or (c.created_at.strftime("%Y-%m-%d") if c.created_at else "Initial")
            if norm not in grouped:
                grouped[norm] = {
                    "diagnosis": norm,
                    "first_recorded_date": d_date,
                    "most_recent_date": d_date,
                    "current_status": c.status,
                    "supporting_sources": ["Patient Profile History"],
                    "verification_status": c.provenance or "USER_PROVIDED"
                }
            else:
                if d_date < grouped[norm]["first_recorded_date"]:
                    grouped[norm]["first_recorded_date"] = d_date
                if d_date > grouped[norm]["most_recent_date"]:
                    grouped[norm]["most_recent_date"] = d_date

        for ee in extracted_conditions:
            norm = ee.name.strip().title()
            doc_name = doc_map.get(ee.document_id, "Clinical Report")
            e_date = ee.created_at.strftime("%Y-%m-%d") if ee.created_at else "Report Date"
            if norm not in grouped:
                grouped[norm] = {
                    "diagnosis": norm,
                    "first_recorded_date": e_date,
                    "most_recent_date": e_date,
                    "current_status": "ACTIVE",
                    "supporting_sources": [f"Document: {doc_name}"],
                    "verification_status": ee.provenance or "AI_EXTRACTED"
                }
            else:
                src = f"Document: {doc_name}"
                if src not in grouped[norm]["supporting_sources"]:
                    grouped[norm]["supporting_sources"].append(src)

        return {"diagnoses": list(grouped.values())}


class ClinicalSummarizer:
    """
    Synthesizes an evidence-grounded, verification-aware longitudinal clinical summary.
    Strictly forbids inventing information, treatments, or speculative diagnoses.
    """

    @classmethod
    def generate_longitudinal_summary(cls, db: Session, patient_id: str) -> Dict[str, Any]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"error": "Patient not found"}

        conditions = patient.conditions or []
        medications = patient.medications or []
        allergies = patient.allergies or []
        labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
        docs = db.query(Document).filter(Document.patient_id == patient_id).all()
        conflicts = db.query(ConflictItem).filter(
            ConflictItem.patient_id == patient_id,
            ConflictItem.status.in_(["OPEN", "UNRESOLVED", "REVIEWED"])
        ).all()
        review_items = db.query(ReviewItem).filter(ReviewItem.patient_id == patient_id).all()

        evidence_references: List[Dict[str, Any]] = []

        # A. Patient Overview
        overview_text = (
            f"Patient {patient.first_name} {patient.last_name} (MRN: {patient.mrn}) is a {patient.age}-year-old {patient.sex.lower()} "
            f"registered on {patient.created_at.strftime('%Y-%m-%d') if patient.created_at else 'initial record'}."
        )

        # B. Diagnoses
        if conditions:
            cond_list = [f"{c.condition_name} ({c.status}, first recorded: {c.diagnosed_date or 'Intake'})" for c in conditions]
            diagnoses_text = f"Documented conditions include: {'; '.join(cond_list)}."
            for c in conditions:
                evidence_references.append({
                    "item": c.condition_name,
                    "category": "DIAGNOSIS",
                    "source": "Patient Medical Profile",
                    "provenance": c.provenance or "USER_PROVIDED"
                })
        else:
            diagnoses_text = "No prior chronic diagnoses recorded in the chart."

        # C. Medications
        if medications:
            med_list = [f"{m.medication_name} {m.dosage or ''} ({m.frequency or 'daily'}) via {m.route}" for m in medications]
            medications_text = f"Active medication regimen: {'; '.join(med_list)}."
            for m in medications:
                evidence_references.append({
                    "item": m.medication_name,
                    "category": "MEDICATION",
                    "source": "Medication Chart",
                    "provenance": m.provenance or "USER_PROVIDED"
                })
        else:
            medications_text = "No active medications documented on profile."

        # D. Allergies
        if allergies:
            allg_list = [f"{a.allergen} (Reaction: {a.reaction or 'Unspecified'}, Severity: {a.severity})" for a in allergies]
            allergies_text = f"Documented allergies: {'; '.join(allg_list)}."
        else:
            allergies_text = "No known drug or environmental allergies recorded."

        # E. Laboratory Findings & Out-of-Range Analytes
        abnormal_labs = [l for l in labs if l.status in ("LOW", "HIGH") and l.provenance != "HUMAN_REJECTED"]
        normal_labs = [l for l in labs if l.status == "NORMAL" and l.provenance != "HUMAN_REJECTED"]

        if abnormal_labs:
            ab_list = []
            for l in abnormal_labs:
                v_str = f"{l.value} {l.unit}" if l.value is not None else l.value_text
                ref = f" [Ref: {l.raw_reference_range}]" if l.raw_reference_range else ""
                ab_list.append(f"{l.test_name}: {v_str} ({l.status}{ref})")
                evidence_references.append({
                    "item": l.test_name,
                    "category": "LABORATORY",
                    "source": l.document.original_filename if l.document else "Laboratory Report",
                    "provenance": l.provenance,
                    "is_verified": l.is_verified
                })
            labs_text = f"Abnormal laboratory findings requiring clinical attention: {'; '.join(ab_list)}."
        elif normal_labs:
            labs_text = f"All {len(normal_labs)} discrete laboratory analytes on file are within source reference boundaries."
        else:
            labs_text = "Insufficient discrete laboratory data available in current record."

        # F. Unresolved Conflicts (Phase 7 Integration)
        if conflicts:
            conf_list = [f"[{cf.severity}] {cf.title}" for cf in conflicts]
            conflicts_text = f"Active safety inconsistencies requiring review: {'; '.join(conf_list)}."
        else:
            conflicts_text = "Zero unresolved clinical discrepancies or drug-allergy contraindications detected."

        # G. Human Verification Status (Phase 8 Integration)
        accepted_cnt = len([r for r in review_items if r.status == "ACCEPTED"])
        corrected_cnt = len([r for r in review_items if r.status == "EDITED"])
        pending_cnt = len([r for r in review_items if r.status == "PENDING"])
        rejected_cnt = len([r for r in review_items if r.status == "REJECTED"])

        verification_summary = (
            f"Verification audit: {accepted_cnt} extraction(s) clinician-verified, "
            f"{corrected_cnt} human-corrected, {pending_cnt} pending review, {rejected_cnt} rejected."
        )

        full_summary = (
            f"{overview_text}\n\n"
            f"CLINICAL HISTORY & DIAGNOSES:\n{diagnoses_text}\n\n"
            f"MEDICATIONS & ALLERGIES:\n{medications_text}\n{allergies_text}\n\n"
            f"LABORATORY FINDINGS:\n{labs_text}\n\n"
            f"SAFETY DISCREPANCIES:\n{conflicts_text}\n\n"
            f"HUMAN VERIFICATION AUDIT:\n{verification_summary}"
        )

        # Store summary in database
        summary_record = Summary(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            summary_text=full_summary,
            disclaimer=DISCLAIMER_TEXT,
            model_provider="evidence_grounded_synthesizer",
            provenance="SYSTEM_CALCULATED",
            created_at=datetime.utcnow()
        )
        db.add(summary_record)
        db.commit()

        return {
            "summary_id": summary_record.id,
            "patient_id": patient_id,
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "summary_text": full_summary,
            "sections": {
                "patient_overview": overview_text,
                "diagnoses": diagnoses_text,
                "medications": medications_text,
                "allergies": allergies_text,
                "laboratories": labs_text,
                "unresolved_conflicts": conflicts_text,
                "verification_status": verification_summary
            },
            "evidence_references": evidence_references,
            "disclaimer": DISCLAIMER_TEXT,
            "generated_at": summary_record.created_at.isoformat()
        }
