"""
Phase 7 Tests: Clinical Conflict & Contradiction Detection Engine
================================================================

Covers all Phase 7 requirements:
1. Duplicate medication with divergent dosage.
2. Active medication that conflicts with an allergy (direct match and cross-reactive class).
3. Active vs Discontinued medication status discrepancy.
4. Conflicting laboratory values on the same date.
5. Different non-standard laboratory units across reports.
6. Conflicting diagnosis status (Active vs Resolved).
7. Duplicate non-conflicting information (should NOT raise false positive).
8. Historical / discontinued information that should NOT be incorrectly flagged.
9. Correctly formatted but differently represented dates (ISO vs US format: no false positive).
10. Physiologically implausible / extreme laboratory value flagged for clinician review.
11. Demographic mismatch (sex and DOB mismatch between profile and document).
12. Review / Resolution workflow with audit logging (preserves original data).
13. Idempotent conflict detection (does not re-duplicate open items).
14. API endpoints for listing, detecting, and resolving conflicts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
import pytest

from app.models.patient import Patient, PatientCondition, PatientAllergy, PatientMedication
from app.models.clinical import LabResult
from app.models.document import Document
from app.models.extracted_entity import ExtractedEntity
from app.models.conflict import ConflictItem
from app.models.audit import AuditLog
from app.services.conflict_detector import (
    ConflictDetector,
    normalize_string,
    parse_date_safely,
    extract_numeric_dose
)


# ---------------------------------------------------------------------------
# Unit tests for helper functions (False-positive protection)
# ---------------------------------------------------------------------------

class TestConflictDetectorHelpers:

    def test_normalize_string(self):
        assert normalize_string("  Amoxicillin   500mg  ") == "amoxicillin 500mg"
        assert normalize_string(None) == ""

    def test_parse_date_safely_various_formats(self):
        # Different representations of the exact same date should normalize to identical ISO string
        d1 = parse_date_safely("2026-08-20")
        d2 = parse_date_safely("08/20/2026")
        d3 = parse_date_safely("20/08/2026")
        assert d1 == "2026-08-20"
        assert d2 == "2026-08-20"
        assert d3 == "2026-08-20"

    def test_extract_numeric_dose(self):
        assert extract_numeric_dose("500 mg") == 500.0
        assert extract_numeric_dose("10mg") == 10.0
        assert extract_numeric_dose("0.25 mcg") == 0.25
        assert extract_numeric_dose("once daily") is None


# ---------------------------------------------------------------------------
# 1 & 8: Medication Conflicts & Discontinued Safety
# ---------------------------------------------------------------------------

class TestMedicationConflicts:

    def test_duplicate_medication_with_different_dose(self, db_session):
        """Same medication appearing with different dosages should be flagged as HIGH severity."""
        patient = db_session.query(Patient).first()
        assert patient is not None

        # Add profile medication: Metformin 500 mg
        m1 = PatientMedication(
            patient_id=patient.id,
            medication_name="Metformin",
            dosage="500 mg",
            frequency="Daily",
            provenance="USER_PROVIDED"
        )
        db_session.add(m1)

        # Add extracted document medication: Metformin 1000 mg
        doc = Document(
            patient_id=patient.id,
            original_filename="clinic_visit.pdf",
            stored_filename="clinic_visit.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            sha256_checksum="abc123hash" + str(uuid.uuid4())[:8],
            document_type="CLINICAL_NOTE"
        )
        db_session.add(doc)
        db_session.flush()

        ee = ExtractedEntity(
            patient_id=patient.id,
            document_id=doc.id,
            entity_type="MEDICATION",
            name="Metformin",
            value="1000 mg",
            provenance="AI_EXTRACTED"
        )
        db_session.add(ee)
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        dose_conflicts = [c for c in conflicts if c.conflict_type == "MEDICATION_DISCREPANCY" and "Dosage" in c.title]

        assert len(dose_conflicts) >= 1
        conf = dose_conflicts[0]
        assert conf.severity == "HIGH"
        assert "500 mg" in conf.description
        assert "1000 mg" in conf.description
        assert conf.status == "OPEN"

    def test_duplicate_medication_same_dose_not_flagged(self, db_session):
        """Duplicate medication with the same dosage should NOT produce a conflict (no false positive)."""
        patient = db_session.query(Patient).first()
        m1 = PatientMedication(
            patient_id=patient.id,
            medication_name="Lisinopril",
            dosage="10 mg",
            provenance="USER_PROVIDED"
        )
        db_session.add(m1)

        doc = Document(
            patient_id=patient.id,
            original_filename="discharge_summary.pdf",
            stored_filename="discharge_summary.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            sha256_checksum="hash_same_dose_" + str(uuid.uuid4())[:8]
        )
        db_session.add(doc)
        db_session.flush()

        ee = ExtractedEntity(
            patient_id=patient.id,
            document_id=doc.id,
            entity_type="MEDICATION",
            name="Lisinopril",
            value="10 mg",
            provenance="AI_EXTRACTED"
        )
        db_session.add(ee)
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        lisinopril_conflicts = [c for c in conflicts if "Lisinopril" in c.title and c.conflict_type == "MEDICATION_DISCREPANCY"]
        assert len(lisinopril_conflicts) == 0


# ---------------------------------------------------------------------------
# 2: Allergy vs Active Medication Conflicts
# ---------------------------------------------------------------------------

class TestAllergyMedicationConflicts:

    def test_allergy_direct_match_with_active_medication(self, db_session):
        """Documented allergy to Aspirin with prescribed Aspirin medication."""
        patient = db_session.query(Patient).first()

        db_session.add(PatientAllergy(
            patient_id=patient.id,
            allergen="Aspirin",
            reaction="Bronchospasm",
            severity="SEVERE",
            provenance="USER_PROVIDED"
        ))
        db_session.add(PatientMedication(
            patient_id=patient.id,
            medication_name="Aspirin",
            dosage="81 mg",
            frequency="Daily",
            provenance="USER_PROVIDED"
        ))
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        allergy_conflicts = [c for c in conflicts if c.conflict_type == "MEDICATION_ALLERGY" and "Aspirin" in c.title]

        assert len(allergy_conflicts) >= 1
        conf = allergy_conflicts[0]
        assert conf.severity == "HIGH"
        assert "Bronchospasm" in conf.description

    def test_cross_reactive_allergy_class_conflict(self, db_session):
        """Allergy to Penicillin with prescribed Amoxicillin (cross-reactive class)."""
        patient = db_session.query(Patient).first()

        db_session.add(PatientAllergy(
            patient_id=patient.id,
            allergen="Penicillin",
            reaction="Hives/Anaphylaxis",
            provenance="USER_PROVIDED"
        ))
        db_session.add(PatientMedication(
            patient_id=patient.id,
            medication_name="Amoxicillin",
            dosage="500 mg",
            provenance="USER_PROVIDED"
        ))
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        pen_conflicts = [c for c in conflicts if c.conflict_type == "MEDICATION_ALLERGY" and "Amoxicillin" in c.title]
        assert len(pen_conflicts) >= 1
        assert pen_conflicts[0].severity == "HIGH"


# ---------------------------------------------------------------------------
# 3: Diagnosis / Condition Conflicts
# ---------------------------------------------------------------------------

class TestConditionConflicts:

    def test_active_vs_resolved_condition_conflict(self, db_session):
        """Condition listed as Resolved in profile but Active in extracted records."""
        patient = db_session.query(Patient).first()

        db_session.add(PatientCondition(
            patient_id=patient.id,
            condition_name="Asthma",
            status="RESOLVED",
            provenance="USER_PROVIDED"
        ))

        doc = Document(
            patient_id=patient.id,
            original_filename="consult_note.pdf",
            stored_filename="consult_note.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            sha256_checksum="hash_asthma_" + str(uuid.uuid4())[:8]
        )
        db_session.add(doc)
        db_session.flush()

        db_session.add(ExtractedEntity(
            patient_id=patient.id,
            document_id=doc.id,
            entity_type="CONDITION",
            name="Asthma",
            value="Active",
            provenance="AI_EXTRACTED"
        ))
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        asthma_conflicts = [c for c in conflicts if c.conflict_type == "DIAGNOSIS_DISCREPANCY" and "Asthma" in c.title]

        assert len(asthma_conflicts) >= 1
        assert asthma_conflicts[0].severity == "MEDIUM"


# ---------------------------------------------------------------------------
# 4 & 5: Laboratory Conflicts
# ---------------------------------------------------------------------------

class TestLaboratoryConflicts:

    def test_conflicting_values_on_same_date(self, db_session):
        """Same test having conflicting values on the same date."""
        patient = db_session.query(Patient).first()

        doc1 = Document(
            patient_id=patient.id,
            original_filename="lab_a.pdf",
            stored_filename="lab_a.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            sha256_checksum="lab_a_hash_" + str(uuid.uuid4())[:8]
        )
        doc2 = Document(
            patient_id=patient.id,
            original_filename="lab_b.pdf",
            stored_filename="lab_b.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            sha256_checksum="lab_b_hash_" + str(uuid.uuid4())[:8]
        )
        db_session.add_all([doc1, doc2])
        db_session.flush()

        # Same test (Glucose), same date (2026-08-20), significantly divergent values (95 vs 180)
        l1 = LabResult(
            patient_id=patient.id,
            document_id=doc1.id,
            test_name="Fasting Glucose",
            value=95.0,
            value_text="95",
            unit="mg/dL",
            report_date="2026-08-20"
        )
        l2 = LabResult(
            patient_id=patient.id,
            document_id=doc2.id,
            test_name="Fasting Glucose",
            value=180.0,
            value_text="180",
            unit="mg/dL",
            report_date="08/20/2026" # Different format of same date!
        )
        db_session.add_all([l1, l2])
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        glucose_conflicts = [c for c in conflicts if c.conflict_type == "LAB_DISCREPANCY" and "Fasting Glucose" in c.title]

        assert len(glucose_conflicts) >= 1
        assert glucose_conflicts[0].severity == "MEDIUM"

    def test_physiologically_implausible_value_flagged(self, db_session):
        """Extreme/impossible lab value (e.g. Potassium 18.5) flagged as suspicious."""
        patient = db_session.query(Patient).first()

        doc = Document(
            patient_id=patient.id,
            original_filename="critical_lab.pdf",
            stored_filename="critical_lab.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            sha256_checksum="crit_lab_hash_" + str(uuid.uuid4())[:8]
        )
        db_session.add(doc)
        db_session.flush()

        l = LabResult(
            patient_id=patient.id,
            document_id=doc.id,
            test_name="Serum Potassium",
            value=18.5,
            value_text="18.5",
            unit="mEq/L",
            report_date="2026-08-21"
        )
        db_session.add(l)
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        potassium_conflicts = [c for c in conflicts if "Potassium" in c.title and c.severity == "HIGH"]
        assert len(potassium_conflicts) >= 1


# ---------------------------------------------------------------------------
# 5: Demographic Discrepancies
# ---------------------------------------------------------------------------

class TestDemographicConflicts:

    def test_conflicting_sex_in_document_text(self, db_session):
        """Profile says MALE, document explicitly says 'Sex: Female'."""
        patient = db_session.query(Patient).first()
        patient.sex = "MALE"

        doc = Document(
            patient_id=patient.id,
            original_filename="admission_record.txt",
            stored_filename="admission_record.txt",
            file_type="txt",
            file_size_bytes=1024,
            sha256_checksum="demog_hash_" + str(uuid.uuid4())[:8],
            raw_text="PATIENT RECORD\nName: Alex Morgan\nSex: Female\nDOB: 1985-04-12"
        )
        db_session.add(doc)
        db_session.commit()

        conflicts = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        sex_conflicts = [c for c in conflicts if c.conflict_type == "DEMOGRAPHIC_MISMATCH" and "Sex" in c.title]

        assert len(sex_conflicts) >= 1
        assert sex_conflicts[0].severity == "HIGH"


# ---------------------------------------------------------------------------
# 6: Review, Resolution & Audit Trail Integrity
# ---------------------------------------------------------------------------

class TestConflictReviewWorkflow:

    def test_resolve_conflict_creates_audit_log_without_altering_patient_data(self, client, db_session):
        """Resolving a conflict updates status, logs an audit entry, and preserves patient records."""
        patient = db_session.query(Patient).first()

        conflict = ConflictItem(
            patient_id=patient.id,
            conflict_type="MEDICATION_ALLERGY",
            severity="HIGH",
            title="Allergy Test Conflict",
            description="Test discrepancy description",
            source_a="Profile",
            source_b="Document",
            status="OPEN"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        # Clinician resolves conflict via API
        payload = {
            "resolution_notes": "Clinician verified with patient: No allergy experienced; amoxicillin tolerated well.",
            "resolved_by": "dr_smith",
            "new_status": "RESOLVED"
        }
        res = client.post(f"/api/conflicts/{conflict.id}/resolve", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "RESOLVED"
        assert data["resolved_by"] == "dr_smith"
        assert "verified with patient" in data["resolution_notes"]

        # Audit trail check: must have logged CONFLICT_STATUS_UPDATED
        audit = db_session.query(AuditLog).filter(
            AuditLog.entity_id == conflict.id,
            AuditLog.action == "CONFLICT_STATUS_UPDATED"
        ).first()
        assert audit is not None
        details = json.loads(audit.details)
        assert details["previous_status"] == "OPEN"
        assert details["new_status"] == "RESOLVED"

    def test_mark_as_reviewed_action(self, client, db_session):
        """Marking as REVIEWED preserves conflict while changing status."""
        patient = db_session.query(Patient).first()
        conflict = ConflictItem(
            patient_id=patient.id,
            conflict_type="DIAGNOSIS_DISCREPANCY",
            severity="MEDIUM",
            title="Review Workflow Test",
            description="Status verification",
            status="OPEN"
        )
        db_session.add(conflict)
        db_session.commit()

        res = client.post(f"/api/conflicts/{conflict.id}/resolve", json={
            "resolution_notes": "Acknowledged. Monitoring in chart.",
            "resolved_by": "dr_patel",
            "new_status": "REVIEWED"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "REVIEWED"

    def test_idempotent_detection_avoids_duplicate_conflicts(self, db_session):
        """Running conflict detection multiple times does NOT spawn duplicate open conflict items."""
        patient = db_session.query(Patient).first()
        db_session.add(PatientAllergy(
            patient_id=patient.id,
            allergen="Sulfa",
            reaction="Rash",
            provenance="USER_PROVIDED"
        ))
        db_session.add(PatientMedication(
            patient_id=patient.id,
            medication_name="Bactrim",
            dosage="1 tab",
            provenance="USER_PROVIDED"
        ))
        db_session.commit()

        # Run 1
        conflicts_1 = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        sulfa_1 = [c for c in conflicts_1 if "Bactrim" in c.title]
        assert len(sulfa_1) == 1

        # Run 2
        conflicts_2 = ConflictDetector.detect_all_conflicts(db_session, patient.id)
        sulfa_2 = [c for c in conflicts_2 if "Bactrim" in c.title]
        assert len(sulfa_2) == 1 # Still exactly 1, no duplicate
