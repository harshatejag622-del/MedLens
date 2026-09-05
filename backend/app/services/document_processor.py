from __future__ import annotations
from app.utils.datetime_utils import utc_now_naive, utc_now
"""
Document Processing Pipeline
==============================
Orchestrates end-to-end AI clinical extraction for a given document:

  1. Read original file bytes from secure storage
  2. Extract page-level text via OCRService
  3. Persist DocumentPage records
  4. Invoke ClinicalExtractionProvider (Gemini or Mock)
  5. Run BusinessValidator (schema + anti-hallucination + evidence grounding)
  6. If validation fails fatally → set document to REVIEW_REQUIRED, log error, exit
  7. If validation passes:
     a. Persist LabResult + ReferenceRange records (AI_EXTRACTED provenance)
     b. Persist Observation records
     c. Persist ExtractedEntity records (symptoms, conditions, medications, allergies)
     d. Create ReviewItem for any low-confidence entities
     e. Update document.processing_status = COMPLETED
     f. Update DocumentProcessingJob
     g. Write AuditLog entry

All database mutations run inside a single transaction. If any mutation fails
the entire operation rolls back and the document is marked FAILED.

Usage:
    from app.services.document_processor import process_document
    result = process_document(db, document_id)
"""


import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clinical import LabResult, Observation
from app.models.conflict import ReviewItem
from app.models.document import Document, DocumentPage, DocumentProcessingJob
from app.models.extracted_entity import ExtractedEntity
from app.models.reference_range import ReferenceRange
from app.services.ai.factory import get_extraction_provider
from app.services.ai.schemas import (
    ClinicalExtractionPayload,
    ExtractionStatus,
    Provenance,
)
from app.services.audit_service import AuditService
from app.services.business_validator import business_validator, BusinessValidationError
from app.services.ocr_service import ocr_service, OCRError
from app.services.reference_range import ReferenceRangeService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Summary of a document processing run."""

    def __init__(
        self,
        document_id: str,
        success: bool,
        status: str,
        lab_results_created: int = 0,
        entities_created: int = 0,
        observations_created: int = 0,
        review_items_created: int = 0,
        warnings: list[str] | None = None,
        error: Optional[str] = None,
    ) -> None:
        self.document_id = document_id
        self.success = success
        self.status = status
        self.lab_results_created = lab_results_created
        self.entities_created = entities_created
        self.observations_created = observations_created
        self.review_items_created = review_items_created
        self.warnings = warnings or []
        self.error = error

    def __repr__(self) -> str:
        return (
            f"ProcessingResult(doc={self.document_id!r}, success={self.success}, "
            f"status={self.status!r}, labs={self.lab_results_created}, error={self.error!r})"
        )


def process_document(db: Session, document_id: str) -> ProcessingResult:
    """
    Execute the full clinical extraction pipeline for a document.

    Args:
        db: Active SQLAlchemy session.
        document_id: UUID of the document to process.

    Returns:
        ProcessingResult describing the outcome.
    """
    doc: Optional[Document] = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return ProcessingResult(
            document_id=document_id,
            success=False,
            status="FAILED",
            error=f"Document {document_id} not found.",
        )

    # --- Get or create processing job ---
    job: Optional[DocumentProcessingJob] = (
        db.query(DocumentProcessingJob)
        .filter(DocumentProcessingJob.document_id == document_id)
        .order_by(DocumentProcessingJob.started_at.desc())
        .first()
    )
    if not job:
        job = DocumentProcessingJob(
            id=str(uuid.uuid4()),
            document_id=document_id,
            status="PROCESSING",
            current_step="INITIALIZING",
            started_at=utc_now_naive(),
            log_messages=f"[{utc_now_naive().isoformat()}] Processing started.",
        )
        db.add(job)

    # Mark document as PROCESSING
    doc.processing_status = "PROCESSING"
    doc.processing_error = None
    job.status = "PROCESSING"
    job.current_step = "OCR_EXTRACTION"
    job.log_messages = (job.log_messages or "") + f"\n[{utc_now_naive().isoformat()}] OCR extraction started."
    db.commit()

    # ---------------------------------------------------------------
    # Step 1: OCR — extract page texts
    # ---------------------------------------------------------------
    try:
        file_path = StorageService.get_document_path(doc.patient_id, doc.stored_filename)
        ocr_result = ocr_service.extract(file_path, document_id)
    except OCRError as exc:
        return _fail_document(db, doc, job, f"OCR extraction failed: {exc}")
    except Exception as exc:
        return _fail_document(db, doc, job, f"Unexpected OCR error: {exc}")

    if not ocr_result.full_text.strip():
        return _fail_document(
            db, doc, job,
            "Document text extraction produced empty content. "
            "Document may be image-based and require OCR, or be empty."
        )

    # ---------------------------------------------------------------
    # Step 2: Persist DocumentPage records
    # ---------------------------------------------------------------
    job.current_step = "PERSISTING_PAGES"
    job.log_messages += f"\n[{utc_now_naive().isoformat()}] Persisting {ocr_result.page_count} page(s)."
    db.commit()

    # Remove any existing pages from previous attempts
    db.query(DocumentPage).filter(DocumentPage.document_id == document_id).delete()

    for page in ocr_result.pages:
        db.add(DocumentPage(
            id=str(uuid.uuid4()),
            document_id=document_id,
            page_number=page.page_number,
            text_content=page.text,
        ))
    doc.raw_text = ocr_result.full_text[:50000]  # Store first 50k chars
    db.commit()

    # ---------------------------------------------------------------
    # Step 3: AI Extraction
    # ---------------------------------------------------------------
    job.current_step = "AI_EXTRACTION"
    job.log_messages += f"\n[{utc_now_naive().isoformat()}] AI extraction started."
    db.commit()

    try:
        provider = get_extraction_provider()
        payload: ClinicalExtractionPayload = provider.extract(
            pages=ocr_result.pages,
            document_id=document_id,
            document_type=doc.document_type or "LABORATORY_REPORT",
            patient_context=None,
        )
        job.log_messages += (
            f"\n[{utc_now_naive().isoformat()}] "
            f"AI extraction complete via '{provider.provider_name}'. "
            f"Labs: {len(payload.lab_results)}, "
            f"Conditions: {len(payload.conditions)}, "
            f"Observations: {len(payload.observations)}."
        )
    except Exception as exc:
        return _fail_document(db, doc, job, f"AI extraction failed: {exc}")

    # ---------------------------------------------------------------
    # Step 4: Business Validation
    # ---------------------------------------------------------------
    job.current_step = "BUSINESS_VALIDATION"
    job.log_messages += f"\n[{utc_now_naive().isoformat()}] Business validation started."
    db.commit()

    try:
        validation_result = business_validator.validate(
            payload=payload,
            full_document_text=ocr_result.full_text,
        )
    except BusinessValidationError as exc:
        return _fail_document(db, doc, job, f"Business validation fatal error: {exc}")

    if not validation_result.is_valid:
        error_summary = "; ".join(validation_result.errors[:5])
        # Non-fatal errors → REVIEW_REQUIRED
        doc.processing_status = "REVIEW_REQUIRED"
        doc.processing_error = f"Validation errors: {error_summary}"
        job.status = "REVIEW_REQUIRED"
        job.current_step = "VALIDATION_ERRORS"
        job.completed_at = utc_now_naive()
        job.log_messages += f"\n[{utc_now_naive().isoformat()}] Validation errors: {error_summary}"
        db.commit()
        return ProcessingResult(
            document_id=document_id,
            success=False,
            status="REVIEW_REQUIRED",
            error=error_summary,
            warnings=validation_result.warnings,
        )

    validated_payload = validation_result.corrected_payload

    # ---------------------------------------------------------------
    # Step 5: Persist extracted data
    # ---------------------------------------------------------------
    job.current_step = "PERSISTING_EXTRACTIONS"
    job.log_messages += f"\n[{utc_now_naive().isoformat()}] Persisting extractions to database."
    db.commit()

    labs_created = 0
    entities_created = 0
    observations_created = 0
    review_items_created = 0

    try:
        # Remove any extractions from previous runs on this document
        db.query(LabResult).filter(LabResult.document_id == document_id).delete()
        db.query(Observation).filter(Observation.document_id == document_id).delete()
        db.query(ExtractedEntity).filter(ExtractedEntity.document_id == document_id).delete()
        db.flush()

        # 5a — LabResults + ReferenceRanges
        for i, lab in enumerate(validated_payload.lab_results):
            ref_low, ref_high = None, None
            if lab.reference_range_text:
                ref_low, ref_high = ReferenceRangeService.parse_numeric_range(lab.reference_range_text)

            status_str = lab.status.value if hasattr(lab.status, "value") else str(lab.status)

            lab_record = LabResult(
                id=str(uuid.uuid4()),
                patient_id=doc.patient_id,
                document_id=document_id,
                test_name=lab.test_name,
                value=lab.value,
                value_text=lab.value_text,
                unit=lab.unit,
                raw_reference_range=lab.reference_range_text,
                reference_low=ref_low,
                reference_high=ref_high,
                status=status_str,
                source_evidence=lab.source_evidence,
                page_number=lab.page_number or 1,
                confidence=lab.confidence,
                confidence_level="HIGH" if lab.confidence >= 0.85 else ("MEDIUM" if lab.confidence >= 0.70 else "LOW"),
                provenance=Provenance.AI_EXTRACTED.value,
                original_ai_value=lab.value_text,
                original_ai_unit=lab.unit,
                original_ai_range=lab.reference_range_text,
                report_date=lab.report_date or validated_payload.report_date or doc.report_date,
            )
            db.add(lab_record)
            db.flush()

            # Persist ReferenceRange record
            db.add(ReferenceRange(
                id=str(uuid.uuid4()),
                lab_result_id=lab_record.id,
                raw_text=lab.reference_range_text,
                low_value=ref_low,
                high_value=ref_high,
                unit=lab.unit,
                is_assessable=(lab.reference_range_text is not None and (ref_low is not None or ref_high is not None)),
                source_notes=(
                    f"AI-extracted via {validated_payload.provider_name}. "
                    f"Grounding validated. Evidence: {(lab.source_evidence or '')[:200]}"
                ),
            ))
            labs_created += 1

            # Create ReviewItem for low-confidence or UNKNOWN status labs
            if i in validation_result.lab_results_for_review:
                db.add(ReviewItem(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    patient_id=doc.patient_id,
                    target_type="LAB_RESULT",
                    target_id=lab_record.id,
                    field_name="lab_result",
                    current_value=f"{lab.test_name}: {lab.value_text} {lab.unit or ''}",
                    reason=(
                        f"Low extraction confidence ({lab.confidence:.0%}). "
                        f"Please verify against source document."
                    ),
                    priority="MEDIUM",
                    status="PENDING",
                ))
                review_items_created += 1

        # 5b — Observations
        for obs in validated_payload.observations:
            db.add(Observation(
                id=str(uuid.uuid4()),
                patient_id=doc.patient_id,
                document_id=document_id,
                category=obs.category,
                content=obs.content,
                source_evidence=obs.source_evidence,
                confidence=obs.confidence,
                provenance=Provenance.AI_EXTRACTED.value,
            ))
            observations_created += 1

        # 5c — Extracted entities (symptoms, conditions, medications, allergies)
        for symptom in validated_payload.symptoms:
            db.add(ExtractedEntity(
                id=str(uuid.uuid4()),
                document_id=document_id,
                patient_id=doc.patient_id,
                entity_type="SYMPTOM",
                name=symptom.symptom,
                source_evidence=symptom.source_evidence,
                page_number=symptom.page_number or 1,
                confidence=symptom.confidence,
                provenance=Provenance.AI_EXTRACTED.value,
            ))
            entities_created += 1

        for condition in validated_payload.conditions:
            db.add(ExtractedEntity(
                id=str(uuid.uuid4()),
                document_id=document_id,
                patient_id=doc.patient_id,
                entity_type="CONDITION",
                name=condition.condition_name,
                source_evidence=condition.source_evidence,
                page_number=condition.page_number or 1,
                confidence=condition.confidence,
                provenance=Provenance.AI_EXTRACTED.value,
            ))
            entities_created += 1

        for med in validated_payload.medications:
            db.add(ExtractedEntity(
                id=str(uuid.uuid4()),
                document_id=document_id,
                patient_id=doc.patient_id,
                entity_type="MEDICATION",
                name=med.medication_name,
                value=med.dosage,
                source_evidence=med.source_evidence,
                page_number=med.page_number or 1,
                confidence=med.confidence,
                provenance=Provenance.AI_EXTRACTED.value,
            ))
            entities_created += 1

        for allergy in validated_payload.allergies:
            db.add(ExtractedEntity(
                id=str(uuid.uuid4()),
                document_id=document_id,
                patient_id=doc.patient_id,
                entity_type="ALLERGY",
                name=allergy.allergen,
                value=allergy.reaction,
                source_evidence=allergy.source_evidence,
                page_number=allergy.page_number or 1,
                confidence=allergy.confidence,
                provenance=Provenance.AI_EXTRACTED.value,
            ))
            entities_created += 1

        # 5d — Update document record
        doc.processing_status = "COMPLETED"
        if validated_payload.report_date:
            doc.report_date = validated_payload.report_date

        # 5e — Update job
        job.status = "COMPLETED"
        job.current_step = "DONE"
        job.completed_at = utc_now_naive()
        job.log_messages += (
            f"\n[{utc_now_naive().isoformat()}] COMPLETED. "
            f"Labs: {labs_created}, Observations: {observations_created}, "
            f"Entities: {entities_created}, Review Items: {review_items_created}."
        )
        if validation_result.warnings:
            job.log_messages += f"\nWarnings: {'; '.join(validation_result.warnings[:10])}"

        db.commit()

        # 5e.1 — Run automated clinical conflict detection across patient data
        try:
            from app.services.conflict_detector import ConflictDetector
            detected_conflicts = ConflictDetector.detect_all_conflicts(db, doc.patient_id)
            if detected_conflicts:
                job.log_messages += f"\n[{utc_now_naive().isoformat()}] Conflict detector identified {len(detected_conflicts)} clinical inconsistency/ies."
                db.commit()
        except Exception as c_err:
            logger.warning("Automated conflict detection non-fatal warning: %s", c_err)

        # 5f — Audit log
        try:
            AuditService.log_action(
                db=db,
                action="DOCUMENT_PROCESSED",
                entity_type="DOCUMENT",
                entity_id=document_id,
                details={
                    "provider": validated_payload.provider_name,
                    "labs": labs_created,
                    "observations": observations_created,
                    "entities": entities_created,
                },
            )
        except Exception:
            pass  # Audit log failure should not block the main pipeline

        logger.info(
            "Document %s processed successfully: %d labs, %d entities.",
            document_id, labs_created, entities_created,
        )

        return ProcessingResult(
            document_id=document_id,
            success=True,
            status="COMPLETED",
            lab_results_created=labs_created,
            entities_created=entities_created,
            observations_created=observations_created,
            review_items_created=review_items_created,
            warnings=validation_result.warnings,
        )

    except Exception as exc:
        db.rollback()
        logger.exception("Database persistence failed for document %s: %s", document_id, exc)
        return _fail_document(db, doc, job, f"Database persistence failed: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fail_document(
    db: Session,
    doc: Document,
    job: DocumentProcessingJob,
    error_message: str,
) -> ProcessingResult:
    """Mark document and job as FAILED, commit, and return failure result."""
    try:
        doc.processing_status = "FAILED"
        doc.processing_error = error_message[:1000]
        job.status = "FAILED"
        job.current_step = "FAILED"
        job.completed_at = utc_now_naive()
        job.log_messages = (job.log_messages or "") + f"\n[{utc_now_naive().isoformat()}] FAILED: {error_message}"
        db.commit()
    except Exception:
        db.rollback()

    logger.error("Document %s processing FAILED: %s", doc.id, error_message)
    return ProcessingResult(
        document_id=doc.id,
        success=False,
        status="FAILED",
        error=error_message,
    )
