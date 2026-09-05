import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    
    test_name = Column(String(200), index=True, nullable=False)
    value = Column(Float, nullable=True)
    value_text = Column(String(100), nullable=False)
    unit = Column(String(50), nullable=True)
    
    # Reference range preservation columns
    raw_reference_range = Column(String(200), nullable=True)
    reference_low = Column(Float, nullable=True)
    reference_high = Column(Float, nullable=True)
    
    # Classification: LOW, NORMAL, HIGH, UNKNOWN
    status = Column(String(50), nullable=False, default="UNKNOWN", index=True)
    
    # Traceability & Provenance
    source_evidence = Column(Text, nullable=True)
    page_number = Column(Integer, default=1)
    confidence = Column(Float, default=1.0)
    confidence_level = Column(String(20), default="HIGH")
    provenance = Column(String(50), default="AI_EXTRACTED", index=True)
    
    # Human verification tracking
    is_verified = Column(Boolean, default=False, index=True)
    verified_by = Column(String(100), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Audit versioning
    original_ai_value = Column(String(100), nullable=True)
    original_ai_unit = Column(String(50), nullable=True)
    original_ai_range = Column(String(200), nullable=True)
    version = Column(Integer, default=1)
    
    report_date = Column(String(20), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="lab_results")
    document = relationship("Document", back_populates="lab_results")
    reference_range_rel = relationship("ReferenceRange", back_populates="lab_result", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_lab_results_patient_test", "patient_id", "test_name"),
        Index("idx_lab_results_patient_status", "patient_id", "status"),
    )

class Observation(Base):
    __tablename__ = "observations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    category = Column(String(100), default="GENERAL")
    content = Column(Text, nullable=False)
    source_evidence = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    provenance = Column(String(50), default="AI_EXTRACTED")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    disclaimer = Column(Text, nullable=False)
    model_provider = Column(String(50), default="local")
    provenance = Column(String(50), default="AI_GENERATED")
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="summaries")
