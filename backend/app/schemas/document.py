from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class DocumentProcessingJobResponse(BaseModel):
    id: str
    document_id: str
    status: str
    current_step: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    log_messages: str
    model_config = ConfigDict(from_attributes=True)

class DocumentResponse(BaseModel):
    id: str
    patient_id: str
    original_filename: str
    stored_filename: str
    file_type: str
    file_size_bytes: int
    sha256_checksum: str
    report_date: Optional[str] = None
    document_type: str
    facility: Optional[str] = None
    source: Optional[str] = None
    processing_status: str
    processing_error: Optional[str] = None
    raw_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(DocumentResponse):
    processing_jobs: List[DocumentProcessingJobResponse] = []
    model_config = ConfigDict(from_attributes=True)

class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    job: DocumentProcessingJobResponse
    message: str

class DocumentRetryResponse(BaseModel):
    document_id: str
    status: str
    current_step: str
    message: str

class DocumentStatusResponse(BaseModel):
    document_id: str
    processing_status: str
    processing_error: Optional[str] = None
    current_step: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    log_messages: Optional[str] = None
