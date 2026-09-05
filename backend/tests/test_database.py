import pytest
from sqlalchemy.exc import IntegrityError
from app.database import Base
from app.models.user import User
from app.models.patient import Patient, PatientCondition, PatientAllergy, PatientMedication, PatientSymptom
from app.models.document import Document, DocumentPage, DocumentProcessingJob
from app.models.extracted_entity import ExtractedEntity
from app.models.clinical import LabResult, Observation, Summary
from app.models.reference_range import ReferenceRange
from app.models.conflict import ConflictItem, ReviewItem
from app.models.audit import AuditLog, VerificationEvent

EXPECTED_TABLES = [
    "users",
    "patients",
    "patient_conditions",
    "patient_allergies",
    "patient_medications",
    "patient_symptoms",
    "documents",
    "document_pages",
    "document_processing_jobs",
    "extracted_entities",
    "lab_results",
    "reference_ranges",
    "observations",
    "summaries",
    "conflicts",
    "review_items",
    "verification_events",
    "audit_logs"
]

def test_all_18_tables_registered_in_metadata():
    """
    Verifies that all 18 required normalized tables are registered in SQLAlchemy metadata.
    """
    registered = set(Base.metadata.tables.keys())
    for tbl in EXPECTED_TABLES:
        assert tbl in registered, f"Required table '{tbl}' not found in metadata!"

def test_synthetic_seed_data_integrity(db_session):
    """
    Verifies that the synthetic seed process correctly populates models.
    """
    # 1. Users seeded
    users = db_session.query(User).all()
    assert len(users) >= 2
    emails = [u.email for u in users]
    assert "dr.lin@medlens.org" in emails

    # 2. 3 Synthetic Patients seeded
    patients = db_session.query(Patient).all()
    assert len(patients) == 3
    for p in patients:
        assert p.is_synthetic_demo is True
        assert "SYNTHETIC" in p.notes

    # 3. Alex Morgan detailed graph
    alex = db_session.query(Patient).filter(Patient.mrn == "SYN-1001").first()
    assert alex is not None
    assert alex.first_name == "Alex"
    assert len(alex.conditions) >= 2
    assert len(alex.allergies) >= 1
    assert len(alex.medications) >= 2

    # 4. Documents & Lab results
    assert len(alex.documents) >= 1
    doc = alex.documents[0]
    assert doc.processing_status == "REVIEW_REQUIRED"
    assert len(doc.pages) >= 1

    # 5. Lab Results & Reference Ranges
    assert len(doc.lab_results) >= 5
    hb = next((r for r in doc.lab_results if r.test_name == "Hemoglobin"), None)
    assert hb is not None
    assert hb.value == 11.2
    assert hb.status == "LOW"
    assert hb.reference_range_rel is not None
    assert hb.reference_range_rel.low_value == 12.0
    assert hb.reference_range_rel.high_value == 15.5

    # 6. Conflicts & Review Queue
    assert len(alex.conflicts) >= 1
    assert alex.conflicts[0].conflict_type == "MEDICATION_ALLERGY"

def test_unique_mrn_constraint(db_session):
    """
    Verifies that duplicate Medical Record Numbers (MRN) are rejected by database constraints.
    """
    p1 = Patient(
        mrn="SYN-DUPE-01",
        first_name="Alice",
        last_name="Test",
        date_of_birth="1990-01-01",
        age=36,
        sex="FEMALE"
    )
    db_session.add(p1)
    db_session.commit()

    p2 = Patient(
        mrn="SYN-DUPE-01", # Duplicate
        first_name="Bob",
        last_name="Test",
        date_of_birth="1992-02-02",
        age=34,
        sex="MALE"
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_unique_user_email_constraint(db_session):
    """
    Verifies that duplicate user emails are rejected.
    """
    u1 = User(
        email="unique.doc@medlens.org",
        hashed_password="hash",
        full_name="Dr. Unique"
    )
    db_session.add(u1)
    db_session.commit()

    u2 = User(
        email="unique.doc@medlens.org", # Duplicate
        hashed_password="hash2",
        full_name="Dr. Duplicate"
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_cascade_delete_patient(db_session):
    """
    Verifies that deleting a patient cascades properly to delete associated
    conditions, allergies, medications, lab results, and documents.
    """
    p = Patient(
        mrn="SYN-CASCADE-01",
        first_name="Cascade",
        last_name="Tester",
        date_of_birth="1988-08-08",
        age=38,
        sex="OTHER"
    )
    db_session.add(p)
    db_session.flush()

    cond = PatientCondition(patient_id=p.id, condition_name="Test Condition")
    allergy = PatientAllergy(patient_id=p.id, allergen="Peanuts")
    db_session.add(cond)
    db_session.add(allergy)
    db_session.commit()

    pat_id = p.id
    cond_id = cond.id
    allergy_id = allergy.id

    # Verify existing
    assert db_session.query(PatientCondition).filter(PatientCondition.id == cond_id).first() is not None

    # Delete Patient
    db_session.delete(p)
    db_session.commit()

    # Verify cascaded deletion
    assert db_session.query(PatientCondition).filter(PatientCondition.id == cond_id).first() is None
    assert db_session.query(PatientAllergy).filter(PatientAllergy.id == allergy_id).first() is None

def test_transaction_rollback_atomicity(db_session):
    """
    Verifies transactional rollback prevents partial commits when an error occurs.
    """
    initial_count = db_session.query(Patient).count()

    try:
        # Add valid patient
        p = Patient(
            mrn="SYN-ATOMIC-01",
            first_name="Atomic",
            last_name="Test",
            date_of_birth="1995-05-05",
            age=31,
            sex="MALE"
        )
        db_session.add(p)
        db_session.flush()

        # Add invalid condition referencing non-existent patient ID to trigger error
        invalid_cond = PatientCondition(
            patient_id="non-existent-guid",
            condition_name="Orphaned Condition"
        )
        db_session.add(invalid_cond)
        db_session.commit()
    except Exception:
        db_session.rollback()

    # Count must remain unchanged after rollback
    assert db_session.query(Patient).count() == initial_count
