import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.patient import Patient, PatientCondition, PatientAllergy
from app.models.clinical import LabResult
from app.services.audit_service import AuditService

client = TestClient(app)

def test_enterprise_security_headers():
    """Verify production security headers are present on all HTTP responses."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "strict-transport-security" in response.headers
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

def test_hipaa_audit_log_csv_export():
    """Verify HIPAA compliance CSV export endpoint."""
    db = SessionLocal()
    try:
        AuditService.log_action(
            db=db,
            action="CLINICAL_VERIFICATION",
            entity_type="LAB_RESULT",
            entity_id="test-entity-123",
            user_id="DR_TEST",
            details="Verified abnormal fasting blood glucose"
        )
    finally:
        db.close()

    response = client.get("/api/audit/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "attachment; filename=hipaa_clinical_audit_trail.csv" in response.headers.get("content-disposition", "")
    
    content = response.text
    assert "Audit ID,Timestamp (UTC),Action Taken,Entity Type" in content
    assert "CLINICAL_VERIFICATION" in content

def test_hl7_fhir_r4_bundle_export():
    """Verify patient records export to valid HL7 FHIR Release 4 Bundle structure."""
    import uuid
    db = SessionLocal()
    unique_mrn = f"MRN-FHIR-{uuid.uuid4().hex[:8]}"
    try:
        patient = Patient(
            mrn=unique_mrn,
            first_name="Eleanor",
            last_name="Vance",
            date_of_birth="1980-04-12",
            age=46,
            sex="FEMALE",
            contact_phone="+1-555-0199",
            contact_email="eleanor.vance@example.com"
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        # Add condition
        cond = PatientCondition(
            patient_id=patient.id,
            condition_name="Type 2 Diabetes Mellitus",
            status="ACTIVE",
            diagnosed_date="2021-06-15"
        )
        # Add lab
        lab = LabResult(
            patient_id=patient.id,
            test_name="Hemoglobin A1c",
            value=7.4,
            value_text="7.4",
            unit="%",
            reference_low=4.0,
            reference_high=5.6,
            status="HIGH",
            is_verified=True,
            report_date="2026-01-10"
        )
        # Add allergy
        allergy = PatientAllergy(
            patient_id=patient.id,
            allergen="Penicillin",
            reaction="Hives and dyspnea",
            severity="SEVERE"
        )
        db.add_all([cond, lab, allergy])
        db.commit()
        patient_id = patient.id
    finally:
        db.close()

    # Request FHIR export
    response = client.get(f"/api/patients/{patient_id}/fhir")
    assert response.status_code == 200
    data = response.json()

    # Validate standard FHIR R4 Bundle envelope
    assert data["resourceType"] == "Bundle"
    assert data["type"] == "collection"
    assert "entry" in data
    assert data["total"] >= 4

    # Validate FHIR Patient resource
    patient_entry = next(e for e in data["entry"] if e["resource"]["resourceType"] == "Patient")
    p_res = patient_entry["resource"]
    assert p_res["id"] == patient_id
    assert p_res["name"][0]["family"] == "Vance"
    assert p_res["gender"] == "female"
    assert p_res["birthDate"] == "1980-04-12"

    # Validate FHIR Condition resource
    cond_entry = next(e for e in data["entry"] if e["resource"]["resourceType"] == "Condition")
    c_res = cond_entry["resource"]
    assert c_res["code"]["text"] == "Type 2 Diabetes Mellitus"
    assert c_res["clinicalStatus"]["coding"][0]["code"] == "active"

    # Validate FHIR Observation resource
    obs_entry = next(e for e in data["entry"] if e["resource"]["resourceType"] == "Observation")
    o_res = obs_entry["resource"]
    assert o_res["code"]["text"] == "Hemoglobin A1c"
    assert o_res["valueQuantity"]["value"] == 7.4
    assert o_res["interpretation"][0]["coding"][0]["code"] == "H"

    # Validate FHIR AllergyIntolerance resource
    allergy_entry = next(e for e in data["entry"] if e["resource"]["resourceType"] == "AllergyIntolerance")
    a_res = allergy_entry["resource"]
    assert a_res["code"]["text"] == "Penicillin"
    assert a_res["criticality"] == "high"

def test_hl7_fhir_r4_not_found():
    """Verify 404 for nonexistent patient FHIR request."""
    response = client.get("/api/patients/nonexistent-uuid-9999/fhir")
    assert response.status_code == 404
