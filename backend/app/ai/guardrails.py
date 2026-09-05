import re
from typing import Tuple, List, Optional
from app.schemas.extraction import ClinicalExtractionSchema

DIAGNOSTIC_PATTERNS = [
    r'\b(?:patient\s+has|you\s+have)\s+[a-zA-Z\s]+',
    r'\bdiagnos(?:ed|is)\s+(?:with|of)\b',
    r'\bsuffering\s+from\b',
    r'\bindicates\s+(?:that\s+you\s+have|presence\s+of)\s+disease\b',
    r'\bconfirms\s+diagnosis\b'
]

PRESCRIPTIVE_PATTERNS = [
    r'\b(?:prescribe|prescription)\b',
    r'\b(?:take|start|begin)\s+[0-9]+\s*(?:mg|g|ml|tablets?)\b',
    r'\b(?:increase|decrease|discontinue|stop)\s+(?:dosage|dose|medication)\b',
    r'\brecommended\s+treatment\s+is\b',
    r'\byou\s+should\s+take\b'
]

CLINICAL_DISCLAIMER = (
    "MedLens is an information organization and understanding tool. "
    "It does not provide medical diagnosis or treatment recommendations. "
    "Always consult a qualified healthcare professional for medical decisions."
)

class ResponsibleAIGuardrails:
    @staticmethod
    def validate_summary_safety(summary_text: str) -> Tuple[bool, str, List[str]]:
        """
        Enforces Section 15 & Critical Case 10:
        Verifies that summary contains zero diagnostic or prescriptive statements.
        Returns: (is_safe: bool, sanitized_or_original_text: str, violations: List[str])
        """
        violations = []

        # Check for diagnostic claims
        for pattern in DIAGNOSTIC_PATTERNS:
            matches = re.findall(pattern, summary_text, re.IGNORECASE)
            for m in matches:
                violations.append(f"Diagnostic claim detected: '{m}'")

        # Check for prescriptive claims
        for pattern in PRESCRIPTIVE_PATTERNS:
            matches = re.findall(pattern, summary_text, re.IGNORECASE)
            for m in matches:
                violations.append(f"Prescriptive recommendation detected: '{m}'")

        if violations:
            # Fallback safe summary grounded purely in structured record presence
            safe_text = (
                "The report contains extracted laboratory values and clinical observations. "
                "Detailed parameters are available in the structured record above. "
                f"\n\nNote: Automated generation suppressed statements flagged for clinical safety: {', '.join(violations)}."
            )
            return False, safe_text, violations

        return True, summary_text, []

    @staticmethod
    def verify_reference_ranges_against_source(
        extraction: ClinicalExtractionSchema,
        document_text: str
    ) -> ClinicalExtractionSchema:
        """
        Enforces Section 8 & Critical Case 9:
        Checks if extracted reference ranges actually exist in the source text.
        If an AI invented a range not present in the document, it is rejected to UNKNOWN.
        """
        clean_doc_text = document_text.lower()

        for lab in extraction.laboratoryResults:
            if lab.referenceRange and lab.referenceRange.raw:
                raw_range = lab.referenceRange.raw.strip().lower()
                # If the raw range substring does not appear in the source text
                if raw_range not in clean_doc_text:
                    # Strip invented range
                    lab.referenceRange.raw = None
                    lab.referenceRange.low = None
                    lab.referenceRange.high = None
                    lab.status = "UNKNOWN"
                    lab.confidence = round(max(0.1, lab.confidence - 0.3), 2)
                    if lab.sourceEvidence:
                        lab.sourceEvidence += " [Safety Flag: Range unverified in source document, reset to UNKNOWN]"
                    else:
                        lab.sourceEvidence = "[Safety Flag: Range unverified in source document, reset to UNKNOWN]"

        return extraction
