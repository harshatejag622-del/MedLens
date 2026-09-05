from app.utils.datetime_utils import utc_now_naive, utc_now
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mrn = Column(String(50), unique=True, index=True, nullable=False) # Medical Record Number
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(String(10), nullable=False) # YYYY-MM-DD
    age = Column(Integer, nullable=False)
    sex = Column(String(20), nullable=False) # MALE, FEMALE, OTHER
    contact_phone = Column(String(30), nullable=True)
    contact_email = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    relevant_history = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, index=True)
    is_synthetic_demo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    # Relationships
    conditions = relationship("PatientCondition", back_populates="patient", cascade="all, delete-orphan")
    allergies = relationship("PatientAllergy", back_populates="patient", cascade="all, delete-orphan")
    medications = relationship("PatientMedication", back_populates="patient", cascade="all, delete-orphan")
    symptoms = relationship("PatientSymptom", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")
    conflicts = relationship("ConflictItem", back_populates="patient", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="patient", cascade="all, delete-orphan")

class PatientCondition(Base):
    __tablename__ = "patient_conditions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    condition_name = Column(String(200), nullable=False)
    status = Column(String(50), default="ACTIVE") # ACTIVE, RESOLVED, HISTORICAL
    diagnosed_date = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    provenance = Column(String(50), default="USER_PROVIDED")
    created_at = Column(DateTime, default=utc_now_naive)

    patient = relationship("Patient", back_populates="conditions")

class PatientAllergy(Base):
    __tablename__ = "patient_allergies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    allergen = Column(String(200), nullable=False)
    reaction = Column(String(200), nullable=True)
    severity = Column(String(50), default="MODERATE") # MILD, MODERATE, SEVERE, ANAPHYLAXIS
    provenance = Column(String(50), default="USER_PROVIDED")
    created_at = Column(DateTime, default=utc_now_naive)

    patient = relationship("Patient", back_populates="allergies")

class PatientMedication(Base):
    __tablename__ = "patient_medications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    medication_name = Column(String(200), nullable=False)
    dosage = Column(String(100), nullable=True)
    frequency = Column(String(100), nullable=True)
    route = Column(String(50), default="ORAL")
    provenance = Column(String(50), default="USER_PROVIDED")
    created_at = Column(DateTime, default=utc_now_naive)

    patient = relationship("Patient", back_populates="medications")

class PatientSymptom(Base):
    __tablename__ = "patient_symptoms"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    symptom = Column(String(200), nullable=False)
    duration = Column(String(100), nullable=True)
    severity = Column(String(50), default="MODERATE")
    provenance = Column(String(50), default="USER_PROVIDED")
    created_at = Column(DateTime, default=utc_now_naive)

    patient = relationship("Patient", back_populates="symptoms")
