"""
MedLens HL7 FHIR R4 Serializer Service
Translates internal MedLens clinical data models to standardized
HL7 FHIR Release 4 Bundle resources for EHR interoperability.
"""

from typing import Dict, Any, List
from datetime import datetime
import uuid
from app.models.patient import Patient

def convert_patient_to_fhir_bundle(patient: Patient) -> Dict[str, Any]:
    """
    Serializes a MedLens Patient and all associated confirmed clinical entities
    into an official HL7 FHIR R4 Bundle (collection type).
    """
    entries: List[Dict[str, Any]] = []

    # 1. FHIR Patient Resource
    gender_map = {
        "MALE": "male",
        "FEMALE": "female",
        "OTHER": "other"
    }
    fhir_gender = gender_map.get((patient.sex or "").upper(), "unknown")

    telecom = []
    if patient.contact_phone:
        telecom.append({"system": "phone", "value": patient.contact_phone, "use": "mobile"})
    if patient.contact_email:
        telecom.append({"system": "email", "value": patient.contact_email, "use": "home"})

    patient_resource = {
        "resourceType": "Patient",
        "id": patient.id,
        "identifier": [
            {
                "use": "usual",
                "system": "urn:oid:medlens:mrn",
                "value": patient.mrn
            }
        ],
        "active": not patient.is_archived,
        "name": [
            {
                "use": "official",
                "family": patient.last_name,
                "given": [patient.first_name]
            }
        ],
        "gender": fhir_gender,
        "birthDate": patient.date_of_birth,
        "telecom": telecom
    }

    if patient.is_synthetic_demo:
        patient_resource["meta"] = {
            "tag": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                    "code": "SYNTHETIC",
                    "display": "Synthetic Demonstration Record"
                }
            ]
        }

    entries.append({
        "fullUrl": f"urn:uuid:{patient.id}",
        "resource": patient_resource
    })

    # 2. FHIR Condition Resources
    for condition in getattr(patient, "conditions", []):
        cond_status = (condition.status or "ACTIVE").lower()
        if cond_status not in ["active", "recurrence", "relapse", "inactive", "remission", "resolved"]:
            cond_status = "active"

        cond_resource = {
            "resourceType": "Condition",
            "id": condition.id,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": cond_status
                    }
                ]
            },
            "code": {
                "text": condition.condition_name
            },
            "subject": {
                "reference": f"Patient/{patient.id}"
            }
        }
        if condition.diagnosed_date:
            cond_resource["recordedDate"] = condition.diagnosed_date

        entries.append({
            "fullUrl": f"urn:uuid:{condition.id}",
            "resource": cond_resource
        })

    # 3. FHIR Observation Resources (Lab Results)
    for lab in getattr(patient, "lab_results", []):
        obs_resource: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": lab.id,
            "status": "final" if lab.is_verified else "preliminary",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory"
                        }
                    ]
                }
            ],
            "code": {
                "text": lab.test_name
            },
            "subject": {
                "reference": f"Patient/{patient.id}"
            }
        }

        if lab.report_date:
            obs_resource["effectiveDateTime"] = lab.report_date

        if lab.value is not None:
            obs_resource["valueQuantity"] = {
                "value": lab.value,
                "unit": lab.unit or "",
                "system": "http://unitsofmeasure.org"
            }
        else:
            obs_resource["valueString"] = lab.value_text

        # Interpretation based on deterministic classification
        if lab.status in ["HIGH", "LOW", "NORMAL"]:
            interp_code = "H" if lab.status == "HIGH" else ("L" if lab.status == "LOW" else "N")
            obs_resource["interpretation"] = [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": interp_code,
                            "display": lab.status
                        }
                    ]
                }
            ]

        # Reference range
        ref_ranges = []
        if lab.reference_low is not None or lab.reference_high is not None or lab.raw_reference_range:
            rr: Dict[str, Any] = {}
            if lab.reference_low is not None:
                rr["low"] = {"value": lab.reference_low, "unit": lab.unit or ""}
            if lab.reference_high is not None:
                rr["high"] = {"value": lab.reference_high, "unit": lab.unit or ""}
            if lab.raw_reference_range:
                rr["text"] = lab.raw_reference_range
            ref_ranges.append(rr)

        if ref_ranges:
            obs_resource["referenceRange"] = ref_ranges

        entries.append({
            "fullUrl": f"urn:uuid:{lab.id}",
            "resource": obs_resource
        })

    # 4. FHIR AllergyIntolerance Resources
    for allergy in getattr(patient, "allergies", []):
        allergy_resource: Dict[str, Any] = {
            "resourceType": "AllergyIntolerance",
            "id": allergy.id,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "code": "active"
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                        "code": "confirmed"
                    }
                ]
            },
            "code": {
                "text": allergy.allergen
            },
            "patient": {
                "reference": f"Patient/{patient.id}"
            },
            "criticality": "high" if (allergy.severity or "").upper() in ["SEVERE", "ANAPHYLAXIS"] else "low"
        }
        if allergy.reaction:
            allergy_resource["reaction"] = [
                {
                    "manifestation": [
                        {
                            "text": allergy.reaction
                        }
                    ]
                }
            ]

        entries.append({
            "fullUrl": f"urn:uuid:{allergy.id}",
            "resource": allergy_resource
        })

    # Bundle Envelope
    bundle = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "meta": {
            "profile": [
                "http://hl7.org/fhir/StructureDefinition/Bundle"
            ]
        },
        "total": len(entries),
        "entry": entries
    }

    return bundle
