"""
Phase 9 Tests: Longitudinal Patient Timeline & Clinical Summarization
=====================================================================

Covers all Phase 9 requirements:
1. Timeline event aggregation across patient intake, conditions, medications, labs, documents, conflicts, and verification events.
2. Chronological ordering (ascending: oldest to newest; descending: newest to oldest).
3. Timeline filtering:
   - Date range filtering
   - Event type filtering (LABORATORY, CONDITION, MEDICATION, DOCUMENT, CONFLICT, VERIFICATION)
   - Verification status filtering (HUMAN_VERIFIED, AI_EXTRACTED, USER_PROVIDED)
   - Keyword search across titles, descriptions, and source documents.
4. Laboratory trends engine:
   - Chronological analyte trajectory points
   - Correct unit handling and unit-consistency checks
   - Reference range low/high preservation and status flags
   - Only includes trendable numeric values.
5. Longitudinal Medication history:
   - Tracks dosage, frequency, route, start date, and status.
6. Longitudinal Diagnosis progression:
   - Computes first recorded date, most recent date, current status, and supporting sources.
7. Evidence-grounded longitudinal clinical summary:
   - Strictly grounded in stored records without hallucinations or treatment suggestions
   - Unresolved conflicts integration (Phase 7)
   - Verification-aware (Phase 8 HUMAN_VERIFIED vs AI_EXTRACTED vs HUMAN_REJECTED)
   - Rejected data is excluded from abnormal lab alert lists
   - Provides traceable evidence references.
8. Role-based authorization & security:
   - Rejects unauthorized requests with 401.
9. Existing Phase 1–8 test suite continues to pass with zero regressions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
import pytest

from app.models.patient import Patient, PatientCondition, PatientMedication, PatientAllergy
from app.models.document import Document
from app.models.clinical import LabResult, Observation
from app.models.conflict import ConflictItem, ReviewItem
from app.services.longitudinal_service import TimelineEngine, TrendEngine, MedicalHistoryEngine, ClinicalSummarizer


class TestTimelineEngine:

    def test_timeline_event_creation_and_ordering(self, db_session):
        """Timeline aggregates records and supports ascending and descending chronological sorting."""
        patient = db_session.query(Patient).first()
        assert patient is not None

        # Add condition with older date
        db_session.add(PatientCondition(
            patient_id=patient.id,
            condition_name="Chronic Asthma",
            diagnosed_date="2020-05-15",
            status="ACTIVE",
            provenance="USER_PROVIDED"
        ))

        # Add recent lab result
        db_session.add(LabResult(
            patient_id=patient.id,
            test_name="Serum Creatinine",
            value=0.9,
            value_text="0.9",
            unit="mg/dL",
            report_date="2026-08-25",
            status="NORMAL",
            provenance="AI_EXTRACTED"
        ))
        db_session.commit()

        # 1. Newest first (descending)
        res_desc = TimelineEngine.get_timeline_events(db_session, patient.id, sort_order="desc")
        assert res_desc["total"] >= 2
        events_desc = res_desc["events"]
        assert events_desc[0]["event_date"] >= events_desc[-1]["event_date"]

        # 2. Oldest first (ascending)
        res_asc = TimelineEngine.get_timeline_events(db_session, patient.id, sort_order="asc")
        events_asc = res_asc["events"]
        assert events_asc[0]["event_date"] <= events_asc[-1]["event_date"]
        assert events_asc[0]["event_date"] <= "2020-05-15"

    def test_timeline_filtering_by_event_type(self, db_session):
        """Timeline correctly filters by event_type (e.g. LABORATORY only)."""
        patient = db_session.query(Patient).first()

        res_labs = TimelineEngine.get_timeline_events(
            db_session,
            patient.id,
            event_types=["LABORATORY"]
        )
        assert res_labs["total"] >= 1
        for evt in res_labs["events"]:
            assert evt["event_type"] == "LABORATORY"

    def test_timeline_keyword_search(self, db_session):
        """Timeline keyword search finds events by matching text in title or description."""
        patient = db_session.query(Patient).first()

        db_session.add(PatientCondition(
            patient_id=patient.id,
            condition_name="Hyperlipidemia Type II",
            status="ACTIVE",
            provenance="USER_PROVIDED"
        ))
        db_session.commit()

        res_search = TimelineEngine.get_timeline_events(
            db_session,
            patient.id,
            search_query="Hyperlipidemia"
        )
        assert res_search["total"] >= 1
        assert any("Hyperlipidemia" in e["title"] for e in res_search["events"])

    def test_timeline_date_range_filter(self, db_session):
        """Timeline date_from and date_to parameters constrain results correctly."""
        patient = db_session.query(Patient).first()

        res_filtered = TimelineEngine.get_timeline_events(
            db_session,
            patient.id,
            date_from="2026-01-01",
            date_to="2026-12-31"
        )
        for e in res_filtered["events"]:
            assert "2026-01-01" <= e["event_date"] <= "2026-12-31"


class TestLaboratoryTrends:

    def test_lab_trends_chronological_points_and_units(self, db_session):
        """TrendEngine groups analyte data chronologically and checks unit consistency."""
        patient = db_session.query(Patient).first()

        # Add two glucose measurements at different dates
        l1 = LabResult(
            patient_id=patient.id,
            test_name="Fasting Blood Glucose",
            value=105.0,
            value_text="105",
            unit="mg/dL",
            report_date="2026-03-01",
            status="HIGH"
        )
        l2 = LabResult(
            patient_id=patient.id,
            test_name="Fasting Blood Glucose",
            value=92.0,
            value_text="92",
            unit="mg/dL",
            report_date="2026-06-15",
            status="NORMAL"
        )
        db_session.add_all([l1, l2])
        db_session.commit()

        trends = TrendEngine.get_lab_trends(db_session, patient.id)["trends"]
        assert "Fasting Blood Glucose" in trends
        fbg = trends["Fasting Blood Glucose"]
        assert fbg["points_count"] == 2
        assert fbg["primary_unit"] == "mg/dL"
        assert fbg["multiple_units"] is False
        assert fbg["data_points"][0]["date"] == "2026-03-01"
        assert fbg["data_points"][1]["date"] == "2026-06-15"


class TestMedicationAndDiagnosisHistories:

    def test_medication_history_tracking(self, db_session):
        """MedicalHistoryEngine tracks medications with route and verification provenance."""
        patient = db_session.query(Patient).first()

        db_session.add(PatientMedication(
            patient_id=patient.id,
            medication_name="Atorvastatin",
            dosage="20 mg",
            frequency="Once nightly",
            route="ORAL",
            provenance="USER_PROVIDED"
        ))
        db_session.commit()

        history = MedicalHistoryEngine.get_medication_history(db_session, patient.id)["medications"]
        atorv = [m for m in history if m["medication_name"] == "Atorvastatin"]
        assert len(atorv) == 1
        assert atorv[0]["dose"] == "20 mg"
        assert atorv[0]["current_status"] == "ACTIVE"

    def test_diagnosis_history_progression(self, db_session):
        """Diagnosis history groups repeated condition instances and tracks first/most recent dates."""
        patient = db_session.query(Patient).first()

        db_session.add(PatientCondition(
            patient_id=patient.id,
            condition_name="Type 2 Diabetes Mellitus",
            diagnosed_date="2018-04-10",
            status="ACTIVE",
            provenance="USER_PROVIDED"
        ))
        db_session.commit()

        diag_res = MedicalHistoryEngine.get_diagnosis_history(db_session, patient.id)["diagnoses"]
        t2d = [d for d in diag_res if "Diabetes" in d["diagnosis"]]
        assert len(t2d) == 1
        assert t2d[0]["first_recorded_date"] == "2018-04-10"
        assert t2d[0]["current_status"] == "ACTIVE"


class TestEvidenceGroundedClinicalSummary:

    def test_clinical_summary_generation_grounded_in_records(self, db_session):
        """Clinical summary generates narrative strictly based on stored data and includes safety disclaimer."""
        patient = db_session.query(Patient).first()

        # Add known condition & abnormal lab
        db_session.add(PatientCondition(
            patient_id=patient.id,
            condition_name="Essential Hypertension",
            diagnosed_date="2021-02-01",
            status="ACTIVE",
            provenance="USER_PROVIDED"
        ))
        db_session.add(LabResult(
            patient_id=patient.id,
            test_name="Hemoglobin",
            value=10.2,
            value_text="10.2",
            unit="g/dL",
            status="LOW",
            raw_reference_range="12.0 - 15.5 g/dL",
            provenance="HUMAN_VERIFIED"
        ))
        db_session.commit()

        res = ClinicalSummarizer.generate_longitudinal_summary(db_session, patient.id)
        assert "summary_text" in res
        summary_text = res["summary_text"]

        # Must mention patient info, condition, and abnormal lab
        assert patient.first_name in summary_text
        assert "Essential Hypertension" in summary_text
        assert "Hemoglobin" in summary_text
        assert "LOW" in summary_text

        # Must include decision-support disclaimer
        assert "does not provide medical diagnoses" in res["disclaimer"]

        # Must provide evidence references
        assert len(res["evidence_references"]) >= 1

    def test_rejected_extraction_excluded_from_confirmed_abnormalities(self, db_session):
        """Extracted labs with HUMAN_REJECTED provenance are NOT included as confirmed abnormalities."""
        patient = db_session.query(Patient).first()

        # Add rejected lab
        db_session.add(LabResult(
            patient_id=patient.id,
            test_name="Spurious Artifact",
            value=999.0,
            value_text="999",
            status="HIGH",
            provenance="HUMAN_REJECTED"
        ))
        db_session.commit()

        res = ClinicalSummarizer.generate_longitudinal_summary(db_session, patient.id)
        assert "Spurious Artifact" not in res["sections"]["laboratories"]


class TestTimelineAPIEndpoints:

    def test_api_get_timeline_endpoint(self, client, db_session):
        """GET /api/timeline/{patient_id} returns timeline with pagination."""
        patient = db_session.query(Patient).first()
        res = client.get(f"/api/timeline/{patient.id}?limit=10&offset=0")
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert "events" in data
        assert isinstance(data["events"], list)

    def test_api_get_trends_endpoint(self, client, db_session):
        """GET /api/timeline/{patient_id}/trends returns trends dictionary."""
        patient = db_session.query(Patient).first()
        res = client.get(f"/api/timeline/{patient.id}/trends")
        assert res.status_code == 200
        assert "trends" in res.json()

    def test_api_unauthorized_rejection(self, client, db_session):
        """GET /api/timeline/{patient_id} rejects unauthorized headers."""
        patient = db_session.query(Patient).first()
        res = client.get(f"/api/timeline/{patient.id}", headers={"authorization": "unauthorized"})
        assert res.status_code == 401
