"""
Google Gemini Clinical Extraction Provider
==========================================
Calls the Gemini REST API (gemini-1.5-flash or gemini-2.5-flash) to extract
structured clinical entities from medical document text.

Requires GEMINI_API_KEY environment variable.

Features:
  - System prompt enforcing strict JSON schema output and anti-hallucination rules
  - Automatic retry with exponential backoff on transient failures
  - JSON parsing with fallback extraction
  - Full validation via Pydantic schemas before returning payload
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.ocr_service import DocumentPageText
from app.services.ai.base import ClinicalExtractionProvider, ExtractionError
from app.services.ai.schemas import (
    ClinicalExtractionPayload,
    ExtractedAllergy,
    ExtractedCondition,
    ExtractedLabResult,
    ExtractedMedication,
    ExtractedObservation,
    ExtractedSymptom,
    Provenance,
)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0

SYSTEM_PROMPT = """You are a highly accurate clinical data extraction AI integrated into a medical records management system.

Your task is to extract structured clinical entities from medical document text.

STRICT RULES YOU MUST FOLLOW:

1. REFERENCE RANGES — CRITICAL SAFETY RULE:
   - You MUST ONLY include a reference_range_text if the range is EXPLICITLY stated in the document text.
   - If the document does NOT provide a reference range, set reference_range_text to null.
   - NEVER invent, infer, or fill in reference ranges from your medical knowledge.
   - If reference_range_text is null, status MUST be "UNKNOWN".
   - This rule exists to prevent clinical harm from hallucinated reference data.

2. SOURCE EVIDENCE:
   - Every extracted entity must include source_evidence: a VERBATIM quote from the document that supports the extraction.
   - The quote must actually appear in the text provided.

3. CONFIDENCE:
   - Set confidence between 0.0 and 1.0 based on clarity of the evidence.
   - Use 0.95+ for clearly stated values, 0.7-0.9 for implicit mentions, <0.7 for uncertain inferences.

4. OUTPUT FORMAT:
   - Return ONLY a single JSON object matching the schema below.
   - No markdown, no code blocks, no explanations, no comments.

OUTPUT SCHEMA:
{
  "report_date": "YYYY-MM-DD or null",
  "lab_results": [
    {
      "test_name": "string",
      "value": float_or_null,
      "value_text": "string",
      "unit": "string_or_null",
      "reference_range_text": "verbatim_from_doc_or_null",
      "status": "LOW|NORMAL|HIGH|UNKNOWN",
      "source_evidence": "verbatim_quote",
      "page_number": integer_or_null,
      "confidence": float
    }
  ],
  "observations": [
    {
      "category": "GENERAL|IMPRESSION|RECOMMENDATION|HISTORY",
      "content": "string",
      "source_evidence": "verbatim_quote",
      "page_number": integer_or_null,
      "confidence": float
    }
  ],
  "symptoms": [
    {
      "symptom": "string",
      "duration": "string_or_null",
      "severity": "string_or_null",
      "source_evidence": "verbatim_quote",
      "page_number": integer_or_null,
      "confidence": float
    }
  ],
  "conditions": [
    {
      "condition_name": "string",
      "icd10_code": "string_or_null",
      "status": "ACTIVE|RESOLVED|CHRONIC|SUSPECTED|HISTORICAL|null",
      "source_evidence": "verbatim_quote",
      "page_number": integer_or_null,
      "confidence": float
    }
  ],
  "medications": [
    {
      "medication_name": "string",
      "dosage": "string_or_null",
      "frequency": "string_or_null",
      "route": "string_or_null",
      "source_evidence": "verbatim_quote",
      "page_number": integer_or_null,
      "confidence": float
    }
  ],
  "allergies": [
    {
      "allergen": "string",
      "reaction": "string_or_null",
      "severity": "MILD|MODERATE|SEVERE|LIFE_THREATENING|null",
      "source_evidence": "verbatim_quote",
      "page_number": integer_or_null,
      "confidence": float
    }
  ]
}"""


class GeminiExtractionProvider(ClinicalExtractionProvider):
    """
    Google Gemini API extraction provider.
    Uses structured JSON generation with a strict clinical extraction system prompt.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model = model or settings.GEMINI_MODEL
        if not self._api_key:
            raise ExtractionError(
                "GEMINI_API_KEY is not set. Configure it in .env or set AI_PROVIDER=local.",
                retryable=False,
            )

    @property
    def provider_name(self) -> str:
        return self._model

    def extract(
        self,
        pages: List[DocumentPageText],
        document_id: str,
        document_type: str = "LABORATORY_REPORT",
        patient_context: dict | None = None,
    ) -> ClinicalExtractionPayload:
        user_prompt = self._build_user_prompt(pages, document_type, patient_context)
        raw_response = self._call_gemini_with_retry(user_prompt)
        parsed = self._parse_response(raw_response, document_id)
        return parsed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        pages: List[DocumentPageText],
        document_type: str,
        patient_context: Optional[dict],
    ) -> str:
        parts = [f"Document Type: {document_type}"]
        if patient_context:
            parts.append(f"Patient Context: {json.dumps(patient_context)}")
        parts.append("\n--- DOCUMENT TEXT ---\n")
        for page in pages:
            parts.append(f"[Page {page.page_number}]\n{page.text}")
        parts.append("\n--- END DOCUMENT TEXT ---\n")
        parts.append("Extract all clinical entities. Return ONLY the JSON object.")
        return "\n".join(parts)

    def _call_gemini_with_retry(self, user_prompt: str) -> str:
        url = f"{GEMINI_API_BASE}/{self._model}:generateContent?key={self._api_key}"
        payload: Dict[str, Any] = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.05,   # near-deterministic for clinical extraction
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
            },
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    return self._extract_text_from_response(data)

                elif response.status_code in {429, 500, 502, 503}:
                    # Transient error — backoff and retry
                    wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    last_error = ExtractionError(
                        f"Gemini API transient error {response.status_code}: {response.text[:200]}",
                        retryable=True,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait)

                elif response.status_code == 401:
                    raise ExtractionError(
                        "Gemini API authentication failed. Check GEMINI_API_KEY.",
                        retryable=False,
                    )
                else:
                    raise ExtractionError(
                        f"Gemini API error {response.status_code}: {response.text[:500]}",
                        retryable=False,
                    )

            except httpx.TimeoutException as exc:
                last_error = ExtractionError(
                    f"Gemini API request timed out (attempt {attempt}/{MAX_RETRIES}): {exc}",
                    retryable=True,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF_SECONDS * attempt)

            except ExtractionError:
                raise

            except Exception as exc:
                raise ExtractionError(
                    f"Unexpected error calling Gemini API: {exc}", retryable=False
                ) from exc

        raise last_error or ExtractionError("Gemini API failed after all retries.", retryable=True)

    def _extract_text_from_response(self, data: Dict[str, Any]) -> str:
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ExtractionError(
                f"Unexpected Gemini response structure: {str(data)[:300]}",
                retryable=False,
            ) from exc

    def _parse_response(self, raw: str, document_id: str) -> ClinicalExtractionPayload:
        # Strip any markdown fences in case the model disobeys instructions
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                f"Gemini returned invalid JSON: {exc}. Raw (first 500): {raw[:500]}",
                retryable=False,
            ) from exc

        warnings: List[str] = []

        # Parse each entity list defensively
        lab_results = []
        for item in data.get("lab_results", []):
            try:
                item["document_id"] = document_id
                item["provenance"] = Provenance.AI_EXTRACTED
                lab_results.append(ExtractedLabResult(**item))
            except Exception as e:
                warnings.append(f"Skipped malformed lab result: {e}")

        observations = []
        for item in data.get("observations", []):
            try:
                item["document_id"] = document_id
                item["provenance"] = Provenance.AI_EXTRACTED
                observations.append(ExtractedObservation(**item))
            except Exception as e:
                warnings.append(f"Skipped malformed observation: {e}")

        symptoms = []
        for item in data.get("symptoms", []):
            try:
                item["document_id"] = document_id
                item["provenance"] = Provenance.AI_EXTRACTED
                symptoms.append(ExtractedSymptom(**item))
            except Exception as e:
                warnings.append(f"Skipped malformed symptom: {e}")

        conditions = []
        for item in data.get("conditions", []):
            try:
                item["document_id"] = document_id
                item["provenance"] = Provenance.AI_EXTRACTED
                conditions.append(ExtractedCondition(**item))
            except Exception as e:
                warnings.append(f"Skipped malformed condition: {e}")

        medications = []
        for item in data.get("medications", []):
            try:
                item["document_id"] = document_id
                item["provenance"] = Provenance.AI_EXTRACTED
                medications.append(ExtractedMedication(**item))
            except Exception as e:
                warnings.append(f"Skipped malformed medication: {e}")

        allergies = []
        for item in data.get("allergies", []):
            try:
                item["document_id"] = document_id
                item["provenance"] = Provenance.AI_EXTRACTED
                allergies.append(ExtractedAllergy(**item))
            except Exception as e:
                warnings.append(f"Skipped malformed allergy: {e}")

        return ClinicalExtractionPayload(
            document_id=document_id,
            provider_name=self.provider_name,
            report_date=data.get("report_date"),
            lab_results=lab_results,
            observations=observations,
            symptoms=symptoms,
            conditions=conditions,
            medications=medications,
            allergies=allergies,
            extraction_warnings=warnings,
            raw_response=raw[:4000] if raw else None,
        )
