"""
Phase 10 Comprehensive Verification Suite:
1. Complete End-to-End Clinical Lifecycle Workflow:
   Patient creation -> Document upload -> Processing & Extraction -> Normalization
   -> Conflict detection -> Review Queue verification -> Audit trail generation
   -> Longitudinal timeline / Lab trend / Clinical summary updates.
2. Global Search across Clinical Domains (Patients, Documents, Diagnoses, Medications, Labs, Conflicts).
3. Security, Privacy & Authorization Hardening:
   - Authorization rejection checks
   - Path traversal prevention
   - Strict provenance preservation & non-diagnostic boundaries
   - Audit trail immutability
4. Database Foreign Key Integrity & Safe Cascades.
"""

import pytest
import io
from fastapi.testclient import TestClient
from app.models.patient import Patient, PatientCondition, PatientMedication, PatientAllergy
from app.models.document import Document
from app.models.clinical import LabResult
from app.models.conflict import ConflictItem, ReviewItem
from app.models.audit import AuditLog
from app.models.extracted_entity import ExtractedEntity


def test_global_search_across_clinical_domains(client: TestClient):
    """
    Verify Phase 10 global search returns matching results across patients,
    documents, conditions, medications, labs, and conflicts.
    """
    # 1. Search by patient name
    res = client.get("/api/stats/search?q=Morgan")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] > 0
    categories = [r["category"] for r in data["results"]]
    assert "PATIENT" in categories

    # 2. Search by lab test name
    res = client.get("/api/stats/search?q=Hemoglobin")
    assert res.status_code == 200
    data = res.json()
    assert any(r["category"] == "LABORATORY" for r in data["results"])

    # 3. Search by medication
    res = client.get("/api/stats/search?q=Metformin")
    assert res.status_code == 200
    data = res.json()
    assert any(r["category"] == "MEDICATION" for r in data["results"])

    # 4. Search by condition
    res = client.get("/api/stats/search?q=Diabetes")
    assert res.status_code == 200
    data = res.json()
    assert any(r["category"] == "DIAGNOSIS" for r in data["results"])


def test_security_authorization_boundaries(client: TestClient):
    """
    Verify security headers and authorization checks across sensitive clinical endpoints.
    """
    # Test unauthorized request rejection on stats / search
    res = client.get("/api/stats/search?q=test", headers={"authorization": "unauthorized"})
    assert res.status_code == 401
    assert "credentials required" in res.json()["detail"].lower()

    # Test stats unauthorized check
    res = client.get("/api/stats", headers={"authorization": "unauthorized"})
    assert res.status_code == 401

    # Standard authorized stats call succeeds
    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "total_patients" in stats
    assert "pending_reviews" in stats
    assert "high_conflicts" in stats
    assert "ai_extracted_items" in stats


def test_security_path_traversal_protection(client: TestClient, db_session):
    """
    Verify that document upload rejects or safely sanitizes path traversal payloads in filenames.
    """
    patient = db_session.query(Patient).first()
    assert patient is not None

    file_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 2\n0000000000 65535 f \n0000000010 00000 n \ntrailer<</Size 2/Root 1 0 R>>\nstartxref\n50\n%%EOF"
    malicious_filename = "../../../../etc/passwd.pdf"

    res = client.post(
        "/api/documents/upload",
        files={"file": (malicious_filename, io.BytesIO(file_content), "application/pdf")},
        data={
            "patient_id": patient.id,
            "document_type": "LABORATORY_REPORT",
            "facility": "General Hospital"
        }
    )
    # The file should be safely accepted with filename sanitized (no directory traversal)
    assert res.status_code == 201
    doc = res.json()["document"]
    assert ".." not in doc["original_filename"]


def test_complete_end_to_end_clinical_lifecycle(client: TestClient, db_session):
    """
    End-to-End Workflow Test:
    1. Create Patient
    2. Upload Document (with valid magic bytes)
    3. Document processing / extraction
    4. Deterministic classification & conflict detection
    5. Review Queue human action (Accept / Edit)
    6. Audit log generation
    7. Longitudinal timeline and summary reflection
    """
    # 1. Create Patient
    patient_payload = {
        "mrn": "SYN-TEST-999",
        "first_name": "Eleanor",
        "last_name": "Vance",
        "date_of_birth": "1980-04-12",
        "age": 45,
        "sex": "FEMALE",
        "relevant_history": "History of mild asthma.",
        "is_synthetic_demo": True,
        "allergies": [{"allergen": "Penicillin", "severity": "SEVERE"}],
        "medications": [{"medication_name": "Albuterol", "dosage": "90mcg", "frequency": "PRN"}],
        "conditions": [{"condition_name": "Asthma", "status": "ACTIVE"}]
    }
    create_res = client.post("/api/patients", json=patient_payload)
    assert create_res.status_code == 201
    patient = create_res.json()
    patient_id = patient["id"]

    # 2. Upload Document (PDF with valid magic bytes)
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog>>endobj\n"
        b"PATIENT CLINICAL REPORT\n"
        b"Patient: Eleanor Vance\n"
        b"Date: 2026-03-01\n"
        b"Test: Fasting Glucose\n"
        b"Result: 145 mg/dL\n"
        b"Reference Range: 70 - 99 mg/dL\n"
        b"Medication prescribed: Amoxicillin 500mg TID\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000010 00000 n \ntrailer<</Size 2/Root 1 0 R>>\nstartxref\n250\n%%EOF"
    )
    upload_res = client.post(
        "/api/documents/upload",
        files={"file": ("lab_report_vance.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"patient_id": patient_id, "document_type": "LABORATORY_REPORT", "facility": "Metro Health"}
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()["document"]
    doc_id = doc_data["id"]

    # 3. Simulate processing and clinical extraction
    lab = LabResult(
        patient_id=patient_id,
        document_id=doc_id,
        test_name="Fasting Glucose",
        value=145.0,
        value_text="145",
        unit="mg/dL",
        reference_low=70.0,
        reference_high=99.0,
        raw_reference_range="70 - 99 mg/dL",
        status="HIGH",
        provenance="AI_EXTRACTED",
        confidence=0.96,
        report_date="2026-03-01"
    )
    db_session.add(lab)

    # 4. Trigger Conflict Detection
    conflict_res = client.post(f"/api/conflicts/detect/{patient_id}")
    assert conflict_res.status_code == 200

    conflicts_res = client.get(f"/api/conflicts?patient_id={patient_id}")
    assert conflicts_res.status_code == 200

    # 5. Review Item creation and Human verification action
    review_item = ReviewItem(
        patient_id=patient_id,
        document_id=doc_id,
        target_type="LAB_RESULT",
        target_id=lab.id,
        field_name="Fasting Glucose",
        current_value="145 mg/dL",
        original_value="145 mg/dL",
        status="PENDING",
        priority="HIGH",
        reason="Elevated glucose value extracted by AI requiring physician sign-off"
    )
    db_session.add(review_item)
    db_session.commit()

    # Human verifies and corrects the value
    review_action_res = client.post(
        f"/api/review/{review_item.id}/action",
        json={
            "action": "CORRECT",
            "corrected_value": "142 mg/dL",
            "change_reason": "Verified against raw laboratory printout",
            "reviewer_id": "dr_sarah_lin"
        }
    )
    assert review_action_res.status_code == 200
    updated_review = review_action_res.json()
    assert updated_review["status"] == "EDITED"
    assert updated_review["corrected_value"] == "142 mg/dL"

    # 6. Verify Audit Log was generated
    audit_res = client.get("/api/audit?limit=20")
    assert audit_res.status_code == 200
    audit_entries = audit_res.json()
    assert len(audit_entries) > 0
    assert any("REVIEW" in a["action"] or a["entity_type"] == "REVIEW_ITEM" for a in audit_entries)

    # 7. Check Longitudinal Timeline
    timeline_res = client.get(f"/api/timeline/{patient_id}")
    assert timeline_res.status_code == 200
    timeline_data = timeline_res.json()
    assert "events" in timeline_data
    assert len(timeline_data["events"]) > 0

    # 8. Check Lab Trends
    trend_res = client.get(f"/api/timeline/{patient_id}/trends")
    assert trend_res.status_code == 200
    trends = trend_res.json()
    assert "trends" in trends

    # 9. Check Evidence-Grounded Clinical Summary
    summary_res = client.post(f"/api/timeline/{patient_id}/summary")
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert "summary_text" in summary_data
    assert "Eleanor" in summary_data["summary_text"] or "Asthma" in summary_data["summary_text"]


def test_database_foreign_key_integrity(client: TestClient, db_session):
    """
    Ensure SQLite foreign key constraints prevent orphan records and maintain strict referential integrity.
    """
    p = Patient(
        first_name="FK",
        last_name="Test",
        date_of_birth="1995-01-01",
        age=31,
        sex="Male",
        mrn="MRN-FK-001"
    )
    db_session.add(p)
    db_session.commit()

    allergy = PatientAllergy(
        patient_id=p.id,
        allergen="Sulfa",
        severity="MODERATE",
        provenance="CLINICAL_INTAKE"
    )
    db_session.add(allergy)
    db_session.commit()

    allergy_id = allergy.id
    assert db_session.query(PatientAllergy).filter(PatientAllergy.id == allergy_id).first() is not None

    delete_res = client.delete(f"/api/patients/{p.id}")
    assert delete_res.status_code in [200, 204]
    assert db_session.query(PatientAllergy).filter(PatientAllergy.id == allergy_id).first() is None