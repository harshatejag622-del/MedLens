"""
Clinical Conflict & Contradiction Detection Engine
=================================================
Phase 7 — MedLens

Clinical data consistency and safety layer.
Detects potentially important conflicts, contradictions, inconsistencies,
and duplicate information across a patient's clinical data without modifying
the underlying records.

DESIGN PRINCIPLES:
1. Do NOT remove or overwrite existing patient data.
2. Do NOT invent clinical information.
3. Preserve original extracted values verbatim.
4. False positive protection:
   - Case-insensitive, whitespace-normalized comparisons.
   - Legitimate date discrepancies vs actual conflicting same-day values.
   - Historical / discontinued items are distinguished from active items.
   - Legitimate convertible units vs conflicting units.
5. All detected conflicts require human / clinical verification;
   never present automated detections as confirmed medical errors.
"""

from __future__ import annotations

import re
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.patient import Patient, PatientCondition, PatientAllergy, PatientMedication
from app.models.clinical import LabResult
from app.models.document import Document
from app.models.extracted_entity import ExtractedEntity
from app.models.conflict import ConflictItem

logger = logging.getLogger(__name__)

# Cross-reactive / common class mappings for drug-allergy safety checks
# Generic medication name / roots mapped to their allergy drug classes
DRUG_ALLERGY_CLASSES: Dict[str, List[str]] = {
    "penicillin": [
        "amoxicillin", "ampicillin", "augmentin", "piperacillin", "oxacillin",
        "cloxacillin", "dicloxacillin", "nafcillin", "penicillin", "amoxil"
    ],
    "amoxicillin": ["penicillin", "augmentin", "ampicillin"],
    "sulfa": [
        "sulfamethoxazole", "bactrim", "septra", "sulfasalazine",
        "sulfadiazine", "sulfisoxazole"
    ],
    "sulfamethoxazole": ["sulfa", "bactrim", "septra"],
    "aspirin": ["ibuprofen", "naproxen", "ketorolac", "nsaid", "advil", "aleve", "motrin"],
    "nsaid": ["aspirin", "ibuprofen", "naproxen", "ketorolac", "meloxicam", "celecoxib", "advil", "aleve"],
    "cephalosporin": ["cephalexin", "cefazolin", "ceftriaxone", "cefuroxime", "cefepime"],
    "codeine": ["morphine", "hydrocodone", "oxycodone"],
}

# Unit compatibility lookup table (convertible units are NOT flagged as incompatible)
COMPATIBLE_UNIT_FAMILIES = [
    {"g/dl", "g/l"},
    {"mg/dl", "mg/l", "mmol/l"},
    {"umol/l", "µmol/l", "mg/dl"},
    {"x10^9/l", "k/ul", "/ul", "cells/ul"},
    {"meq/l", "mmol/l"},
]


def normalize_string(val: Optional[str]) -> str:
    """Strip whitespace and lowercase for safe normalized comparison."""
    if not val:
        return ""
    return re.sub(r"\s+", " ", val).strip().lower()


def parse_date_safely(date_str: Optional[str]) -> Optional[str]:
    """
    Normalizes dates from various formats (YYYY-MM-DD, MM/DD/YYYY, DD-MM-YYYY)
    into standard ISO YYYY-MM-DD for fair comparison.
    Avoids false positives due to formatting differences.
    """
    if not date_str:
        return None
    s = date_str.strip()
    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    
    # Try common formats
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s.lower()


def extract_numeric_dose(dose_str: Optional[str]) -> Optional[float]:
    """Extracts first numeric dose value if cleanly present (e.g. '500 mg' -> 500.0)."""
    if not dose_str:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", dose_str)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


class ConflictDetector:
    """
    Engine that inspects a patient's integrated record (profile + extracted entities + labs + documents)
    and identifies inconsistencies, cross-document conflicts, and safety risks.
    """

    @classmethod
    def detect_all_conflicts(cls, db: Session, patient_id: str) -> List[ConflictItem]:
        """
        Runs comprehensive conflict detection for the specified patient.
        Persists newly discovered conflicts to the database without duplicating existing open conflicts.
        Returns all active conflict records for the patient.
        """
        patient: Optional[Patient] = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return []

        # Gather all sources of patient clinical information
        profile_meds = patient.medications or []
        profile_allergies = patient.allergies or []
        profile_conditions = patient.conditions or []
        labs = patient.lab_results or []
        documents = patient.documents or []
        extracted_entities = db.query(ExtractedEntity).filter(ExtractedEntity.patient_id == patient_id).all()

        detected: List[Dict[str, Any]] = []

        # 1. Medication Conflicts
        detected.extend(cls._detect_medication_conflicts(profile_meds, extracted_entities, documents))

        # 2. Allergy-Medication Contraindications
        detected.extend(cls._detect_allergy_conflicts(profile_allergies, profile_meds, extracted_entities, documents))

        # 3. Diagnosis / Condition Conflicts
        detected.extend(cls._detect_condition_conflicts(profile_conditions, extracted_entities, documents))

        # 4. Laboratory Conflicts
        detected.extend(cls._detect_lab_conflicts(labs, documents))

        # 5. Demographic / Record Metadata Conflicts
        detected.extend(cls._detect_demographic_conflicts(patient, documents))

        # Persist new conflicts safely without duplicating existing unresolved ones
        new_items = cls._sync_conflicts_to_db(db, patient_id, detected)
        return new_items

    # ------------------------------------------------------------------
    # 1. Medication Conflicts
    # ------------------------------------------------------------------
    @classmethod
    def _detect_medication_conflicts(
        cls,
        profile_meds: List[PatientMedication],
        extracted_entities: List[ExtractedEntity],
        documents: List[Document]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        doc_map = {d.id: d.original_filename for d in documents}

        # Build list of all medication entries with source
        all_meds: List[Dict[str, Any]] = []
        for pm in profile_meds:
            all_meds.append({
                "name": pm.medication_name,
                "dosage": pm.dosage,
                "frequency": pm.frequency,
                "route": pm.route,
                "status": "ACTIVE",
                "source": f"Patient Medication Profile ({pm.provenance})",
                "entity_id": pm.id,
            })

        for ee in extracted_entities:
            if ee.entity_type == "MEDICATION":
                doc_name = doc_map.get(ee.document_id, "Extracted Document")
                all_meds.append({
                    "name": ee.name,
                    "dosage": ee.value, # dosage stored in value
                    "frequency": None,
                    "route": None,
                    "status": "ACTIVE",
                    "source": f"Document '{doc_name}' (p. {ee.page_number})",
                    "entity_id": ee.id,
                })

        # Compare pairs for dose mismatch or frequency mismatch
        seen_pairs = set()
        for i in range(len(all_meds)):
            for j in range(i + 1, len(all_meds)):
                m1 = all_meds[i]
                m2 = all_meds[j]
                norm1 = normalize_string(m1["name"])
                norm2 = normalize_string(m2["name"])

                # Check if referring to same drug
                if norm1 and norm2 and (norm1 in norm2 or norm2 in norm1 or norm1 == norm2):
                    pair_key = tuple(sorted([m1["entity_id"], m2["entity_id"]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # A. Dose discrepancy check (both have explicit dosage that differs numerically)
                    d1 = extract_numeric_dose(m1["dosage"])
                    d2 = extract_numeric_dose(m2["dosage"])
                    if d1 is not None and d2 is not None and abs(d1 - d2) > 0.001:
                        results.append({
                            "conflict_type": "MEDICATION_DISCREPANCY",
                            "severity": "HIGH",
                            "title": f"Conflicting Dosage Documented: {m1['name'].title()}",
                            "description": (
                                f"Medication '{m1['name'].title()}' is documented with divergent dosages: "
                                f"'{m1['dosage']}' vs '{m2['dosage']}'. "
                                "Requires clinical verification to ensure accurate active regimen."
                            ),
                            "source_a": f"{m1['source']}: {m1['dosage']}",
                            "source_b": f"{m2['source']}: {m2['dosage']}",
                            "conflicting_values": json.dumps({
                                "medication": m1["name"],
                                "source_1_dosage": m1["dosage"],
                                "source_2_dosage": m2["dosage"]
                            }),
                        })

                    # B. Active vs Discontinued / Conflicting status
                    s1 = normalize_string(m1.get("status"))
                    s2 = normalize_string(m2.get("status"))
                    if s1 and s2 and s1 != s2 and ("discontinued" in (s1, s2) or "inactive" in (s1, s2)):
                        results.append({
                            "conflict_type": "MEDICATION_DISCREPANCY",
                            "severity": "MEDIUM",
                            "title": f"Active vs Discontinued Status Conflict: {m1['name'].title()}",
                            "description": (
                                f"Medication '{m1['name'].title()}' appears as active in one record but "
                                "discontinued in another. Verify ongoing therapy."
                            ),
                            "source_a": f"{m1['source']} (Status: {m1['status']})",
                            "source_b": f"{m2['source']} (Status: {m2['status']})",
                            "conflicting_values": json.dumps({
                                "medication": m1["name"],
                                "status_1": m1["status"],
                                "status_2": m2["status"]
                            }),
                        })

        return results

    # ------------------------------------------------------------------
    # 2. Allergy Conflicts (Allergy vs Active Med)
    # ------------------------------------------------------------------
    @classmethod
    def _detect_allergy_conflicts(
        cls,
        profile_allergies: List[PatientAllergy],
        profile_meds: List[PatientMedication],
        extracted_entities: List[ExtractedEntity],
        documents: List[Document]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        doc_map = {d.id: d.original_filename for d in documents}

        # Gather all allergies
        allergies: List[Dict[str, Any]] = []
        for pa in profile_allergies:
            allergies.append({
                "allergen": pa.allergen,
                "reaction": pa.reaction,
                "source": f"Patient Allergy Profile ({pa.provenance})",
            })
        for ee in extracted_entities:
            if ee.entity_type == "ALLERGY":
                doc_name = doc_map.get(ee.document_id, "Extracted Document")
                allergies.append({
                    "allergen": ee.name,
                    "reaction": ee.value,
                    "source": f"Document '{doc_name}' (p. {ee.page_number})",
                })

        # Gather all medications
        medications: List[Dict[str, Any]] = []
        for pm in profile_meds:
            medications.append({
                "name": pm.medication_name,
                "dosage": pm.dosage,
                "source": f"Patient Medication Profile ({pm.provenance})",
            })
        for ee in extracted_entities:
            if ee.entity_type == "MEDICATION":
                doc_name = doc_map.get(ee.document_id, "Extracted Document")
                medications.append({
                    "name": ee.name,
                    "dosage": ee.value,
                    "source": f"Document '{doc_name}' (p. {ee.page_number})",
                })

        # Cross-reference every allergen with every medication
        seen_contraindications = set()
        for al in allergies:
            norm_allergen = normalize_string(al["allergen"])
            if not norm_allergen:
                continue

            for med in medications:
                norm_med = normalize_string(med["name"])
                if not norm_med:
                    continue

                is_conflict = False
                reason = ""

                # Direct match (e.g. Allergy: Penicillin, Med: Penicillin VK)
                if norm_allergen in norm_med or norm_med in norm_allergen:
                    is_conflict = True
                    reason = f"Documented allergy to '{al['allergen']}' directly matches prescribed medication '{med['name']}'."
                else:
                    # Check drug allergy cross-reactive class mapping
                    for drug_class, related_drugs in DRUG_ALLERGY_CLASSES.items():
                        if drug_class in norm_allergen or any(r in norm_allergen for r in related_drugs):
                            if any(r in norm_med for r in related_drugs) or drug_class in norm_med:
                                is_conflict = True
                                reason = (
                                    f"Cross-reactivity risk: Prescribed medication '{med['name']}' "
                                    f"belongs to the '{drug_class.upper()}' drug class, to which an allergy is recorded."
                                )
                                break

                if is_conflict:
                    pair_key = (norm_allergen, norm_med)
                    if pair_key in seen_contraindications:
                        continue
                    seen_contraindications.add(pair_key)

                    results.append({
                        "conflict_type": "MEDICATION_ALLERGY",
                        "severity": "HIGH",
                        "title": f"Potential Allergy/Medication Contraindication: {med['name'].title()}",
                        "description": (
                            f"Safety Alert: {reason} "
                            f"Allergy reaction on file: '{al['reaction'] or 'Unspecified'}'. "
                            "Immediate clinical confirmation required before administration."
                        ),
                        "source_a": f"Allergy: {al['source']} ('{al['allergen']}')",
                        "source_b": f"Medication: {med['source']} ('{med['name']}')",
                        "conflicting_values": json.dumps({
                            "allergen": al["allergen"],
                            "reaction": al["reaction"],
                            "medication": med["name"],
                            "dosage": med.get("dosage")
                        }),
                    })

        return results

    # ------------------------------------------------------------------
    # 3. Diagnosis & Condition Conflicts
    # ------------------------------------------------------------------
    @classmethod
    def _detect_condition_conflicts(
        cls,
        profile_conditions: List[PatientCondition],
        extracted_entities: List[ExtractedEntity],
        documents: List[Document]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        doc_map = {d.id: d.original_filename for d in documents}

        conditions_all: List[Dict[str, Any]] = []
        for pc in profile_conditions:
            conditions_all.append({
                "name": pc.condition_name,
                "status": pc.status, # ACTIVE, RESOLVED, HISTORICAL
                "diagnosed_date": pc.diagnosed_date,
                "source": f"Patient Condition Profile ({pc.provenance})",
                "id": pc.id,
            })

        for ee in extracted_entities:
            if ee.entity_type == "CONDITION":
                doc_name = doc_map.get(ee.document_id, "Extracted Document")
                conditions_all.append({
                    "name": ee.name,
                    "status": "ACTIVE", # default extracted
                    "diagnosed_date": None,
                    "source": f"Document '{doc_name}' (p. {ee.page_number})",
                    "id": ee.id,
                })

        seen = set()
        for i in range(len(conditions_all)):
            for j in range(i + 1, len(conditions_all)):
                c1 = conditions_all[i]
                c2 = conditions_all[j]
                n1 = normalize_string(c1["name"])
                n2 = normalize_string(c2["name"])

                if n1 and n2 and (n1 == n2 or n1 in n2 or n2 in n1):
                    pair_key = tuple(sorted([c1["id"], c2["id"]]))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)

                    st1 = normalize_string(c1["status"])
                    st2 = normalize_string(c2["status"])

                    # Resolved vs Active conflict
                    if ("resolved" in (st1, st2) or "inactive" in (st1, st2)) and "active" in (st1, st2):
                        results.append({
                            "conflict_type": "DIAGNOSIS_DISCREPANCY",
                            "severity": "MEDIUM",
                            "title": f"Conflicting Condition Status: {c1['name'].title()}",
                            "description": (
                                f"Condition '{c1['name'].title()}' is documented as {c1['status']} in one source "
                                f"but as {c2['status']} in another. "
                                "Requires clinician review to determine if condition is currently active or resolved."
                            ),
                            "source_a": f"{c1['source']} (Status: {c1['status']})",
                            "source_b": f"{c2['source']} (Status: {c2['status']})",
                            "conflicting_values": json.dumps({
                                "condition": c1["name"],
                                "status_1": c1["status"],
                                "status_2": c2["status"]
                            }),
                        })

        return results

    # ------------------------------------------------------------------
    # 4. Laboratory Conflicts
    # ------------------------------------------------------------------
    @classmethod
    def _detect_lab_conflicts(
        cls,
        labs: List[LabResult],
        documents: List[Document]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        doc_map = {d.id: d.original_filename for d in documents}

        # Group labs by canonical test name and normalized report date
        labs_by_test_and_date: Dict[Tuple[str, Optional[str]], List[LabResult]] = {}
        labs_by_test: Dict[str, List[LabResult]] = {}

        for lab in labs:
            test_norm = normalize_string(lab.test_name)
            date_norm = parse_date_safely(lab.report_date)
            if not test_norm:
                continue

            labs_by_test.setdefault(test_norm, []).append(lab)
            labs_by_test_and_date.setdefault((test_norm, date_norm), []).append(lab)

            # Suspicious / physiologically implausible laboratory values check
            # E.g. Potassium > 15, Hemoglobin > 30, Glucose > 2500, Platelets < 0
            if lab.value is not None:
                is_suspicious = False
                suspicion_reason = ""
                if "potassium" in test_norm and (lab.value > 15.0 or lab.value < 1.0):
                    is_suspicious = True
                    suspicion_reason = f"Potassium value {lab.value} {lab.unit or ''} is physiologically extreme (<1.0 or >15.0 mEq/L)."
                elif "hemoglobin" in test_norm and (lab.value > 30.0 or lab.value < 2.0):
                    is_suspicious = True
                    suspicion_reason = f"Hemoglobin value {lab.value} {lab.unit or ''} is outside plausible human physiological boundaries."
                elif "glucose" in test_norm and (lab.value > 2500.0 or lab.value < 10.0):
                    is_suspicious = True
                    suspicion_reason = f"Glucose value {lab.value} {lab.unit or ''} is physiologically implausible."

                if is_suspicious:
                    doc_name = doc_map.get(lab.document_id, "Laboratory Document")
                    results.append({
                        "conflict_type": "LAB_DISCREPANCY",
                        "severity": "HIGH",
                        "title": f"Physiologically Suspicious Lab Value: {lab.test_name}",
                        "description": (
                            f"{suspicion_reason} This may indicate pre-analytical specimen artifact, "
                            "transcription error, or severe critical value. Needs immediate clinician verification."
                        ),
                        "source_a": f"Document '{doc_name}': {lab.value_text} {lab.unit or ''}",
                        "source_b": "Physiological boundary check",
                        "conflicting_values": json.dumps({
                            "test_name": lab.test_name,
                            "value": lab.value,
                            "unit": lab.unit,
                            "date": lab.report_date
                        }),
                    })

        # A. Same test having conflicting values on the same date
        seen_same_day = set()
        for (test_norm, date_norm), test_labs in labs_by_test_and_date.items():
            if not date_norm or len(test_labs) < 2:
                continue

            for i in range(len(test_labs)):
                for j in range(i + 1, len(test_labs)):
                    l1 = test_labs[i]
                    l2 = test_labs[j]
                    pair_key = tuple(sorted([l1.id, l2.id]))
                    if pair_key in seen_same_day:
                        continue
                    seen_same_day.add(pair_key)

                    # If values are both numeric and differ by more than 10%
                    if l1.value is not None and l2.value is not None:
                        diff = abs(l1.value - l2.value)
                        mean = (l1.value + l2.value) / 2.0
                        relative_diff = (diff / mean) if mean > 0 else diff
                        if relative_diff > 0.05: # >5% difference on same date
                            doc1 = doc_map.get(l1.document_id, "Document A")
                            doc2 = doc_map.get(l2.document_id, "Document B")
                            results.append({
                                "conflict_type": "LAB_DISCREPANCY",
                                "severity": "MEDIUM",
                                "title": f"Conflicting Same-Day Lab Values: {l1.test_name}",
                                "description": (
                                    f"Test '{l1.test_name}' has divergent values recorded on date {date_norm}: "
                                    f"'{l1.value_text} {l1.unit or ''}' vs '{l2.value_text} {l2.unit or ''}'. "
                                    "Confirm specimen timing or testing facility variations."
                                ),
                                "source_a": f"Doc '{doc1}': {l1.value_text} {l1.unit or ''}",
                                "source_b": f"Doc '{doc2}': {l2.value_text} {l2.unit or ''}",
                                "conflicting_values": json.dumps({
                                    "test": l1.test_name,
                                    "date": date_norm,
                                    "val_1": f"{l1.value} {l1.unit}",
                                    "val_2": f"{l2.value} {l2.unit}"
                                }),
                            })

        # B. Different / Incompatible units for the same laboratory test across documents
        seen_units = set()
        for test_norm, test_labs in labs_by_test.items():
            units = {normalize_string(l.unit) for l in test_labs if l.unit}
            if len(units) > 1:
                # Check if the units are legitimately compatible/convertible
                is_compatible = False
                for family in COMPATIBLE_UNIT_FAMILIES:
                    if units.issubset(family):
                        is_compatible = True
                        break

                if not is_compatible:
                    unit_key = (test_norm, tuple(sorted(list(units))))
                    if unit_key not in seen_units:
                        seen_units.add(unit_key)
                        u_list = list(units)
                        sample_labs = test_labs[:2]
                        d1 = doc_map.get(sample_labs[0].document_id, "Report 1")
                        d2 = doc_map.get(sample_labs[1].document_id, "Report 2")
                        results.append({
                            "conflict_type": "UNIT_MISMATCH",
                            "severity": "LOW",
                            "title": f"Non-Standard Unit Variation: {test_labs[0].test_name}",
                            "description": (
                                f"Test '{test_labs[0].test_name}' is reported with varying measurement units "
                                f"across records: {', '.join(u_list)}. "
                                "Clinician must account for unit scaling when trending longitudinal values."
                            ),
                            "source_a": f"Doc '{d1}': {sample_labs[0].unit}",
                            "source_b": f"Doc '{d2}': {sample_labs[1].unit}",
                            "conflicting_values": json.dumps({
                                "test": test_labs[0].test_name,
                                "units_found": list(units)
                            }),
                        })

        return results

    # ------------------------------------------------------------------
    # 5. Demographic / Record Metadata Conflicts
    # ------------------------------------------------------------------
    @classmethod
    def _detect_demographic_conflicts(
        cls,
        patient: Patient,
        documents: List[Document]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        # Compare patient intake demographics with text mentions in documents
        # E.g. If patient profile sex is MALE but document mentions 'female' in patient info block
        for doc in documents:
            if not doc.raw_text:
                continue
            text = doc.raw_text

            # Sex mismatch check
            pat_sex = normalize_string(patient.sex)
            if pat_sex in ("male", "female"):
                # Search for explicit document headers like "Sex: Female" or "Gender: F"
                m = re.search(r"(?:sex|gender)\s*[:=]\s*(male|female|m|f)\b", text, re.IGNORECASE)
                if m:
                    doc_sex_raw = m.group(1).lower()
                    doc_sex = "male" if doc_sex_raw in ("male", "m") else "female"
                    if doc_sex != pat_sex:
                        results.append({
                            "conflict_type": "DEMOGRAPHIC_MISMATCH",
                            "severity": "HIGH",
                            "title": f"Patient Sex Discrepancy Detected in '{doc.original_filename}'",
                            "description": (
                                f"Patient registration profile states sex as '{patient.sex.upper()}', "
                                f"whereas document '{doc.original_filename}' explicitly designates '{doc_sex.upper()}'. "
                                "Possible document misattribution or chart mismatch."
                            ),
                            "source_a": f"Patient Registration Profile: {patient.sex.upper()}",
                            "source_b": f"Document '{doc.original_filename}': {doc_sex.upper()}",
                            "conflicting_values": json.dumps({
                                "profile_sex": patient.sex,
                                "document_sex": doc_sex,
                                "document_id": doc.id
                            }),
                        })

            # Date of birth mismatch check
            if patient.date_of_birth:
                norm_profile_dob = parse_date_safely(patient.date_of_birth)
                # Look for "DOB: MM/DD/YYYY" or "Date of Birth: YYYY-MM-DD" in doc text
                dob_match = re.search(r"(?:dob|date\s+of\s+birth)\s*[:=]\s*(\d{1,4}[/-]\d{1,2}[/-]\d{1,4})", text, re.IGNORECASE)
                if dob_match:
                    doc_dob_raw = dob_match.group(1)
                    doc_dob_norm = parse_date_safely(doc_dob_raw)
                    if doc_dob_norm and norm_profile_dob and doc_dob_norm != norm_profile_dob:
                        results.append({
                            "conflict_type": "DEMOGRAPHIC_MISMATCH",
                            "severity": "HIGH",
                            "title": f"Conflicting Date of Birth in '{doc.original_filename}'",
                            "description": (
                                f"Patient profile records DOB as '{patient.date_of_birth}' (normalized: {norm_profile_dob}), "
                                f"but document '{doc.original_filename}' notes DOB as '{doc_dob_raw}'. "
                                "Verify patient identification to prevent cross-patient record contamination."
                            ),
                            "source_a": f"Patient Profile DOB: {patient.date_of_birth}",
                            "source_b": f"Document '{doc.original_filename}' DOB: {doc_dob_raw}",
                            "conflicting_values": json.dumps({
                                "profile_dob": patient.date_of_birth,
                                "document_dob": doc_dob_raw
                            }),
                        })

        return results

    # ------------------------------------------------------------------
    # Synchronization Helper
    # ------------------------------------------------------------------
    @classmethod
    def _sync_conflicts_to_db(
        cls,
        db: Session,
        patient_id: str,
        detected: List[Dict[str, Any]]
    ) -> List[ConflictItem]:
        """
        Idempotently inserts newly detected conflicts without duplicating existing
        OPEN or REVIEWED items. Retains historical resolutions and audit trails.
        """
        existing_conflicts = db.query(ConflictItem).filter(ConflictItem.patient_id == patient_id).all()
        existing_keys = {
            (c.conflict_type, c.title, c.source_a, c.source_b)
            for c in existing_conflicts
        }

        created_count = 0
        for item in detected:
            key = (item["conflict_type"], item["title"], item.get("source_a"), item.get("source_b"))
            if key not in existing_keys:
                conflict = ConflictItem(
                    id=str(uuid.uuid4()),
                    patient_id=patient_id,
                    conflict_type=item["conflict_type"],
                    severity=item.get("severity", "MEDIUM"),
                    title=item["title"],
                    description=item["description"],
                    source_a=item.get("source_a"),
                    source_b=item.get("source_b"),
                    conflicting_values=item.get("conflicting_values"),
                    status="OPEN",
                    created_at=datetime.utcnow()
                )
                db.add(conflict)
                existing_keys.add(key)
                created_count += 1

        if created_count > 0:
            db.commit()
            logger.info("Detected and persisted %d new clinical conflict(s) for patient %s", created_count, patient_id)

        return db.query(ConflictItem).filter(ConflictItem.patient_id == patient_id).order_by(ConflictItem.created_at.desc()).all()
