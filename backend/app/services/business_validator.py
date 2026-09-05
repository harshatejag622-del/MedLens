from __future__ import annotations
"""
Clinical Business Validator
=============================
Two-stage validation pipeline that sits between the AI extraction output
and the database write:

  Stage 1 — Schema Gate:
    The Pydantic schemas already validate types and field constraints.
    This stage performs cross-field and clinical-rule validations.

  Stage 2 — Anti-Hallucination Guard (CRITICAL):
    Verifies that every asserted reference range is GROUNDED in the
    document source text. If a range cannot be located in the source text,
    it is nullified and status is forced to UNKNOWN.

    This prevents AI hallucinated reference ranges from being persisted
    to the database and influencing clinical decisions.

  Stage 3 — Confidence & Review Flagging:
    Entities with low confidence (< LOW_CONFIDENCE_THRESHOLD) are tagged
    for human review via ReviewItem records.

Validation is non-destructive: it corrects or strips unsafe data but does
not throw exceptions for correctable issues. Fatal structural failures
raise BusinessValidationError.
"""


import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.ai.schemas import (
    ClinicalExtractionPayload,
    ExtractedLabResult,
    ExtractionStatus,
)

# Minimum confidence below which an entity is flagged for human review
LOW_CONFIDENCE_THRESHOLD = 0.60

# Minimum length (chars) for a source_evidence to be considered valid
MIN_EVIDENCE_LENGTH = 3


@dataclass
class ValidationResult:
    """Result of business validation on an extraction payload."""
    is_valid: bool
    corrected_payload: ClinicalExtractionPayload
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Entity IDs/indices flagged for human review
    lab_results_for_review: List[int] = field(default_factory=list)  # indices into corrected_payload.lab_results
    entities_for_review: List[str] = field(default_factory=list)     # descriptive labels


class BusinessValidationError(Exception):
    """Raised when validation failure is fatal and the payload cannot be corrected."""
    pass


class BusinessValidator:
    """
    Validates and corrects ClinicalExtractionPayload before database persistence.
    """

    def validate(
        self,
        payload: ClinicalExtractionPayload,
        full_document_text: str,
    ) -> ValidationResult:
        """
        Run full validation pipeline.

        Args:
            payload: Output from the ClinicalExtractionProvider.
            full_document_text: Complete extracted text from the document (all pages).

        Returns:
            ValidationResult with corrected payload, errors, warnings, and review flags.

        Raises:
            BusinessValidationError: If the payload is too malformed to correct.
        """
        errors: List[str] = []
        warnings: List[str] = []
        review_indices: List[int] = []
        review_labels: List[str] = []

        # --- Stage 1: Cross-field clinical checks ---
        errors += self._stage1_cross_field(payload)

        # --- Stage 2: Anti-hallucination reference range guard ---
        corrected_labs, range_warnings, range_errors = self._stage2_antihallucination(
            payload.lab_results, full_document_text
        )
        warnings.extend(range_warnings)
        errors.extend(range_errors)

        # --- Stage 3: Confidence scoring & review flagging ---
        for i, lab in enumerate(corrected_labs):
            if lab.confidence < LOW_CONFIDENCE_THRESHOLD:
                review_indices.append(i)
                review_labels.append(
                    f"Low-confidence lab result: '{lab.test_name}' (confidence={lab.confidence:.2f})"
                )

        for symptom in payload.symptoms:
            if symptom.confidence < LOW_CONFIDENCE_THRESHOLD:
                review_labels.append(
                    f"Low-confidence symptom: '{symptom.symptom}' (confidence={symptom.confidence:.2f})"
                )

        for condition in payload.conditions:
            if condition.confidence < LOW_CONFIDENCE_THRESHOLD:
                review_labels.append(
                    f"Low-confidence condition: '{condition.condition_name}' (confidence={condition.confidence:.2f})"
                )

        # Stage 4: Evidence grounding check — source_evidence must appear in doc
        corrected_labs = self._stage4_evidence_grounding(
            corrected_labs, full_document_text, warnings
        )

        # Rebuild payload with corrections
        corrected = payload.model_copy(update={
            "lab_results": corrected_labs,
            "extraction_warnings": payload.extraction_warnings + warnings,
        })

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            corrected_payload=corrected,
            errors=errors,
            warnings=warnings,
            lab_results_for_review=review_indices,
            entities_for_review=review_labels,
        )

    # ------------------------------------------------------------------
    # Stage 1 — Cross-field checks
    # ------------------------------------------------------------------

    def _stage1_cross_field(self, payload: ClinicalExtractionPayload) -> List[str]:
        errors = []

        if not payload.document_id:
            errors.append("FATAL: Payload is missing document_id.")

        for i, lab in enumerate(payload.lab_results):
            if not lab.test_name or not lab.test_name.strip():
                errors.append(f"Lab result [{i}] has empty test_name.")

            if lab.value is not None:
                if lab.value < 0 and lab.unit not in {"-", "°C", "°F", "mV"}:
                    # Negative values are suspicious for most lab tests
                    errors.append(
                        f"Lab result [{i}] '{lab.test_name}' has suspicious negative value {lab.value}. "
                        "Check unit of measurement."
                    )

            if lab.reference_range_text and not lab.source_evidence:
                errors.append(
                    f"Lab result [{i}] '{lab.test_name}' asserts a reference range "
                    "but has no source_evidence. Cannot verify grounding."
                )

        return errors

    # ------------------------------------------------------------------
    # Stage 2 — Anti-hallucination reference range guard
    # ------------------------------------------------------------------

    def _stage2_antihallucination(
        self,
        lab_results: List[ExtractedLabResult],
        doc_text: str,
    ) -> tuple[List[ExtractedLabResult], List[str], List[str]]:
        """
        CRITICAL SAFETY CHECK:
        For every lab result that has a reference_range_text, verify that the
        numeric values in that range actually appear in proximity to each other
        in the document text.

        If a range CANNOT be verified, strip it and set status = UNKNOWN.
        """
        warnings: List[str] = []
        errors: List[str] = []
        corrected: List[ExtractedLabResult] = []

        for lab in lab_results:
            if lab.reference_range_text is None:
                # Correctly absent — no range claimed, status should be UNKNOWN
                if lab.status != ExtractionStatus.UNKNOWN:
                    warnings.append(
                        f"'{lab.test_name}': status was {lab.status} but reference_range_text is None. "
                        "Correcting status to UNKNOWN."
                    )
                    lab = lab.model_copy(update={"status": ExtractionStatus.UNKNOWN})
                corrected.append(lab)
                continue

            # Verify the range is grounded in the source text
            grounded = _is_range_grounded(lab.reference_range_text, doc_text)
            if not grounded:
                warnings.append(
                    f"ANTI-HALLUCINATION: '{lab.test_name}' asserts reference range "
                    f"'{lab.reference_range_text}' which cannot be located in document text. "
                    f"Range stripped, status set to UNKNOWN."
                )
                lab = lab.model_copy(update={
                    "reference_range_text": None,
                    "status": ExtractionStatus.UNKNOWN,
                })

            corrected.append(lab)

        return corrected, warnings, errors

    # ------------------------------------------------------------------
    # Stage 4 — Source evidence grounding
    # ------------------------------------------------------------------

    def _stage4_evidence_grounding(
        self,
        lab_results: List[ExtractedLabResult],
        doc_text: str,
        warnings: List[str],
    ) -> List[ExtractedLabResult]:
        corrected = []
        for lab in lab_results:
            if lab.source_evidence and len(lab.source_evidence) >= MIN_EVIDENCE_LENGTH:
                # Normalise whitespace for comparison
                norm_evidence = " ".join(lab.source_evidence.split()).lower()
                norm_doc = " ".join(doc_text.split()).lower()
                if norm_evidence not in norm_doc:
                    warnings.append(
                        f"'{lab.test_name}': source_evidence not found verbatim in document. "
                        f"Evidence: '{lab.source_evidence[:80]}'. Confidence reduced."
                    )
                    lab = lab.model_copy(update={
                        "confidence": round(lab.confidence * 0.7, 4)
                    })
            corrected.append(lab)
        return corrected


# ---------------------------------------------------------------------------
# Grounding helpers
# ---------------------------------------------------------------------------

def _is_range_grounded(range_text: str, doc_text: str) -> bool:
    """
    Check whether the numeric values in a reference range appear together
    in the document text within a reasonable proximity window.

    Strategy: extract the two numbers from range_text, then check that
    both numbers appear within 100 characters of each other somewhere in
    the document.
    """
    numbers = re.findall(r"\d+(?:\.\d+)?", range_text)
    if len(numbers) < 2:
        # Single-bound ranges — check that number appears in doc
        if len(numbers) == 1:
            return numbers[0] in doc_text
        return False

    low_str = numbers[0]
    high_str = numbers[1]

    # Search doc_text for both numbers appearing within 100 chars
    for m in re.finditer(re.escape(low_str), doc_text):
        window = doc_text[m.start(): m.start() + 150]
        if high_str in window:
            return True

    # Also check reverse order
    for m in re.finditer(re.escape(high_str), doc_text):
        window = doc_text[max(0, m.start() - 150): m.end()]
        if low_str in window:
            return True

    return False


# Module-level singleton
business_validator = BusinessValidator()
