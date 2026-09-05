import io
import csv
import json
from datetime import datetime
from typing import Dict, Any
from app.models.patient import Patient

class ExportService:
    @staticmethod
    def export_json(patient: Patient) -> Dict[str, Any]:
        """
        Exports the complete structured patient record as JSON with strict provenance metadata.
        """
        return {
            "export_metadata": {
                "system": "MedLens Clinical Information Intelligence",
                "version": "1.0.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "disclaimer": "MedLens is an information organization tool. It does not provide medical diagnosis or treatment recommendations."
            },
            "patient": {
                "mrn": patient.mrn,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "date_of_birth": patient.date_of_birth,
                "age": patient.age,
                "sex": patient.sex,
                "contact_phone": patient.contact_phone,
                "contact_email": patient.contact_email,
                "provenance": "USER_PROVIDED"
            },
            "conditions": [
                {
                    "name": c.condition_name,
                    "status": c.status,
                    "diagnosed_date": c.diagnosed_date,
                    "provenance": c.provenance
                } for c in patient.conditions
            ],
            "allergies": [
                {
                    "allergen": a.allergen,
                    "reaction": a.reaction,
                    "severity": a.severity,
                    "provenance": a.provenance
                } for a in patient.allergies
            ],
            "medications": [
                {
                    "medication_name": m.medication_name,
                    "dosage": m.dosage,
                    "frequency": m.frequency,
                    "route": m.route,
                    "provenance": m.provenance
                } for m in patient.medications
            ],
            "laboratory_results": [
                {
                    "test_name": r.test_name,
                    "value": r.value,
                    "value_text": r.value_text,
                    "unit": r.unit,
                    "reference_range": r.raw_reference_range,
                    "status": r.status,
                    "confidence": r.confidence,
                    "provenance": r.provenance,
                    "is_verified": r.is_verified,
                    "source_evidence": r.source_evidence,
                    "report_date": r.report_date
                } for r in patient.lab_results
            ],
            "active_conflicts": [
                {
                    "type": c.conflict_type,
                    "severity": c.severity,
                    "title": c.title,
                    "description": c.description,
                    "status": c.status
                } for c in patient.conflicts if c.status == "UNRESOLVED"
            ]
        }

    @staticmethod
    def export_csv_labs(patient: Patient) -> str:
        """
        Generates CSV format string of all laboratory results for the patient.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "MRN", "Patient Name", "Test Name", "Value", "Unit",
            "Reference Range", "Status", "Report Date", "Confidence", "Provenance", "Verified"
        ])

        full_name = f"{patient.first_name} {patient.last_name}"
        for r in patient.lab_results:
            writer.writerow([
                patient.mrn,
                full_name,
                r.test_name,
                r.value_text,
                r.unit or "",
                r.raw_reference_range or "Not Provided in Source",
                r.status,
                r.report_date or "",
                f"{round(r.confidence * 100, 1)}%",
                r.provenance,
                "YES" if r.is_verified else "NO"
            ])

        return output.getvalue()
