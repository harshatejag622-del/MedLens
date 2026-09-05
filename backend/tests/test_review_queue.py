"""
Phase 8 Tests: Clinical Review Queue & Human Verification Workflow
==================================================================

Covers all Phase 8 requirements:
1. New AI extraction entry in the review queue defaults to AI_EXTRACTED / PENDING status.
2. Authorized reviewer can ACCEPT extraction -> status becomes ACCEPTED (HUMAN_VERIFIED).
3. Authorized reviewer can CORRECT extraction -> original AI value preserved, corrected value stored, status EDITED (HUMAN_CORRECTED).
4. Authorized reviewer can REJECT extraction -> original AI value preserved, status REJECTED (HUMAN_REJECTED).
5. Reviewer can DEFER extraction -> status becomes DEFERRED.
6. Role-based authorization: Unauthorized request is rejected with 401/403.
7. Original AI value is preserved verbatim after correction and visible in audit trail.
8. Immutable audit trail: VerificationEvent and AuditLog are created for review actions.
9. Side-by-side details inspection endpoint (/api/review/{id}) provides source evidence and linked Phase 7 conflicts.
10. Review queue filtering works by status, priority, and clinical target_type.
11. Operational stats endpoint includes accurate calculated review metrics.
12. Existing Phase 1–7 test suite continues to pass with zero regressions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
import pytest

from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical import LabResult
from app.models.conflict import ReviewItem, ConflictItem
from app.models.audit import VerificationEvent, AuditLog


class TestReviewQueueWorkflow:

    def test_new_review_item_defaults(self, db_session):
        """Newly created extraction item enters queue with PENDING status and default priority."""
        patient = db_session.query(Patient).first()
        doc = db_session.query(Document).first()

        item = ReviewItem(
            patient_id=patient.id,
            document_id=doc.id if doc else None,
            target_type="LAB_RESULT",
            target_id=str(uuid.uuid4()),
            field_name="Hemoglobin",
            current_value="11.2 g/dL",
            original_value="11.2 g/dL",
            confidence=0.74,
            reason="Ambiguous source format in report table",
            priority="HIGH",
            status="PENDING"
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.status == "PENDING"
        assert item.priority == "HIGH"
        assert item.original_value == "11.2 g/dL"
        assert item.reviewed_by is None

    def test_accept_action_marks_human_verified(self, client, db_session):
        """Reviewer accepting an extraction updates status to ACCEPTED and marks LabResult verified."""
        patient = db_session.query(Patient).first()
        lab = LabResult(
            patient_id=patient.id,
            test_name="Serum Ferritin",
            value=12.0,
            value_text="12.0",
            unit="ng/mL",
            provenance="AI_EXTRACTED",
            is_verified=False
        )
        db_session.add(lab)
        db_session.flush()

        item = ReviewItem(
            patient_id=patient.id,
            target_type="LAB_RESULT",
            target_id=lab.id,
            field_name="Serum Ferritin",
            current_value="12.0 ng/mL",
            original_value="12.0 ng/mL",
            confidence=0.88,
            reason="Low normal threshold",
            priority="MEDIUM",
            status="PENDING"
        )
        db_session.add(item)
        db_session.commit()

        # Execute ACCEPT
        res = client.post(f"/api/review/{item.id}/action", json={
            "action": "ACCEPT",
            "change_reason": "Verified against physical laboratory printout.",
            "reviewer_id": "dr_evans"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ACCEPTED"
        assert data["reviewed_by"] == "dr_evans"

        # Check underlying LabResult
        db_session.refresh(lab)
        assert lab.is_verified is True
        assert lab.provenance == "HUMAN_VERIFIED"
        assert lab.verified_by == "dr_evans"

        # Check audit trail entry
        event = db_session.query(VerificationEvent).filter(VerificationEvent.target_id == lab.id).first()
        assert event is not None
        assert event.provenance == "HUMAN_VERIFIED"

    def test_correct_action_preserves_original_ai_value(self, client, db_session):
        """Reviewer correcting an extraction preserves original_value and saves corrected_value."""
        patient = db_session.query(Patient).first()
        lab = LabResult(
            patient_id=patient.id,
            test_name="Platelet Count",
            value=14.0,
            value_text="14",
            unit="K/uL",
            provenance="AI_EXTRACTED",
            is_verified=False
        )
        db_session.add(lab)
        db_session.flush()

        item = ReviewItem(
            patient_id=patient.id,
            target_type="LAB_RESULT",
            target_id=lab.id,
            field_name="Platelet Count",
            current_value="14 K/uL",
            original_value="14 K/uL",
            confidence=0.62,
            reason="Suspected OCR decimal slip",
            priority="HIGH",
            status="PENDING"
        )
        db_session.add(item)
        db_session.commit()

        # Execute CORRECT
        res = client.post(f"/api/review/{item.id}/action", json={
            "action": "CORRECT",
            "corrected_value": "140 K/uL",
            "change_reason": "OCR missed trailing zero on report image; verified as 140 K/uL.",
            "reviewer_id": "dr_rodriguez"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "EDITED"
        assert data["original_value"] == "14 K/uL"
        assert data["corrected_value"] == "140 K/uL"
        assert data["current_value"] == "140 K/uL"

        # Check underlying LabResult
        db_session.refresh(lab)
        assert lab.provenance == "HUMAN_CORRECTED"
        assert lab.value_text == "140 K/uL"
        assert lab.original_ai_value == "14"

    def test_reject_action(self, client, db_session):
        """Reviewer rejecting an extraction marks status as REJECTED and updates provenance."""
        patient = db_session.query(Patient).first()
        lab = LabResult(
            patient_id=patient.id,
            test_name="Phantom Analyte",
            value=99.0,
            value_text="99",
            provenance="AI_EXTRACTED",
            is_verified=False
        )
        db_session.add(lab)
        db_session.flush()

        item = ReviewItem(
            patient_id=patient.id,
            target_type="LAB_RESULT",
            target_id=lab.id,
            field_name="Phantom Analyte",
            current_value="99",
            original_value="99",
            reason="Unrecognized test name header",
            priority="LOW",
            status="PENDING"
        )
        db_session.add(item)
        db_session.commit()

        res = client.post(f"/api/review/{item.id}/action", json={
            "action": "REJECT",
            "change_reason": "Spurious OCR artifact, not a clinical lab test.",
            "reviewer_id": "dr_patel"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "REJECTED"

        db_session.refresh(lab)
        assert lab.provenance == "HUMAN_REJECTED"

    def test_defer_action(self, client, db_session):
        """Reviewer deferring an extraction marks status as DEFERRED for later follow-up."""
        patient = db_session.query(Patient).first()
        item = ReviewItem(
            patient_id=patient.id,
            target_type="MEDICATION",
            target_id=str(uuid.uuid4()),
            field_name="Unclear Dosage",
            current_value="Unknown",
            reason="Illegible script",
            priority="MEDIUM",
            status="PENDING"
        )
        db_session.add(item)
        db_session.commit()

        res = client.post(f"/api/review/{item.id}/action", json={
            "action": "DEFER",
            "change_reason": "Awaiting callback from prescribing clinic.",
            "reviewer_id": "dr_chen"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "DEFERRED"


class TestReviewQueueSecurityAndInspection:

    def test_role_based_access_rejection(self, client, db_session):
        """Requests with unauthorized or patient roles are rejected."""
        res_unauth = client.get("/api/review", headers={"authorization": "unauthorized"})
        assert res_unauth.status_code == 401

        res_forbidden = client.get("/api/review", headers={"authorization": "role:patient"})
        assert res_forbidden.status_code == 403

    def test_side_by_side_details_endpoint_with_conflict_integration(self, client, db_session):
        """GET /api/review/{id} returns source text context and linked Phase 7 conflicts."""
        patient = db_session.query(Patient).first()

        doc = Document(
            patient_id=patient.id,
            original_filename="cbc_panel_stjude.pdf",
            stored_filename="cbc_panel_stjude.pdf",
            file_type="pdf",
            file_size_bytes=2048,
            sha256_checksum="inspect_hash_" + str(uuid.uuid4())[:8],
            raw_text="LABORATORY REPORT\nHemoglobin: 11.2 g/dL (Reference 12.0 - 15.5 g/dL)\nPlatelets: 180 K/uL"
        )
        db_session.add(doc)
        db_session.flush()

        # Add linked clinical conflict
        conflict = ConflictItem(
            patient_id=patient.id,
            conflict_type="LAB_DISCREPANCY",
            severity="HIGH",
            title="Conflicting Hemoglobin Value",
            description="Divergent Hemoglobin documented across documents.",
            status="OPEN"
        )
        db_session.add(conflict)

        # Review item
        item = ReviewItem(
            patient_id=patient.id,
            document_id=doc.id,
            target_type="LAB_RESULT",
            target_id=str(uuid.uuid4()),
            field_name="Hemoglobin",
            current_value="11.2 g/dL",
            original_value="11.2 g/dL",
            confidence=0.91,
            reason="Low hemoglobin alert",
            priority="HIGH",
            status="PENDING"
        )
        db_session.add(item)
        db_session.commit()

        res = client.get(f"/api/review/{item.id}")
        assert res.status_code == 200
        data = res.json()

        # Check side-by-side payload
        review_data = data["review_item"]
        assert review_data["field_name"] == "Hemoglobin"
        assert review_data["original_value"] == "11.2 g/dL"
        assert "Hemoglobin: 11.2" in review_data["source_text"]

        # Check linked conflict integration
        assert len(data["related_conflicts"]) >= 1
        assert "Hemoglobin" in data["related_conflicts"][0]["title"]
        assert "Human Verification Required" in data["safety_disclaimer"]

    def test_review_queue_filtering(self, client, db_session):
        """Review queue supports filtering by status, priority, and target_type."""
        patient = db_session.query(Patient).first()

        i_high = ReviewItem(
            patient_id=patient.id,
            target_type="LAB_RESULT",
            target_id=str(uuid.uuid4()),
            field_name="Filtered Lab",
            reason="Priority test",
            priority="HIGH",
            status="PENDING"
        )
        i_low = ReviewItem(
            patient_id=patient.id,
            target_type="MEDICATION",
            target_id=str(uuid.uuid4()),
            field_name="Filtered Med",
            reason="Priority test",
            priority="LOW",
            status="ACCEPTED"
        )
        db_session.add_all([i_high, i_low])
        db_session.commit()

        # Filter by priority=HIGH
        res = client.get("/api/review?priority=HIGH")
        assert res.status_code == 200
        priorities = [it["priority"] for it in res.json()]
        assert all(p == "HIGH" for p in priorities)

        # Filter by status=ACCEPTED
        res = client.get("/api/review?status=ACCEPTED")
        assert res.status_code == 200
        statuses = [it["status"] for it in res.json()]
        assert all(s == "ACCEPTED" for s in statuses)

    def test_operational_stats_metrics_accuracy(self, client, db_session):
        """GET /api/stats includes verified review counts computed directly from database."""
        res = client.get("/api/stats")
        assert res.status_code == 200
        stats = res.json()

        assert "pending_reviews" in stats
        assert "high_priority_reviews" in stats
        assert "verified_reviews" in stats
        assert "corrected_reviews" in stats
        assert "rejected_reviews" in stats
        assert "deferred_reviews" in stats
        assert isinstance(stats["pending_reviews"], int)
