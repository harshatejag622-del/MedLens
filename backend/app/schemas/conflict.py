from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ConflictResponse(BaseModel):
    id: str
    patient_id: str
    conflict_type: str
    severity: str
    title: str
    description: str
    source_a: Optional[str] = None
    source_b: Optional[str] = None
    conflicting_values: Optional[str] = None
    status: str
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ConflictResolveRequest(BaseModel):
    resolution_notes: str
    resolved_by: str = "clinician_user"
    new_status: str = "RESOLVED" # REVIEWED, RESOLVED, DISMISSED, OPEN

class ReviewItemResponse(BaseModel):
    id: str
    document_id: Optional[str] = None
    patient_id: str
    target_type: str
    target_id: str
    field_name: str
    current_value: Optional[str] = None
    original_value: Optional[str] = None
    corrected_value: Optional[str] = None
    confidence: Optional[float] = 1.0
    source_text: Optional[str] = None
    reason: str
    priority: str
    status: str
    reviewer_note: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewActionRequest(BaseModel):
    action: str # ACCEPT, CORRECT, REJECT, DEFER
    corrected_value: Optional[str] = None
    change_reason: Optional[str] = None
    reviewer_id: str = "clinician_user"
    reviewer_name: Optional[str] = "Dr. Clinician"
