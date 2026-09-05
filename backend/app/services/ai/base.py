from __future__ import annotations
"""
Abstract Base for Clinical Extraction Providers
================================================
Defines the interface that all AI extraction providers must implement.
Providers are expected to be stateless — all state is passed as arguments.
"""


import abc
from typing import List

from app.services.ocr_service import DocumentPageText
from app.services.ai.schemas import ClinicalExtractionPayload


class ClinicalExtractionProvider(abc.ABC):
    """
    Abstract interface for AI-powered clinical extraction.

    Implementations:
      - GeminiExtractionProvider  — Google Gemini API (structured output)
      - DeterministicMockProvider — Regex/NLP engine for offline dev and tests
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier (e.g. 'gemini-1.5-flash', 'mock')."""

    @abc.abstractmethod
    def extract(
        self,
        pages: List[DocumentPageText],
        document_id: str,
        document_type: str = "LABORATORY_REPORT",
        patient_context: dict | None = None,
    ) -> ClinicalExtractionPayload:
        """
        Perform clinical extraction against the supplied page-level texts.

        Args:
            pages: Page texts produced by OCRService.
            document_id: UUID of the source document.
            document_type: Hints the AI toward appropriate entity types.
            patient_context: Optional dict with patient demographics for context.

        Returns:
            ClinicalExtractionPayload — validated structured data.
            If extraction fails, raise ExtractionError.
        """


class ExtractionError(Exception):
    """Raised when an AI provider fails to produce a usable extraction."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable
