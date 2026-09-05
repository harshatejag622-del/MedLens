"""
OCR & Text Extraction Service
==============================
Provides a provider-agnostic OCR abstraction for extracting page-level text
from medical documents (PDF, TXT). Returns structured per-page results with
exact character offsets and page numbers for source evidence grounding.

Supported providers:
  - PyPDFTextExtractor  — pure-text PDF extraction (page-aware)
  - PlainTextExtractor  — UTF-8 text files treated as a single page
"""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DocumentPageText:
    """Text content extracted from a single document page."""
    page_number: int
    text: str
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)

    def snippet(self, start: int, length: int = 120) -> str:
        """Return a readable evidence snippet anchored at char offset `start`."""
        return self.text[max(0, start): start + length].replace("\n", " ").strip()


@dataclass
class OCRResult:
    """Full extraction result for a document."""
    document_id: str
    pages: List[DocumentPageText]
    full_text: str = field(init=False)
    page_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.full_text = "\n\n".join(p.text for p in self.pages)
        self.page_count = len(self.pages)


class OCRError(Exception):
    """Raised when text extraction fails unrecoverably."""
    pass


# ---------------------------------------------------------------------------
# Abstract provider interface
# ---------------------------------------------------------------------------

class BaseOCRProvider(abc.ABC):
    """Abstract base class for document text extraction providers."""

    @abc.abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Return True if this provider can process the given file."""

    @abc.abstractmethod
    def extract(self, file_path: Path, document_id: str) -> OCRResult:
        """Extract and return page-level text from the file."""


# ---------------------------------------------------------------------------
# PDF extractor — page-aware using pypdf
# ---------------------------------------------------------------------------

class PyPDFTextExtractor(BaseOCRProvider):
    """Extracts text from PDF files using pypdf, preserving page boundaries."""

    SUPPORTED_SUFFIX = ".pdf"

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == self.SUPPORTED_SUFFIX

    def extract(self, file_path: Path, document_id: str) -> OCRResult:
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            raise OCRError(
                "pypdf is required for PDF extraction. Install it with: pip install pypdf"
            )

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise OCRError(f"Failed to open PDF '{file_path.name}': {exc}") from exc

        if len(reader.pages) == 0:
            raise OCRError(f"PDF '{file_path.name}' contains no pages.")

        pages: List[DocumentPageText] = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text() or ""
            except Exception:
                raw = ""
            # Normalise whitespace while preserving paragraph breaks
            cleaned = _normalise_whitespace(raw)
            pages.append(DocumentPageText(page_number=page_num, text=cleaned))

        return OCRResult(document_id=document_id, pages=pages)


# ---------------------------------------------------------------------------
# Plain-text extractor
# ---------------------------------------------------------------------------

class PlainTextExtractor(BaseOCRProvider):
    """Reads a UTF-8 text file and treats the whole file as page 1."""

    SUPPORTED_SUFFIXES = {".txt", ".text"}

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_SUFFIXES

    def extract(self, file_path: Path, document_id: str) -> OCRResult:
        try:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise OCRError(f"Failed to read text file '{file_path.name}': {exc}") from exc

        cleaned = _normalise_whitespace(raw)
        pages = [DocumentPageText(page_number=1, text=cleaned)]
        return OCRResult(document_id=document_id, pages=pages)


# ---------------------------------------------------------------------------
# Service router
# ---------------------------------------------------------------------------

class OCRService:
    """
    Unified OCR router.  Selects the appropriate provider based on file extension
    and delegates extraction.  Falls back to PlainTextExtractor for unknown types.
    """

    def __init__(self) -> None:
        self._providers: List[BaseOCRProvider] = [
            PyPDFTextExtractor(),
            PlainTextExtractor(),
        ]

    def extract(self, file_path: str, document_id: str) -> OCRResult:
        """
        Extract page-level text from a document file.

        Args:
            file_path: Absolute path to the stored document.
            document_id: Document UUID for result attribution.

        Returns:
            OCRResult with one entry per page.

        Raises:
            OCRError: If the file cannot be read or no provider can handle it.
        """
        path = Path(file_path)
        if not path.exists():
            raise OCRError(f"Document file not found: {file_path}")

        for provider in self._providers:
            if provider.can_handle(path):
                return provider.extract(path, document_id)

        # Unknown format — attempt UTF-8 text read as fallback
        try:
            return PlainTextExtractor().extract(path, document_id)
        except OCRError:
            raise OCRError(
                f"No OCR provider available for file type '{path.suffix}'."
            )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _normalise_whitespace(text: str) -> str:
    """
    Normalise whitespace: collapse multiple blank lines to one,
    strip trailing spaces on each line, preserve paragraph structure.
    """
    lines = text.splitlines()
    cleaned_lines = [line.rstrip() for line in lines]
    # Collapse 3+ consecutive blank lines into 2
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines))
    return result.strip()


# Module-level singleton
ocr_service = OCRService()
