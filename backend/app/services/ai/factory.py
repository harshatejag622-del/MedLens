from __future__ import annotations
"""
AI Provider Factory
====================
Instantiates the appropriate ClinicalExtractionProvider based on application
configuration and available credentials.

Selection priority:
  1. If AI_PROVIDER == 'gemini' and GEMINI_API_KEY is set → GeminiExtractionProvider
  2. If AI_PROVIDER == 'gemini' and GEMINI_API_KEY is not set → warn + fallback to mock
  3. Default / AI_PROVIDER == 'local' → DeterministicMockProvider
"""


import logging
from typing import Optional

from app.config import settings
from app.services.ai.base import ClinicalExtractionProvider

logger = logging.getLogger(__name__)


def get_extraction_provider(
    override: Optional[str] = None,
) -> ClinicalExtractionProvider:
    """
    Return the configured ClinicalExtractionProvider.

    Args:
        override: Explicitly set provider name ('gemini' | 'local').
                  If None, uses settings.AI_PROVIDER.
    """
    provider_name = (override or settings.AI_PROVIDER).lower().strip()

    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            logger.warning(
                "AI_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                "Falling back to DeterministicMockProvider."
            )
            return _get_mock_provider()
        try:
            from app.services.ai.gemini_provider import GeminiExtractionProvider
            provider = GeminiExtractionProvider()
            logger.info(
                "GeminiExtractionProvider initialised with model '%s'.",
                settings.GEMINI_MODEL,
            )
            return provider
        except Exception as exc:
            logger.error(
                "Failed to initialise GeminiExtractionProvider: %s. "
                "Falling back to mock provider.",
                exc,
            )
            return _get_mock_provider()

    return _get_mock_provider()


def _get_mock_provider() -> ClinicalExtractionProvider:
    from app.services.ai.mock_provider import DeterministicMockProvider
    provider = DeterministicMockProvider()
    logger.info("DeterministicMockProvider initialised.")
    return provider
