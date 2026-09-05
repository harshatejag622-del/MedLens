from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.patient import Patient, PatientCondition, PatientAllergy, PatientMedication, PatientSymptom
from app.models.document import Document, DocumentPage, DocumentProcessingJob
from app.models.extracted_entity import ExtractedEntity
from app.models.clinical import LabResult, Observation, Summary
from app.models.reference_range import ReferenceRange
from app.models.conflict import ConflictItem, ReviewItem
from app.models.audit import AuditLog, VerificationEvent
from app.demo_data.synthetic_records import SYNTHETIC_PATIENTS
from app.services.audit_service import AuditService

def seed_database(db: Session):
    """
    Seeds initial synthetic demo data across all 18 tables.
    Every entity is explicitly marked as SYNTHETIC DEMO DATA.
    """
    if db.query(Patient).count() > 0:
        return

    print("Seeding complete synthetic demo database across all 18 tables...")

    # 1. Seed Clinician & Auditor Users
    clinician_user = User(
        email="dr.lin@medlens.org",
        hashed_password="$2b$12$e8YkYf8e2k1k0Q8W9O3.8O6Z1mH2o3q4r5s6t7u8v9w0x1y2z3a4b", # demo hash
        full_name="Dr. Sarah Lin, MD",
        role="CLINICIAN",
        is_active=True
    )
    auditor_user = User(
        email="auditor@medlens.org",
        hashed_password="$2b$12$e8YkYf8e2k1k0Q8W9O3.8O6Z1mH2o3q4r5s6t7u8v9w0x1y2z3a4b",
        full_name="Marcus Vance, CPHIMS",
        role="AUDITOR",
        is_active=True
    )
    db.add(clinician_user)
    db.add(auditor_user)
    db.flush()

    # 2. Seed 3 Synthetic Demo Patients
    for pat_data in SYNTHETIC_PATIENTS:
        patient = Patient(
            mrn=pat_data["mrn"],
            first_name=pat_data["first_name"],
            last_name=pat_data["last_name"],
            date_of_birth=pat_data["date_of_birth"],
            age=pat_data["age"],
            sex=pat_data["sex"],
            contact_phone=pat_data["contact_phone"],
            contact_email=pat_data["contact_email"],
            relevant_history=pat_data.get("relevant_history"),
            notes=f"SYNTHETIC DEMO PATIENT: {pat_data['notes']}",
            is_archived=False,
            is_synthetic_demo=True
        )
        db.add(patient)
        db.flush()

        # Conditions
        for c in pat_data.get("conditions", []):
            db.add(PatientCondition(
                patient_id=patient.id,
                condition_name=c["condition_name"],
                status=c["status"],
                diagnosed_date=c["diagnosed_date"],
                notes=c.get("notes"),
                provenance="USER_PROVIDED"
            ))

        # Allergies
        for a in pat_data.get("allergies", []):
            db.add(PatientAllergy(
                patient_id=patient.id,
                allergen=a["allergen"],
                reaction=a["reaction"],
                severity=a["severity"],
                provenance="USER_PROVIDED"
            ))

        # Medications
        for m in pat_data.get("medications", []):
            db.add(PatientMedication(
                patient_id=patient.id,
                medication_name=m["medication_name"],
                dosage=m["dosage"],
                frequency=m["frequency"],
                route=m["route"],
                provenance="USER_PROVIDED"
            ))

        # Symptoms
        for s in pat_data.get("symptoms", []):
            db.add(PatientSymptom(
                patient_id=patient.id,
                symptom=s["symptom"],
                duration=s["duration"],
                severity=s["severity"],
                provenance="USER_PROVIDED"
            ))

        # 3. For Alex Morgan: Seed Document, Pages, ProcessingJob, Extracted Entities, Lab Results, Reference Ranges, Conflicts, Reviews, Summaries
        if patient.mrn == "SYN-1001":
            doc = Document(
                patient_id=patient.id,
                original_filename="alex_morgan_cbc_panel_2026.txt",
                stored_filename="alex_morgan_cbc_panel_2026.txt",
                file_type="text/plain",
                file_size_bytes=1420,
                sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                report_date="2026-08-20",
                document_type="LABORATORY_REPORT",
                facility="MetroHealth Diagnostic Services",
                processing_status="REVIEW_REQUIRED",
                raw_text="MetroHealth Diagnostic Services\nPatient: Alex Morgan | DoB: 1981-04-12 | Sex: F\nReport Date: 2026-08-20\n\nTEST NAME          RESULT    UNIT       REFERENCE RANGE\nHemoglobin         11.2      g/dL       12.0–15.5\nWBC Count          6.8       x10^3/uL   4.5–11.0\nPlatelets          245       x10^3/uL   150–450\nFerritin           18        ng/mL      15–150\nTotal Iron         45        ug/dL      60–170\n\nPrescribed: Amoxicillin 500mg PO TID for secondary upper respiratory finding."
            )
            db.add(doc)
            db.flush()

            # DocumentPage
            page = DocumentPage(
                document_id=doc.id,
                page_number=1,
                text_content=doc.raw_text
            )
            db.add(page)

            # DocumentProcessingJob
            job = DocumentProcessingJob(
                document_id=doc.id,
                status="COMPLETED",
                current_step="EXTRACTION_VERIFIED",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                log_messages="[INFO] Ingestion completed. [INFO] Checksum verified. [INFO] Extraction finished."
            )
            db.add(job)

            # Extracted Entities
            db.add(ExtractedEntity(
                document_id=doc.id,
                patient_id=patient.id,
                entity_type="MEDICATION",
                name="Amoxicillin",
                value="500mg",
                unit="mg",
                source_evidence="Prescribed: Amoxicillin 500mg PO TID",
                page_number=1,
                confidence=0.97,
                provenance="AI_EXTRACTED"
            ))

            # Lab Results & Reference Ranges
            labs_data = [
                {"name": "Hemoglobin", "val": 11.2, "unit": "g/dL", "raw_range": "12.0–15.5 g/dL", "low": 12.0, "high": 15.5, "status": "LOW", "conf": 0.98, "snippet": "Hemoglobin 11.2 g/dL 12.0–15.5"},
                {"name": "WBC Count", "val": 6.8, "unit": "x10^3/uL", "raw_range": "4.5–11.0 x10^3/uL", "low": 4.5, "high": 11.0, "status": "NORMAL", "conf": 0.99, "snippet": "WBC Count 6.8 x10^3/uL 4.5–11.0"},
                {"name": "Platelets", "val": 245.0, "unit": "x10^3/uL", "raw_range": "150–450 x10^3/uL", "low": 150.0, "high": 450.0, "status": "NORMAL", "conf": 0.96, "snippet": "Platelets 245 x10^3/uL 150–450"},
                {"name": "Ferritin", "val": 18.0, "unit": "ng/mL", "raw_range": "15–150 ng/mL", "low": 15.0, "high": 150.0, "status": "NORMAL", "conf": 0.94, "snippet": "Ferritin 18 ng/mL 15–150"},
                {"name": "Total Iron", "val": 45.0, "unit": "ug/dL", "raw_range": "60–170 ug/dL", "low": 60.0, "high": 170.0, "status": "LOW", "conf": 0.95, "snippet": "Total Iron 45 ug/dL 60–170"}
            ]

            for item in labs_data:
                lab_res = LabResult(
                    patient_id=patient.id,
                    document_id=doc.id,
                    test_name=item["name"],
                    value=item["val"],
                    value_text=str(item["val"]),
                    unit=item["unit"],
                    raw_reference_range=item["raw_range"],
                    reference_low=item["low"],
                    reference_high=item["high"],
                    status=item["status"],
                    source_evidence=item["snippet"],
                    page_number=1,
                    confidence=item["conf"],
                    provenance="AI_EXTRACTED",
                    report_date="2026-08-20"
                )
                db.add(lab_res)
                db.flush()

                # ReferenceRange row
                db.add(ReferenceRange(
                    lab_result_id=lab_res.id,
                    raw_text=item["raw_range"],
                    low_value=item["low"],
                    high_value=item["high"],
                    unit=item["unit"],
                    is_assessable=True,
                    source_notes=f"Source laboratory reference range: {item['raw_range']}"
                ))

            # Observation
            db.add(Observation(
                patient_id=patient.id,
                document_id=doc.id,
                category="FINDING",
                content="Specimen integrity acceptable. No gross hemolysis noted.",
                source_evidence="Specimen integrity acceptable.",
                confidence=0.99,
                provenance="AI_EXTRACTED"
            ))

            # Conflict: Penicillin Allergy vs Amoxicillin Medication
            conflict = ConflictItem(
                patient_id=patient.id,
                conflict_type="MEDICATION_ALLERGY",
                severity="HIGH",
                title="Potential Cross-Reactive Medication/Allergy Inconsistency: Amoxicillin",
                description="Patient profile records an allergy to 'Penicillin', while uploaded document lists medication 'Amoxicillin'. Please verify against the original source.",
                source_a="Patient Allergy Profile: Penicillin",
                source_b="Extracted Document Medication: Amoxicillin",
                status="UNRESOLVED"
            )
            db.add(conflict)

            # Review Item: Total Iron
            review_item = ReviewItem(
                document_id=doc.id,
                patient_id=patient.id,
                target_type="LAB_RESULT",
                target_id=lab_res.id,
                field_name="Total Iron",
                current_value="45 ug/dL (LOW)",
                reason="Value below source reference range (60–170 ug/dL). Awaiting clinical review.",
                priority="HIGH",
                status="PENDING"
            )
            db.add(review_item)

            # Summary
            summary = Summary(
                patient_id=patient.id,
                summary_text=(
                    "According to the uploaded report dated 2026-08-20 from MetroHealth Diagnostic Services, "
                    "laboratory values were recorded for Hemoglobin, WBC Count, Platelets, Ferritin, and Total Iron. "
                    "Hemoglobin (11.2 g/dL) and Total Iron (45 ug/dL) are below the reference ranges stated in the report. "
                    "WBC Count, Platelets, and Ferritin are within the reference ranges provided by the laboratory."
                ),
                disclaimer=(
                    "MedLens is an information organization and understanding tool. "
                    "It does not provide medical diagnosis or treatment recommendations. "
                    "Always consult a qualified healthcare professional for medical decisions."
                ),
                model_provider="local",
                provenance="AI_GENERATED"
            )
            db.add(summary)

            # Verification Event
            db.add(VerificationEvent(
                target_id=lab_res.id,
                target_type="LAB_RESULT",
                verified_by="clinician_user",
                original_value="11.2",
                corrected_value="11.2",
                change_reason="Verified against document scan page 1 snippet.",
                provenance="HUMAN_VERIFIED"
            ))

        AuditService.log_action(
            db=db,
            action="PATIENT_CREATED",
            entity_type="PATIENT",
            entity_id=patient.id,
            details={"mrn": patient.mrn, "note": "SYNTHETIC DEMO PATIENT intake seeded"}
        )

    db.commit()
    print("Database seeding completed across all 18 tables.")
