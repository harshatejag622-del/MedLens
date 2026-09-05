import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class ReferenceRange(Base):
    __tablename__ = "reference_ranges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lab_result_id = Column(String(36), ForeignKey("lab_results.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    raw_text = Column(String(200), nullable=True)
    low_value = Column(Float, nullable=True)
    high_value = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    is_assessable = Column(Boolean, default=True, nullable=False)
    source_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lab_result = relationship("LabResult", back_populates="reference_range_rel")
