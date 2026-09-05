import re
from datetime import datetime, date
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

# =====================================================================
# Clinical Sub-Entity Schemas (Condition, Allergy, Medication, Symptom)
# =====================================================================

class ConditionBase(BaseModel):
    condition_name: str = Field(..., min_length=1, max_length=200, description="Clinical diagnosis / condition name")
    status: str = Field(default="ACTIVE", description="ACTIVE, RESOLVED, HISTORICAL")
    diagnosed_date: Optional[str] = Field(None, description="Date of diagnosis (YYYY-MM-DD or approx)")
    notes: Optional[str] = None
    provenance: str = Field(default="USER_PROVIDED", description="Source provenance: USER_PROVIDED, DOCUMENT_EXTRACTED, etc.")

    @field_validator("condition_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Condition name cannot be empty")
        return s

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"ACTIVE", "RESOLVED", "HISTORICAL", "CHRONIC"}
        val = v.strip().upper()
        return val if val in allowed else "ACTIVE"

    @field_validator("provenance")
    @classmethod
    def enforce_provenance(cls, v: str) -> str:
        return v.strip() or "USER_PROVIDED"

class ConditionCreate(ConditionBase):
    pass

class ConditionResponse(ConditionBase):
    id: str
    patient_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AllergyBase(BaseModel):
    allergen: str = Field(..., min_length=1, max_length=200, description="Allergen name (e.g., Penicillin, Peanuts)")
    reaction: Optional[str] = Field(None, max_length=200, description="Clinical reaction (e.g., Anaphylaxis, Rash)")
    severity: str = Field(default="MODERATE", description="MILD, MODERATE, SEVERE, LIFE_THREATENING")
    provenance: str = Field(default="USER_PROVIDED", description="Source provenance")

    @field_validator("allergen")
    @classmethod
    def clean_allergen(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Allergen cannot be empty")
        return s

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"MILD", "MODERATE", "SEVERE", "LIFE_THREATENING"}
        val = v.strip().upper()
        return val if val in allowed else "MODERATE"

    @field_validator("provenance")
    @classmethod
    def enforce_provenance(cls, v: str) -> str:
        return v.strip() or "USER_PROVIDED"

class AllergyCreate(AllergyBase):
    pass

class AllergyResponse(AllergyBase):
    id: str
    patient_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MedicationBase(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=200, description="Generic or brand medication name")
    dosage: Optional[str] = Field(None, max_length=100, description="Strength / dose (e.g., 10 mg)")
    frequency: Optional[str] = Field(None, max_length=100, description="Frequency (e.g., Once daily, BID)")
    route: str = Field(default="ORAL", description="Route: ORAL, IV, TOPICAL, INHALATION, etc.")
    provenance: str = Field(default="USER_PROVIDED", description="Source provenance")

    @field_validator("medication_name")
    @classmethod
    def clean_med_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Medication name cannot be empty")
        return s

    @field_validator("provenance")
    @classmethod
    def enforce_provenance(cls, v: str) -> str:
        return v.strip() or "USER_PROVIDED"

class MedicationCreate(MedicationBase):
    pass

class MedicationResponse(MedicationBase):
    id: str
    patient_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SymptomBase(BaseModel):
    symptom: str = Field(..., min_length=1, max_length=200, description="Reported symptom")
    duration: Optional[str] = Field(None, max_length=100, description="Duration (e.g., 3 weeks)")
    severity: str = Field(default="MODERATE", description="MILD, MODERATE, SEVERE")
    provenance: str = Field(default="USER_PROVIDED", description="Source provenance")

    @field_validator("symptom")
    @classmethod
    def clean_symptom(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Symptom cannot be empty")
        return s

    @field_validator("provenance")
    @classmethod
    def enforce_provenance(cls, v: str) -> str:
        return v.strip() or "USER_PROVIDED"

class SymptomCreate(SymptomBase):
    pass

class SymptomResponse(SymptomBase):
    id: str
    patient_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# Patient Core Schemas
# =====================================================================

class PatientBase(BaseModel):
    mrn: str = Field(..., min_length=2, max_length=50, description="Medical Record Number")
    first_name: str = Field(..., min_length=1, max_length=100, description="Patient's legal first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Patient's legal last name")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    age: int = Field(..., ge=0, le=130, description="Age in years (0 - 130)")
    sex: str = Field(..., description="Sex: MALE, FEMALE, OTHER, UNKNOWN")
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=100)
    relevant_history: Optional[str] = Field(None, description="Relevant clinical / surgical / family history")
    notes: Optional[str] = Field(None, description="Intake notes and clinical impressions")
    is_archived: bool = Field(default=False, description="Archive status flag")
    is_synthetic_demo: bool = Field(default=False, description="Explicit marker for synthetic demo records")

    @field_validator("mrn")
    @classmethod
    def validate_mrn(cls, v: str) -> str:
        s = v.strip().upper()
        if len(s) < 2:
            raise ValueError("MRN must be at least 2 characters")
        return s

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Name field cannot be empty or only spaces")
        return s

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        s = v.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            raise ValueError("Date of birth must follow YYYY-MM-DD format (e.g. 1985-06-15)")
        try:
            parsed = datetime.strptime(s, "%Y-%m-%d").date()
            if parsed > date.today():
                raise ValueError("Date of birth cannot be in the future")
        except ValueError as e:
            if "future" in str(e):
                raise e
            raise ValueError(f"Invalid date of birth calendar date: {s}")
        return s

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str) -> str:
        allowed = {"MALE", "FEMALE", "OTHER", "UNKNOWN"}
        val = v.strip().upper()
        if val not in allowed:
            raise ValueError(f"Sex must be one of {allowed}")
        return val


class PatientCreate(PatientBase):
    conditions: Optional[List[ConditionCreate]] = []
    allergies: Optional[List[AllergyCreate]] = []
    medications: Optional[List[MedicationCreate]] = []
    symptoms: Optional[List[SymptomCreate]] = []


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=130)
    sex: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    relevant_history: Optional[str] = None
    notes: Optional[str] = None
    is_archived: Optional[bool] = None
    conditions: Optional[List[ConditionCreate]] = None
    allergies: Optional[List[AllergyCreate]] = None
    medications: Optional[List[MedicationCreate]] = None
    symptoms: Optional[List[SymptomCreate]] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            raise ValueError("Date of birth must follow YYYY-MM-DD format")
        parsed = datetime.strptime(s, "%Y-%m-%d").date()
        if parsed > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return s

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        allowed = {"MALE", "FEMALE", "OTHER", "UNKNOWN"}
        val = v.strip().upper()
        if val not in allowed:
            raise ValueError(f"Sex must be one of {allowed}")
        return val


class PatientResponse(PatientBase):
    id: str
    created_at: datetime
    updated_at: datetime
    conditions: List[ConditionResponse] = []
    allergies: List[AllergyResponse] = []
    medications: List[MedicationResponse] = []
    symptoms: List[SymptomResponse] = []

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# Comprehensive Patient Overview Schemas
# =====================================================================

class DocumentOverviewItem(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    facility_name: Optional[str] = None
    upload_date: datetime
    processing_status: str
    sha256_checksum: str
    model_config = ConfigDict(from_attributes=True)

class LabResultOverviewItem(BaseModel):
    id: str
    test_name: str
    category: str
    numerical_value: Optional[float] = None
    text_value: Optional[str] = None
    unit: Optional[str] = None
    flag: str
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    reference_text: Optional[str] = None
    collection_date: Optional[datetime] = None
    provenance: Optional[str] = "AI_EXTRACTED"
    is_verified: Optional[bool] = False
    original_ai_value: Optional[str] = None
    confidence: Optional[float] = 1.0
    model_config = ConfigDict(from_attributes=True)

class ConflictOverviewItem(BaseModel):
    id: str
    conflict_type: str
    severity: str
    description: str
    status: str
    source_one: Optional[str] = None
    source_two: Optional[str] = None
    conflicting_values: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SummaryOverviewItem(BaseModel):
    id: str
    summary_type: str
    content: str
    provenance: str
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TimelineEventOverviewItem(BaseModel):
    id: str
    date: str
    title: str
    event_type: str # INTAKE, CONDITION, ALLERGY, MEDICATION, DOCUMENT, LAB, CONFLICT
    description: str
    badge_type: str
    source_provenance: str

class PatientOverviewResponse(PatientResponse):
    documents: List[DocumentOverviewItem] = []
    lab_results: List[LabResultOverviewItem] = []
    conflicts: List[ConflictOverviewItem] = []
    summaries: List[SummaryOverviewItem] = []
    timeline: List[TimelineEventOverviewItem] = []
