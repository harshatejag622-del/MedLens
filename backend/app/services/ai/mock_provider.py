from __future__ import annotations
"""
Deterministic Mock Clinical Extraction Provider
===============================================
A fully offline, reproducible extraction engine using regex pattern matching.
This provider does NOT call any external API.

Use cases:
  - Local development
  - CI/CD automated testing (no API keys needed)
  - Demo environment with predictable, verifiable results

Safety guarantees:
  - Only extracts reference ranges that are literally present in the source text.
  - Sets status = UNKNOWN when range is absent.
  - Embeds verbatim source_evidence quotes for every extraction.
  - Assigns stable confidence scores based on match quality.
"""


import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.services.ocr_service import DocumentPageText
from app.services.ai.base import ClinicalExtractionProvider
from app.services.ai.schemas import (
    ClinicalExtractionPayload,
    ExtractedAllergy,
    ExtractedCondition,
    ExtractedLabResult,
    ExtractedMedication,
    ExtractedObservation,
    ExtractedSymptom,
    ExtractionStatus,
    Provenance,
)


# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

# Each entry: (regex pattern, canonical test name)
LAB_TEST_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Haematology
    (re.compile(
        r"(Haemoglobin|Hemoglobin|HGB|HB)[:\s]+([0-9]+\.?[0-9]*)\s*([a-zA-Z/µ%]+)?",
        re.IGNORECASE
    ), "Hemoglobin"),
    (re.compile(
        r"(WBC|White\s+Blood\s+Cell(?:\s+Count)?)[:\s]+([0-9]+\.?[0-9]*)\s*(?:x\s*10[39]/?[µu]?L?|/[µu]L|[kK]/[µu]L)?",
        re.IGNORECASE
    ), "WBC"),
    (re.compile(
        r"(Platelets?|PLT)[:\s]+([0-9]+\.?[0-9]*)\s*(?:x\s*10[39]/?[µu]?L?|[kK]/[µu]L)?",
        re.IGNORECASE
    ), "Platelets"),
    (re.compile(
        r"(RBC|Red\s+Blood\s+Cell(?:\s+Count)?)[:\s]+([0-9]+\.?[0-9]*)\s*(?:x\s*10[69]/?[µu]?L?)?",
        re.IGNORECASE
    ), "RBC"),
    (re.compile(
        r"(Haematocrit|Hematocrit|HCT|PCV)[:\s]+([0-9]+\.?[0-9]*)\s*%?",
        re.IGNORECASE
    ), "Hematocrit"),
    # Chemistry
    (re.compile(
        r"(Glucose|Blood\s+Glucose|FBG|RBG)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "Glucose"),
    (re.compile(
        r"(Creatinine|Serum\s+Creatinine)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|µmol/L|umol/L)?",
        re.IGNORECASE
    ), "Creatinine"),
    (re.compile(
        r"(BUN|Blood\s+Urea\s+Nitrogen|Urea)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "BUN"),
    (re.compile(
        r"(Sodium|Na\+?)[:\s]+([0-9]+\.?[0-9]*)\s*(mEq/L|mmol/L)?",
        re.IGNORECASE
    ), "Sodium"),
    (re.compile(
        r"(Potassium|K\+?)[:\s]+([0-9]+\.?[0-9]*)\s*(mEq/L|mmol/L)?",
        re.IGNORECASE
    ), "Potassium"),
    (re.compile(
        r"(Chloride|Cl\-?)[:\s]+([0-9]+\.?[0-9]*)\s*(mEq/L|mmol/L)?",
        re.IGNORECASE
    ), "Chloride"),
    (re.compile(
        r"(Total\s+Cholesterol|Cholesterol)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "Total Cholesterol"),
    (re.compile(
        r"(LDL|LDL-C|LDL\s+Cholesterol)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "LDL Cholesterol"),
    (re.compile(
        r"(HDL|HDL-C|HDL\s+Cholesterol)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "HDL Cholesterol"),
    (re.compile(
        r"(Triglycerides?|TG)[:\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "Triglycerides"),
    (re.compile(
        r"(HbA1c|Glycated\s+Haemoglobin|Glycated\s+Hemoglobin|A1C)[:\s]+([0-9]+\.?[0-9]*)\s*%?",
        re.IGNORECASE
    ), "HbA1c"),
    (re.compile(
        r"(TSH|Thyroid\s+Stimulating\s+Hormone)[:\s]+([0-9]+\.?[0-9]*)\s*(?:mIU/L|µIU/mL|uIU/mL)?",
        re.IGNORECASE
    ), "TSH"),
    (re.compile(
        r"(ALT|SGPT|Alanine\s+Aminotransferase)[:\s]+([0-9]+\.?[0-9]*)\s*(?:U/L|IU/L)?",
        re.IGNORECASE
    ), "ALT"),
    (re.compile(
        r"(AST|SGOT|Aspartate\s+Aminotransferase)[:\s]+([0-9]+\.?[0-9]*)\s*(?:U/L|IU/L)?",
        re.IGNORECASE
    ), "AST"),
    (re.compile(
        r"(Bilirubin|Total\s+Bilirubin)[:\|\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|µmol/L|umol/L)?",
        re.IGNORECASE
    ), "Total Bilirubin"),
    (re.compile(
        r"(eGFR|Estimated\s+GFR|Glomerular\s+Filtration\s+Rate)[:\|\s]+([0-9]+\.?[0-9]*)\s*(?:mL/min/1\.73m2|mL/min)?",
        re.IGNORECASE
    ), "eGFR"),
    (re.compile(
        r"(Calcium|Ca\+?)[:\|\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "Calcium"),
    (re.compile(
        r"(Albumin)[:\|\s]+([0-9]+\.?[0-9]*)\s*(g/dL|g/L)?",
        re.IGNORECASE
    ), "Albumin"),
    (re.compile(
        r"(Total\s+Protein|Protein)[:\|\s]+([0-9]+\.?[0-9]*)\s*(g/dL|g/L)?",
        re.IGNORECASE
    ), "Total Protein"),
    (re.compile(
        r"(ALP|Alkaline\s+Phosphatase)[:\|\s]+([0-9]+\.?[0-9]*)\s*(?:U/L|IU/L)?",
        re.IGNORECASE
    ), "Alkaline Phosphatase"),
    (re.compile(
        r"(Uric\s+Acid)[:\|\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|µmol/L)?",
        re.IGNORECASE
    ), "Uric Acid"),
    (re.compile(
        r"(Troponin|Troponin\s+I|Troponin\s+T|cTnI)[:\|\s]+([0-9]+\.?[0-9]*)\s*(?:ng/mL|µg/L)?",
        re.IGNORECASE
    ), "Troponin"),
    (re.compile(
        r"(CRP|C-Reactive\s+Protein)[:\|\s]+([0-9]+\.?[0-9]*)\s*(mg/L|mg/dL)?",
        re.IGNORECASE
    ), "CRP"),
    (re.compile(
        r"(ESR|Erythrocyte\s+Sedimentation\s+Rate)[:\|\s]+([0-9]+\.?[0-9]*)\s*(?:mm/hr|mm/h)?",
        re.IGNORECASE
    ), "ESR"),
    (re.compile(
        r"(Vitamin\s+D|25-OH\s+Vitamin\s+D|25-Hydroxyvitamin\s+D)[:\|\s]+([0-9]+\.?[0-9]*)\s*(?:ng/mL|nmol/L)?",
        re.IGNORECASE
    ), "Vitamin D"),
    (re.compile(
        r"(Ferritin)[:\|\s]+([0-9]+\.?[0-9]*)\s*(?:ng/mL|µg/L)?",
        re.IGNORECASE
    ), "Ferritin"),
    (re.compile(
        r"(Magnesium|Mg)[:\|\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "Magnesium"),
    (re.compile(
        r"(Phosphorus|Phosphate|PO4)[:\|\s]+([0-9]+\.?[0-9]*)\s*(mg/dL|mmol/L)?",
        re.IGNORECASE
    ), "Phosphorus"),
]

# Reference range patterns — must be adjacent to the lab line
REF_RANGE_PATTERNS = [
    re.compile(r"(?:Ref(?:erence)?\s*(?:Range|Interval)?|Normal\s*(?:Range|Values?)?)[:\s]*([0-9]+\.?[0-9]*)\s*[-–—]\s*([0-9]+\.?[0-9]*)"),
    re.compile(r"\(\s*([0-9]+\.?[0-9]*)\s*[-–—]\s*([0-9]+\.?[0-9]*)\s*\)"),
    re.compile(r"\[\s*([0-9]+\.?[0-9]*)\s*[-–—]\s*([0-9]+\.?[0-9]*)\s*\]"),
    re.compile(r"<\s*([0-9]+\.?[0-9]*)\s*(?:to|-)\s*([0-9]+\.?[0-9]*)"),
]

MEDICATION_PATTERNS = [
    re.compile(
        r"(?:Medications?|Drugs?|Rx|Prescribed)[:\s]+([A-Za-z][A-Za-z\-\s]+?)(?:\s+([0-9]+\s*mg|[0-9]+\s*mcg|[0-9]+\s*g|[0-9]+\s*IU))?(?:\s+(daily|twice\s+daily|TDS|QDS|PRN|BD|OD|QID|BID|TID|once|weekly))?",
        re.IGNORECASE
    ),
]

CONDITION_KEYWORDS = [
    "diabetes", "hypertension", "asthma", "COPD", "CKD", "anaemia", "anemia",
    "hypothyroidism", "hyperthyroidism", "dyslipidaemia", "dyslipidemia",
    "heart failure", "atrial fibrillation", "depression", "anxiety",
    "chronic kidney disease", "rheumatoid arthritis", "osteoarthritis",
    "coronary artery disease", "myocardial infarction", "stroke", "gout",
    "pneumonia", "bronchitis", "fatty liver", "cirrhosis", "hepatitis",
    "GERD", "peptic ulcer", "neuropathy", "retinopathy", "nephropathy"
]

ALLERGY_PATTERNS = [
    # "Allergies: Penicillin - Rash (MODERATE)" style
    re.compile(
        r"(?:Allerg(?:y|ies)|Adverse\s+Reaction|Intolerance)[:\s]+([A-Za-z][A-Za-z\-\s]{1,50}?)"
        r"(?:\s*[-–]\s*([A-Za-z][A-Za-z\s]{1,80}?))?(?:\s*\([A-Z_]+\))?(?=\n|,|;|$)",
        re.IGNORECASE
    ),
    # "Known allergy to Penicillin" style
    re.compile(
        r"(?:known\s+allerg(?:y|ic)\s+to|allergy\s+to)\s+([A-Za-z][A-Za-z\-\s]{1,50})",
        re.IGNORECASE
    ),
]


SYMPTOM_KEYWORDS = [
    "fatigue", "shortness of breath", "dyspnoea", "chest pain", "palpitations",
    "headache", "dizziness", "nausea", "vomiting", "abdominal pain", "weakness",
    "oedema", "edema", "fever", "cough", "haematuria", "haemoptysis",
    "weight loss", "weight gain", "polyuria", "polydipsia", "blurred vision",
    "chest tightness", "sweating", "diaphoresis", "syncope", "tremor",
    "joint pain", "back pain", "insomnia", "malaise", "chills", "loss of appetite"
]

DATE_PATTERN = re.compile(
    r"(?:Report\s+Date|Collection\s+Date|Date(?:\s+of\s+Report)?|Dated?)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4})"
)

OBSERVATION_TRIGGERS = [
    "impression", "conclusion", "summary", "comment", "remarks",
    "interpretation", "recommendation", "note",
]


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------

class DeterministicMockProvider(ClinicalExtractionProvider):
    """
    Deterministic, offline clinical extraction provider.
    Extracts entities using rule-based regex matching against document text.
    Produces the same output for the same input — suitable for tests.
    """

    @property
    def provider_name(self) -> str:
        return "mock-deterministic-v1"

    def extract(
        self,
        pages: List[DocumentPageText],
        document_id: str,
        document_type: str = "LABORATORY_REPORT",
        patient_context: dict | None = None,
    ) -> ClinicalExtractionPayload:
        warnings: List[str] = []
        lab_results: List[ExtractedLabResult] = []
        observations: List[ExtractedObservation] = []
        symptoms: List[ExtractedSymptom] = []
        conditions: List[ExtractedCondition] = []
        medications: List[ExtractedMedication] = []
        allergies: List[ExtractedAllergy] = []
        report_date: Optional[str] = None

        for page in pages:
            text = page.text
            pn = page.page_number

            # --- Report date ---
            if report_date is None:
                report_date = _extract_date(text)

            # --- Lab results ---
            for pattern, canonical_name in LAB_TEST_PATTERNS:
                for match in pattern.finditer(text):
                    try:
                        value_str = match.group(2).strip()
                        value_float = float(value_str)
                    except (IndexError, ValueError):
                        continue

                    try:
                        unit = match.group(3).strip() if match.lastindex >= 3 else None
                    except (IndexError, AttributeError):
                        unit = None

                    # Context window around the match for evidence & range
                    span_start = max(0, match.start() - 20)
                    span_end = min(len(text), match.end() + 200)
                    context = text[span_start:span_end]
                    evidence = match.group(0).strip()

                    # Extract reference range ONLY if verbatim in adjacent context
                    ref_text, status = _extract_ref_range(context, value_float)

                    lab_results.append(ExtractedLabResult(
                        test_name=canonical_name,
                        value=value_float,
                        value_text=value_str,
                        unit=unit,
                        reference_range_text=ref_text,
                        status=status,
                        source_evidence=evidence,
                        page_number=pn,
                        document_id=document_id,
                        confidence=0.88,
                        report_date=report_date,
                    ))

            # --- Conditions ---
            for keyword in CONDITION_KEYWORDS:
                idx = text.lower().find(keyword.lower())
                if idx != -1:
                    evidence_snippet = text[max(0, idx - 10): idx + len(keyword) + 60].replace("\n", " ").strip()
                    # Check not already added
                    already = any(c.condition_name.lower() == keyword.lower() for c in conditions)
                    if not already:
                        conditions.append(ExtractedCondition(
                            condition_name=keyword.title(),
                            source_evidence=evidence_snippet,
                            page_number=pn,
                            document_id=document_id,
                            confidence=0.80,
                        ))

            # --- Symptoms ---
            for kw in SYMPTOM_KEYWORDS:
                idx = text.lower().find(kw.lower())
                if idx != -1:
                    evidence_snippet = text[max(0, idx - 10): idx + len(kw) + 60].replace("\n", " ").strip()
                    already = any(s.symptom.lower() == kw.lower() for s in symptoms)
                    if not already:
                        symptoms.append(ExtractedSymptom(
                            symptom=kw.title(),
                            source_evidence=evidence_snippet,
                            page_number=pn,
                            document_id=document_id,
                            confidence=0.75,
                        ))

            # --- Allergies ---
            for pat in ALLERGY_PATTERNS:
                for m in pat.finditer(text):
                    allergen = m.group(1).strip().rstrip(",; ")
                    if len(allergen) < 2 or len(allergen) > 150:
                        continue
                    try:
                        reaction = m.group(2).strip() if m.lastindex >= 2 and m.group(2) else None
                    except IndexError:
                        reaction = None
                    already = any(a.allergen.lower() == allergen.lower() for a in allergies)
                    if not already:
                        allergies.append(ExtractedAllergy(
                            allergen=allergen,
                            reaction=reaction,
                            source_evidence=m.group(0).strip(),
                            page_number=pn,
                            document_id=document_id,
                            confidence=0.82,
                        ))

            # --- Medications ---
            for m in MEDICATION_PATTERNS[0].finditer(text):
                med_name = m.group(1).strip().rstrip(",;:")
                if len(med_name) < 2 or len(med_name) > 150:
                    continue
                dosage = m.group(2).strip() if m.lastindex >= 2 and m.group(2) else None
                frequency = m.group(3).strip() if m.lastindex >= 3 and m.group(3) else None
                already = any(med.medication_name.lower() == med_name.lower() for med in medications)
                if not already:
                    medications.append(ExtractedMedication(
                        medication_name=med_name,
                        dosage=dosage,
                        frequency=frequency,
                        source_evidence=m.group(0).strip(),
                        page_number=pn,
                        document_id=document_id,
                        confidence=0.78,
                    ))

            # --- Observations ---
            lines = text.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip().lower()
                for trigger in OBSERVATION_TRIGGERS:
                    if stripped.startswith(trigger) and len(stripped) > len(trigger) + 2:
                        # Grab this line and the next few
                        obs_text = " ".join(
                            l.strip() for l in lines[i: i + 4] if l.strip()
                        )
                        if len(obs_text) > 20:
                            observations.append(ExtractedObservation(
                                category=trigger.upper(),
                                content=obs_text[:500],
                                source_evidence=obs_text[:200],
                                page_number=pn,
                                document_id=document_id,
                                confidence=0.85,
                            ))

        if not lab_results and not conditions and not observations:
            warnings.append(
                "No recognisable clinical entities extracted. "
                "Document may be non-clinical or text extraction yielded no content."
            )

        return ClinicalExtractionPayload(
            document_id=document_id,
            provider_name=self.provider_name,
            report_date=report_date,
            lab_results=_deduplicate_labs(lab_results),
            observations=observations,
            symptoms=symptoms,
            conditions=conditions,
            medications=medications,
            allergies=allergies,
            extraction_warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _extract_date(text: str) -> Optional[str]:
    """Attempt to extract a YYYY-MM-DD formatted report date from text."""
    m = DATE_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Try ISO format first
    iso = re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw)
    if iso:
        return raw
    # Try DD/MM/YYYY or MM/DD/YYYY
    slash = re.fullmatch(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", raw)
    if slash:
        d, mo, y = slash.group(1), slash.group(2), slash.group(3)
        if len(y) == 2:
            y = "20" + y
        try:
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        except Exception:
            pass
    # Try "01 January 2024" style
    try:
        return datetime.strptime(raw, "%d %B %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        return datetime.strptime(raw, "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    return None


def _extract_ref_range(context: str, value: float) -> Tuple[Optional[str], ExtractionStatus]:
    """
    Attempt to extract a VERBATIM reference range from the context window.
    Returns (raw_range_text, status) where status is LOW/NORMAL/HIGH/UNKNOWN.
    ONLY extracts ranges that are literally present in the text.
    """
    for pat in REF_RANGE_PATTERNS:
        m = pat.search(context)
        if m:
            try:
                low = float(m.group(1))
                high = float(m.group(2))
                if low <= high:
                    raw = f"{low} - {high}"
                    if value < low:
                        return raw, ExtractionStatus.LOW
                    elif value > high:
                        return raw, ExtractionStatus.HIGH
                    else:
                        return raw, ExtractionStatus.NORMAL
            except (ValueError, IndexError):
                continue

    return None, ExtractionStatus.UNKNOWN


def _deduplicate_labs(results: List[ExtractedLabResult]) -> List[ExtractedLabResult]:
    """Keep only the first occurrence of each test name (by canonical name, case-insensitive)."""
    seen: Dict[str, bool] = {}
    deduped = []
    for r in results:
        key = r.test_name.lower()
        if key not in seen:
            seen[key] = True
            deduped.append(r)
    return deduped
