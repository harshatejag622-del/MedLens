from app.utils.datetime_utils import utc_now_naive, utc_now
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_checksum = Column(String(64), index=True, nullable=False)
    report_date = Column(String(20), nullable=True)
    document_type = Column(String(100), default="LABORATORY_REPORT")
    facility = Column(String(200), nullable=True)
    source = Column(String(200), nullable=True)
    processing_status = Column(String(50), default="QUEUED", index=True) # QUEUED, PROCESSING, COMPLETED, FAILED, REVIEW_REQUIRED
    processing_error = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="document", cascade="all, delete-orphan")
    review_items = relationship("ReviewItem", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("DocumentProcessingJob", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_patient_status", "patient_id", "processing_status"),
    )

class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    document = relationship("Document", back_populates="pages")

class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="QUEUED", index=True)
    current_step = Column(String(100), default="INITIALIZING")
    started_at = Column(DateTime, default=utc_now_naive, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    log_messages = Column(Text, default="")

    document = relationship("Document", back_populates="processing_jobs")

# Alias for compatibility
ProcessingJob = DocumentProcessingJob
