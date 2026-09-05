from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal

class ExtractedReferenceRange(BaseModel):
    raw: Optional[str] = None
    low: Optional[float] = None
    high: Optional[float] = None

class ExtractedLabResult(BaseModel):
    testName: str = Field(..., description="Standardized lab test name")
    value: Optional[float] = Field(None, description="Numeric parsed value")
    valueText: str = Field(..., description="Raw text representation of value")
    unit: Optional[str] = Field(None, description="Reported unit of measure")
    referenceRange: ExtractedReferenceRange = Field(default_factory=ExtractedReferenceRange)
    status: Literal["LOW", "NORMAL", "HIGH", "UNKNOWN"] = Field(..., description="Calculated status")
    sourceEvidence: Optional[str] = Field(None, description="Exact text snippet from the document")
    pageNumber: int = Field(1, description="Page number of the extraction")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    provenance: str = Field("AI_EXTRACTED", description="Provenance marker")

class ExtractedObservation(BaseModel):
    category: str = "GENERAL"
    content: str
    sourceEvidence: Optional[str] = None
    confidence: float = 1.0

class ExtractedCondition(BaseModel):
    conditionName: str
    status: str = "ACTIVE"
    sourceEvidence: Optional[str] = None

class ExtractedMedication(BaseModel):
    medicationName: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    sourceEvidence: Optional[str] = None

class ExtractedAllergy(BaseModel):
    allergen: str
    reaction: Optional[str] = None
    severity: Optional[str] = "MODERATE"
    sourceEvidence: Optional[str] = None

class ExtractedSymptom(BaseModel):
    symptom: str
    duration: Optional[str] = None
    sourceEvidence: Optional[str] = None

class ExtractedDocumentMetadata(BaseModel):
    documentType: str = "LABORATORY_REPORT"
    reportDate: Optional[str] = None
    facility: Optional[str] = None
    patientName: Optional[str] = None
    patientDob: Optional[str] = None
    patientSex: Optional[str] = None

class ClinicalExtractionSchema(BaseModel):
    document: ExtractedDocumentMetadata = Field(default_factory=ExtractedDocumentMetadata)
    laboratoryResults: List[ExtractedLabResult] = Field(default_factory=list)
    observations: List[ExtractedObservation] = Field(default_factory=list)
    conditions: List[ExtractedCondition] = Field(default_factory=list)
    medications: List[ExtractedMedication] = Field(default_factory=list)
    allergies: List[ExtractedAllergy] = Field(default_factory=list)
    symptoms: List[ExtractedSymptom] = Field(default_factory=list)
