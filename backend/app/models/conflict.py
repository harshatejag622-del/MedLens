import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class ConflictItem(Base):
    __tablename__ = "conflicts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    conflict_type = Column(String(100), nullable=False) # MEDICATION_ALLERGY, MEDICATION_DISCREPANCY, DIAGNOSIS_DISCREPANCY, LAB_DISCREPANCY, DEMOGRAPHIC_MISMATCH, DUPLICATE_DOCUMENT, UNIT_MISMATCH
    severity = Column(String(20), default="MEDIUM") # HIGH, MEDIUM, LOW, INFO
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    source_a = Column(Text, nullable=True) # Source 1
    source_b = Column(Text, nullable=True) # Source 2
    conflicting_values = Column(Text, nullable=True) # JSON or descriptive string of opposing values
    status = Column(String(30), default="OPEN") # OPEN, REVIEWED, RESOLVED, DISMISSED
    resolution_notes = Column(Text, nullable=True) # Reviewer note
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="conflicts")

class ReviewItem(Base):
    __tablename__ = "review_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(50), nullable=False) # LAB_RESULT, PATIENT_FIELD, EXTRACTION, MEDICATION, ALLERGY, CONDITION
    target_id = Column(String(36), nullable=False)
    field_name = Column(String(100), nullable=False)
    current_value = Column(Text, nullable=True)
    original_value = Column(Text, nullable=True) # Original unedited AI value preserved verbatim
    corrected_value = Column(Text, nullable=True) # Human-corrected value if edited
    confidence = Column(Float, default=1.0)
    source_text = Column(Text, nullable=True) # Excerpt from source document / evidence
    reason = Column(Text, nullable=False) # e.g. "Low extraction confidence (<0.85)", "Missing reference range in source"
    priority = Column(String(20), default="MEDIUM") # HIGH, MEDIUM, LOW
    status = Column(String(30), default="PENDING") # PENDING, ACCEPTED, EDITED, REJECTED, DEFERRED
    reviewer_note = Column(Text, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="review_items")
    patient = relationship("Patient")
