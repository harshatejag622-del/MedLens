import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

class ExtractedEntity(Base):
    __tablename__ = "extracted_entities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    entity_type = Column(String(50), nullable=False, index=True) # CONDITION, MEDICATION, ALLERGY, SYMPTOM, OBSERVATION
    name = Column(String(255), nullable=False)
    value = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=True)
    
    source_evidence = Column(Text, nullable=True)
    page_number = Column(Integer, default=1)
    confidence = Column(Float, default=1.0)
    provenance = Column(String(50), default="AI_EXTRACTED")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_extracted_entities_patient_type", "patient_id", "entity_type"),
    )
