from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LabResultResponse(BaseModel):
    id: str
    patient_id: str
    document_id: Optional[str] = None
    test_name: str
    value: Optional[float] = None
    value_text: str
    unit: Optional[str] = None
    raw_reference_range: Optional[str] = None
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    status: str # LOW, NORMAL, HIGH, UNKNOWN
    source_evidence: Optional[str] = None
    page_number: int = 1
    confidence: float
    confidence_level: str
    provenance: str
    is_verified: bool
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    original_ai_value: Optional[str] = None
    original_ai_unit: Optional[str] = None
    original_ai_range: Optional[str] = None
    version: int
    report_date: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class LabResultCorrectionRequest(BaseModel):
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    raw_reference_range: Optional[str] = None
    change_reason: Optional[str] = None
    reviewer_id: str = "clinician_user"

class LabComparisonItem(BaseModel):
    test_name: str
    current_value: Optional[float]
    current_value_text: str
    current_unit: Optional[str]
    current_date: Optional[str]
    current_status: str
    current_range: Optional[str]
    
    previous_value: Optional[float]
    previous_value_text: str
    previous_unit: Optional[str]
    previous_date: Optional[str]
    previous_status: str
    previous_range: Optional[str]
    
    change_absolute: Optional[float] = None
    change_percentage: Optional[float] = None
    comparison_note: str # Neutral language e.g. "Value changed from X to Y" or "Comparison unavailable because units differ"
    safe_to_compare: bool

class SummaryResponse(BaseModel):
    id: str
    patient_id: str
    summary_text: str
    disclaimer: str
    model_provider: str
    provenance: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
