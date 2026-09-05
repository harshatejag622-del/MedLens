from abc import ABC, abstractmethod
from typing import Dict, Any
from app.schemas.extraction import ClinicalExtractionSchema

class BaseAIProvider(ABC):
    @abstractmethod
    def extract_clinical_information(
        self,
        document_text: str,
        metadata: Dict[str, Any] = None
    ) -> ClinicalExtractionSchema:
        """
        Extracts structured clinical data strictly conforming to ClinicalExtractionSchema.
        Must never return unvalidated free-form text.
        """
        pass

    @abstractmethod
    def generate_summary(
        self,
        structured_record: Dict[str, Any]
    ) -> str:
        """
        Generates a concise, patient-friendly summary grounded purely in structured record data.
        Must never diagnose, prescribe, or recommend dosage changes.
        """
        pass
