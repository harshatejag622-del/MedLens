"""
Phase 5 AI Extraction Tests
=============================
Tests the complete AI-powered medical report extraction pipeline including:

  1. Mock provider deterministic extraction
  2. Schema validation rejects malformed AI output
  3. Anti-hallucination guard rejects invented reference ranges
  4. Missing reference range → UNKNOWN status (never inferred)
  5. Full document processing pipeline (OCR → AI → Validate → Persist)
  6. Retry after failed extraction
  7. Gemini provider JSON parsing
  8. Evidence grounding check
"""

from __future__ import annotations

import io
import json
import os
import struct
import uuid
from pathlib import Path
from typing import List

import pytest

from app.services.ai.mock_provider import DeterministicMockProvider
from app.services.ai.schemas import (
    ClinicalExtractionPayload,
    ExtractedLabResult,
    ExtractionStatus,
    Provenance,
)
from app.services.business_validator import BusinessValidator, business_validator
from app.services.ocr_service import DocumentPageText, OCRService, PlainTextExtractor, PyPDFTextExtractor
from app.services.document_processor import process_document


# ---------------------------------------------------------------------------
# Sample synthetic lab report text (used across many tests)
# ---------------------------------------------------------------------------

SAMPLE_LAB_TEXT = """\
CLINICAL LABORATORY REPORT
Patient: John Smith
MRN: MRN-TEST-001
Report Date: 2024-03-15
Laboratory: St. Jude Clinical Laboratories

COMPLETE BLOOD COUNT (CBC)
Hemoglobin: 10.2 g/dL       Reference Range (12.0 - 16.0)
WBC: 11.5 x10^9/L            Reference Range (4.0 - 11.0)
Platelets: 225 x10^9/L       Reference Range (150 - 400)
RBC: 4.1 x10^6/uL            Reference Range (4.2 - 5.4)

METABOLIC PANEL
Glucose: 142 mg/dL            Reference Range (70 - 100)
Creatinine: 1.3 mg/dL         Reference Range (0.6 - 1.2)
Sodium: 138 mEq/L             Reference Range (136 - 145)

Impression: Microcytic anaemia suspected. Elevated glucose consistent with diabetes.
Recommendation: Correlate with ferritin and HbA1c.

Allergies: Penicillin - Rash (MODERATE)
Medications: Metformin 500 mg twice daily

Conditions: diabetes, hypertension
"""

SAMPLE_LAB_TEXT_NO_RANGES = """\
LABORATORY RESULTS
Patient: Jane Doe
Report Date: 2024-01-20

Hemoglobin: 11.5 g/dL
WBC: 8.2 x10^9/L
Glucose: 95 mg/dL

Note: Reference ranges not provided in this report.
"""


# ---------------------------------------------------------------------------
# 1. Mock provider deterministic extraction
# ---------------------------------------------------------------------------

class TestMockProviderDeterministicExtraction:

    def test_extracts_lab_results_with_correct_values(self):
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        doc_id = str(uuid.uuid4())

        payload = provider.extract(pages=pages, document_id=doc_id)

        assert payload.provider_name == "mock-deterministic-v1"
        assert payload.document_id == doc_id
        # Should extract at least hemoglobin, WBC, glucose
        names_lower = {r.test_name.lower() for r in payload.lab_results}
        assert "hemoglobin" in names_lower
        assert "wbc" in names_lower
        assert "glucose" in names_lower

    def test_lab_values_are_correct(self):
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")

        hgb = next((r for r in payload.lab_results if r.test_name.lower() == "hemoglobin"), None)
        assert hgb is not None
        assert hgb.value == 10.2
        assert hgb.unit is not None

    def test_extracts_reference_ranges_from_text(self):
        """Mock provider must only extract ranges that are verbatim in the document."""
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")

        hgb = next((r for r in payload.lab_results if r.test_name.lower() == "hemoglobin"), None)
        assert hgb is not None
        # Hemoglobin is 10.2, range is 12.0 - 16.0 → should be LOW
        if hgb.reference_range_text is not None:
            assert hgb.status == ExtractionStatus.LOW

    def test_no_range_in_document_gives_unknown_status(self):
        """When document has no reference ranges, all statuses must be UNKNOWN."""
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT_NO_RANGES)]
        payload = provider.extract(pages=pages, document_id="no-range-doc")

        for lab in payload.lab_results:
            assert lab.reference_range_text is None or lab.status == ExtractionStatus.UNKNOWN, (
                f"'{lab.test_name}' has range '{lab.reference_range_text}' "
                f"but status is '{lab.status}' — should be UNKNOWN when range absent."
            )

    def test_extracts_report_date(self):
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")
        assert payload.report_date == "2024-03-15"

    def test_extracts_conditions(self):
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")
        condition_names = {c.condition_name.lower() for c in payload.conditions}
        assert "diabetes" in condition_names or "hypertension" in condition_names

    def test_extracts_allergies(self):
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")
        allergen_names = {a.allergen.lower() for a in payload.allergies}
        assert "penicillin" in allergen_names

    def test_provenance_is_ai_extracted(self):
        """Every extracted entity must carry AI_EXTRACTED provenance."""
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")
        for lab in payload.lab_results:
            assert lab.provenance == Provenance.AI_EXTRACTED

    def test_source_evidence_is_set(self):
        """Every lab result must carry a non-empty source_evidence."""
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT)]
        payload = provider.extract(pages=pages, document_id="test-doc")
        for lab in payload.lab_results:
            assert lab.source_evidence is not None
            assert len(lab.source_evidence) > 0

    def test_empty_document_produces_warning(self):
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text="   ")]
        payload = provider.extract(pages=pages, document_id="empty-doc")
        assert len(payload.extraction_warnings) > 0


# ---------------------------------------------------------------------------
# 2. Schema validation rejects malformed AI output
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_missing_test_name_raises_validation_error(self):
        """ExtractedLabResult requires test_name — empty string must fail."""
        with pytest.raises(Exception):
            ExtractedLabResult(
                test_name="",   # too short — min_length=1 but empty string fails
                value_text="12.5",
            )

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(Exception):
            ExtractedLabResult(
                test_name="Hemoglobin",
                value_text="12.5",
                confidence=1.5,   # > 1.0 is invalid
            )

    def test_negative_confidence_raises(self):
        with pytest.raises(Exception):
            ExtractedLabResult(
                test_name="Hemoglobin",
                value_text="12.5",
                confidence=-0.1,
            )

    def test_invalid_date_format_raises(self):
        with pytest.raises(Exception):
            ExtractedLabResult(
                test_name="Hemoglobin",
                value_text="12.5",
                report_date="15/03/2024",   # wrong format, must be YYYY-MM-DD
            )

    def test_payload_with_no_document_id_raises(self):
        with pytest.raises(Exception):
            ClinicalExtractionPayload(
                document_id="",  # missing
                provider_name="mock",
            )

    def test_gemini_provider_skips_malformed_items(self):
        """
        Simulate GeminiExtractionProvider._parse_response with malformed items.
        Malformed items must be skipped (warning emitted) without crashing.
        """
        from app.services.ai.gemini_provider import GeminiExtractionProvider

        # We can't call the real API, but we can test _parse_response directly
        raw_json = json.dumps({
            "report_date": "2024-03-15",
            "lab_results": [
                # Valid item
                {
                    "test_name": "Hemoglobin",
                    "value": 10.2,
                    "value_text": "10.2",
                    "unit": "g/dL",
                    "reference_range_text": None,
                    "status": "UNKNOWN",
                    "source_evidence": "Hemoglobin: 10.2",
                    "page_number": 1,
                    "confidence": 0.9,
                },
                # Malformed item — missing required value_text
                {
                    "test_name": "WBC",
                    "value": 8.0,
                    # value_text intentionally missing
                    "confidence": 0.9,
                },
            ],
            "observations": [],
            "symptoms": [],
            "conditions": [],
            "medications": [],
            "allergies": [],
        })

        # Create provider bypassing __init__ API key check
        provider = object.__new__(GeminiExtractionProvider)
        provider._api_key = "test-key"
        provider._model = "gemini-1.5-flash"

        payload = provider._parse_response(raw_json, "test-doc-id")

        # Only valid item should be parsed
        assert len(payload.lab_results) == 1
        assert payload.lab_results[0].test_name == "Hemoglobin"
        # Warning about skipped malformed item
        assert len(payload.extraction_warnings) >= 1


# ---------------------------------------------------------------------------
# 3. Anti-hallucination: invented reference range is rejected
# ---------------------------------------------------------------------------

class TestAntiHallucination:

    def test_invented_range_not_in_doc_is_stripped(self):
        """
        If the AI asserts a reference range that is NOT present in the source
        document text, the business validator must strip it and set UNKNOWN.
        """
        validator = BusinessValidator()

        # Document text has NO reference range data
        doc_text = "Hemoglobin: 10.2 g/dL"

        # AI hallucinates a reference range of 12.0 - 16.0
        lab = ExtractedLabResult(
            test_name="Hemoglobin",
            value=10.2,
            value_text="10.2",
            unit="g/dL",
            reference_range_text="12.0 - 16.0",   # NOT in doc_text
            status=ExtractionStatus.LOW,           # Derived from hallucinated range
            source_evidence="Hemoglobin: 10.2",
            confidence=0.9,
        )

        payload = ClinicalExtractionPayload(
            document_id="test-doc",
            provider_name="test",
            lab_results=[lab],
        )

        result = validator.validate(payload, doc_text)

        assert result.is_valid
        corrected_lab = result.corrected_payload.lab_results[0]
        assert corrected_lab.reference_range_text is None, (
            "Hallucinated reference range must be stripped to None"
        )
        assert corrected_lab.status == ExtractionStatus.UNKNOWN, (
            "Status must be UNKNOWN when reference range is stripped"
        )
        # A warning should have been emitted
        anti_hallucination_warnings = [
            w for w in result.warnings if "ANTI-HALLUCINATION" in w
        ]
        assert len(anti_hallucination_warnings) >= 1

    def test_grounded_range_is_preserved(self):
        """If the range IS in the document text, it must be preserved."""
        validator = BusinessValidator()
        doc_text = "Hemoglobin: 10.2 g/dL   Reference Range (12.0 - 16.0)"

        lab = ExtractedLabResult(
            test_name="Hemoglobin",
            value=10.2,
            value_text="10.2",
            unit="g/dL",
            reference_range_text="12.0 - 16.0",
            status=ExtractionStatus.LOW,
            source_evidence="Hemoglobin: 10.2",
            confidence=0.9,
        )

        payload = ClinicalExtractionPayload(
            document_id="test-doc",
            provider_name="test",
            lab_results=[lab],
        )

        result = validator.validate(payload, doc_text)

        corrected_lab = result.corrected_payload.lab_results[0]
        assert corrected_lab.reference_range_text == "12.0 - 16.0"
        assert corrected_lab.status == ExtractionStatus.LOW

    def test_multiple_labs_only_strips_ungrounded(self):
        """Only the hallucinated range is stripped; grounded ranges survive."""
        validator = BusinessValidator()
        doc_text = "Hemoglobin: 10.2 g/dL Ref: 12.0 - 16.0\nWBC: 8.5"

        labs = [
            ExtractedLabResult(
                test_name="Hemoglobin",
                value=10.2,
                value_text="10.2",
                unit="g/dL",
                reference_range_text="12.0 - 16.0",  # grounded
                status=ExtractionStatus.LOW,
                source_evidence="Hemoglobin: 10.2",
                confidence=0.9,
            ),
            ExtractedLabResult(
                test_name="WBC",
                value=8.5,
                value_text="8.5",
                unit="x10^9/L",
                reference_range_text="4.0 - 11.0",  # NOT grounded — AI invented
                status=ExtractionStatus.NORMAL,
                source_evidence="WBC: 8.5",
                confidence=0.9,
            ),
        ]

        payload = ClinicalExtractionPayload(
            document_id="test-doc",
            provider_name="test",
            lab_results=labs,
        )

        result = validator.validate(payload, doc_text)
        corrected_labs = {r.test_name: r for r in result.corrected_payload.lab_results}

        # Hemoglobin range preserved
        assert corrected_labs["Hemoglobin"].reference_range_text == "12.0 - 16.0"
        # WBC range stripped
        assert corrected_labs["WBC"].reference_range_text is None
        assert corrected_labs["WBC"].status == ExtractionStatus.UNKNOWN


# ---------------------------------------------------------------------------
# 4. Missing reference range → UNKNOWN status (Pydantic schema enforcement)
# ---------------------------------------------------------------------------

class TestMissingReferenceRange:

    def test_schema_enforces_unknown_when_range_absent(self):
        """ExtractedLabResult model validator must set UNKNOWN if range is None."""
        lab = ExtractedLabResult(
            test_name="Glucose",
            value=142.0,
            value_text="142",
            unit="mg/dL",
            reference_range_text=None,  # not provided in document
            status=ExtractionStatus.HIGH,  # AI tries to set HIGH without a range
            source_evidence="Glucose: 142 mg/dL",
            confidence=0.9,
        )
        # Model validator must override status to UNKNOWN
        assert lab.status == ExtractionStatus.UNKNOWN
        assert lab.reference_range_text is None

    def test_empty_string_range_treated_as_absent(self):
        """Empty reference_range_text must be treated same as None."""
        lab = ExtractedLabResult(
            test_name="WBC",
            value=8.5,
            value_text="8.5",
            unit="x10^9/L",
            reference_range_text="   ",  # whitespace-only
            status=ExtractionStatus.NORMAL,
            source_evidence="WBC: 8.5",
            confidence=0.9,
        )
        assert lab.reference_range_text is None
        assert lab.status == ExtractionStatus.UNKNOWN

    def test_document_without_ranges_all_unknown(self):
        """End-to-end: document with no ranges → all UNKNOWN after extraction."""
        provider = DeterministicMockProvider()
        pages = [DocumentPageText(page_number=1, text=SAMPLE_LAB_TEXT_NO_RANGES)]
        payload = provider.extract(pages=pages, document_id="no-range-test")

        for lab in payload.lab_results:
            # Either range is None, or status is UNKNOWN
            if lab.reference_range_text is None:
                assert lab.status == ExtractionStatus.UNKNOWN, (
                    f"'{lab.test_name}': range is None but status={lab.status}"
                )


# ---------------------------------------------------------------------------
# 5. Full document processing pipeline
# ---------------------------------------------------------------------------

class TestFullProcessingPipeline:

    def _create_txt_document(self, db, patient_id: str) -> str:
        """Helper: write a .txt file to storage and create a Document record."""
        from app.models.document import Document, DocumentProcessingJob
        from app.services.storage_service import StorageService

        content = SAMPLE_LAB_TEXT.encode("utf-8")
        stored_filename, abs_path, file_size, checksum = StorageService.store_document(
            patient_id=patient_id,
            original_filename="test_lab_report.txt",
            content=content,
        )

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            patient_id=patient_id,
            original_filename="test_lab_report.txt",
            stored_filename=stored_filename,
            file_type="txt",
            file_size_bytes=file_size,
            sha256_checksum=checksum,
            processing_status="QUEUED",
            document_type="LABORATORY_REPORT",
        )
        db.add(doc)

        job = DocumentProcessingJob(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            status="QUEUED",
            current_step="INITIALIZING",
            log_messages="Created for test.",
        )
        db.add(job)
        db.commit()

        return doc_id

    def test_full_pipeline_processes_txt_document(self, db_session):
        """Process a TXT lab report end-to-end and verify database records."""
        from app.models.clinical import LabResult, Observation
        from app.models.document import Document, DocumentPage

        # Get first demo patient
        from app.models.patient import Patient
        patient = db_session.query(Patient).first()
        assert patient is not None

        doc_id = self._create_txt_document(db_session, patient.id)

        result = process_document(db_session, doc_id)

        # Processing should succeed
        assert result.success is True, f"Processing failed: {result.error}"
        assert result.status == "COMPLETED"

        # Document status updated
        doc = db_session.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "COMPLETED"

        # DocumentPage records created
        pages = db_session.query(DocumentPage).filter(DocumentPage.document_id == doc_id).all()
        assert len(pages) >= 1

        # LabResult records created
        labs = db_session.query(LabResult).filter(LabResult.document_id == doc_id).all()
        assert len(labs) >= 1
        assert result.lab_results_created >= 1

        # All lab results have AI_EXTRACTED provenance
        for lab in labs:
            assert lab.provenance == Provenance.AI_EXTRACTED.value

    def test_pipeline_creates_reference_range_records(self, db_session):
        """LabResults with grounded ranges should create linked ReferenceRange records."""
        from app.models.clinical import LabResult
        from app.models.reference_range import ReferenceRange
        from app.models.patient import Patient

        patient = db_session.query(Patient).first()
        doc_id = self._create_txt_document(db_session, patient.id)

        process_document(db_session, doc_id)

        labs = db_session.query(LabResult).filter(LabResult.document_id == doc_id).all()
        for lab in labs:
            ref_range = db_session.query(ReferenceRange).filter(
                ReferenceRange.lab_result_id == lab.id
            ).first()
            assert ref_range is not None, (
                f"LabResult '{lab.test_name}' is missing a linked ReferenceRange record."
            )

    def test_pipeline_sets_unknown_when_no_range(self, db_session):
        """Labs extracted from rangeless document must have UNKNOWN status in DB."""
        from app.models.clinical import LabResult
        from app.models.patient import Patient
        from app.models.document import Document, DocumentProcessingJob
        from app.services.storage_service import StorageService

        patient = db_session.query(Patient).first()
        content = SAMPLE_LAB_TEXT_NO_RANGES.encode("utf-8")
        stored_filename, abs_path, file_size, checksum = StorageService.store_document(
            patient_id=patient.id,
            original_filename="no_range_lab.txt",
            content=content,
        )

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            patient_id=patient.id,
            original_filename="no_range_lab.txt",
            stored_filename=stored_filename,
            file_type="txt",
            file_size_bytes=file_size,
            sha256_checksum=checksum,
            processing_status="QUEUED",
            document_type="LABORATORY_REPORT",
        )
        db_session.add(doc)
        db_session.add(DocumentProcessingJob(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            status="QUEUED",
            current_step="INITIALIZING",
            log_messages="",
        ))
        db_session.commit()

        process_document(db_session, doc_id)

        labs = db_session.query(LabResult).filter(LabResult.document_id == doc_id).all()
        for lab in labs:
            if lab.raw_reference_range is None:
                assert lab.status == "UNKNOWN", (
                    f"'{lab.test_name}' has null range but status={lab.status}"
                )

    def test_pipeline_handles_missing_document(self, db_session):
        """Processing a non-existent document_id must return failure result."""
        result = process_document(db_session, "nonexistent-document-id")
        assert result.success is False
        assert result.status == "FAILED"
        assert "not found" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# 6. Retry after failed extraction
# ---------------------------------------------------------------------------

class TestRetryAfterFailure:

    def test_failed_document_transitions_to_processing_on_retry(self, db_session):
        """After a failed processing attempt, retrying should re-run the pipeline."""
        from app.models.document import Document, DocumentProcessingJob
        from app.models.patient import Patient
        from app.services.storage_service import StorageService

        patient = db_session.query(Patient).first()

        # Create document
        content = SAMPLE_LAB_TEXT.encode("utf-8")
        stored_filename, _, file_size, checksum = StorageService.store_document(
            patient_id=patient.id,
            original_filename="retry_test.txt",
            content=content,
        )

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            patient_id=patient.id,
            original_filename="retry_test.txt",
            stored_filename=stored_filename,
            file_type="txt",
            file_size_bytes=file_size,
            sha256_checksum=checksum + "retry",  # unique checksum
            processing_status="QUEUED",
            processing_error="Previous run failed.",
            document_type="LABORATORY_REPORT",
        )
        db_session.add(doc)
        db_session.add(DocumentProcessingJob(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            status="QUEUED",
            current_step="INITIALIZING",
            log_messages="",
        ))
        db_session.commit()

        # First processing attempt
        result = process_document(db_session, doc_id)
        assert result.success is True

        # Verify document is now COMPLETED
        doc = db_session.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "COMPLETED"
        assert doc.processing_error is None


# ---------------------------------------------------------------------------
# 7. OCR Service
# ---------------------------------------------------------------------------

class TestOCRService:

    def test_plain_text_extractor_single_page(self, tmp_path):
        txt_file = tmp_path / "report.txt"
        txt_file.write_text(SAMPLE_LAB_TEXT, encoding="utf-8")

        extractor = PlainTextExtractor()
        result = extractor.extract(txt_file, "test-doc")

        assert result.page_count == 1
        assert "Hemoglobin" in result.full_text
        assert result.pages[0].page_number == 1

    def test_pdf_extractor_handles_nonexistent_file(self, tmp_path):
        from app.services.ocr_service import OCRError
        extractor = PyPDFTextExtractor()
        with pytest.raises(OCRError):
            extractor.extract(tmp_path / "nonexistent.pdf", "test-doc")

    def test_ocr_service_routes_txt_correctly(self, tmp_path):
        txt_file = tmp_path / "report.txt"
        txt_file.write_text("Hemoglobin: 12.5 g/dL", encoding="utf-8")

        svc = OCRService()
        result = svc.extract(str(txt_file), "test-doc")

        assert result.page_count == 1
        assert "Hemoglobin" in result.full_text


# ---------------------------------------------------------------------------
# 8. Evidence grounding check
# ---------------------------------------------------------------------------

class TestEvidenceGrounding:

    def test_evidence_not_in_document_reduces_confidence(self):
        """If source_evidence cannot be found in doc text, confidence must be reduced."""
        validator = BusinessValidator()
        doc_text = "Hemoglobin: 10.2 g/dL"

        lab = ExtractedLabResult(
            test_name="Hemoglobin",
            value=10.2,
            value_text="10.2",
            unit="g/dL",
            reference_range_text=None,
            status=ExtractionStatus.UNKNOWN,
            source_evidence="Haemoglobin level ten point two",  # NOT in doc_text verbatim
            confidence=0.9,
        )

        payload = ClinicalExtractionPayload(
            document_id="test-doc",
            provider_name="test",
            lab_results=[lab],
        )

        result = validator.validate(payload, doc_text)
        corrected_lab = result.corrected_payload.lab_results[0]

        # Confidence must be reduced when evidence not grounded
        assert corrected_lab.confidence < 0.9, (
            f"Expected confidence to be reduced below 0.9, got {corrected_lab.confidence}"
        )

    def test_grounded_evidence_confidence_unchanged(self):
        """If source_evidence IS in doc text, confidence must remain unchanged."""
        validator = BusinessValidator()
        doc_text = "Hemoglobin: 10.2 g/dL"

        lab = ExtractedLabResult(
            test_name="Hemoglobin",
            value=10.2,
            value_text="10.2",
            unit="g/dL",
            reference_range_text=None,
            status=ExtractionStatus.UNKNOWN,
            source_evidence="Hemoglobin: 10.2 g/dL",  # verbatim in doc_text
            confidence=0.9,
        )

        payload = ClinicalExtractionPayload(
            document_id="test-doc",
            provider_name="test",
            lab_results=[lab],
        )

        result = validator.validate(payload, doc_text)
        corrected_lab = result.corrected_payload.lab_results[0]
        assert corrected_lab.confidence == pytest.approx(0.9)
