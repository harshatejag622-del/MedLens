import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(String(100), default="clinician_user")
    action = Column(String(100), nullable=False) # PATIENT_CREATED, DOCUMENT_UPLOADED, EXTRACTION_COMPLETED, FIELD_EDITED, FIELD_VERIFIED, CONFLICT_RESOLVED, SUMMARY_GENERATED, RECORD_EXPORTED
    entity_type = Column(String(50), nullable=False) # PATIENT, DOCUMENT, LAB_RESULT, CONFLICT, SUMMARY
    entity_id = Column(String(100), nullable=False)
    details = Column(Text, nullable=True) # JSON details of the action
    ip_address = Column(String(50), default="127.0.0.1")

class VerificationEvent(Base):
    __tablename__ = "verification_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_id = Column(String(36), nullable=False)
    target_type = Column(String(50), default="LAB_RESULT")
    verified_by = Column(String(100), default="clinician_user")
    original_value = Column(String(200), nullable=True)
    corrected_value = Column(String(200), nullable=True)
    change_reason = Column(Text, nullable=True)
    provenance = Column(String(50), default="HUMAN_VERIFIED")
    timestamp = Column(DateTime, default=datetime.utcnow)
