from typing import List, Dict, Any

SYNTHETIC_PATIENTS: List[Dict[str, Any]] = [
    {
        "mrn": "SYN-1001",
        "first_name": "Alex",
        "last_name": "Morgan",
        "date_of_birth": "1981-04-12",
        "age": 45,
        "sex": "FEMALE",
        "contact_phone": "555-0192",
        "contact_email": "alex.morgan.synthetic@example.org",
        "relevant_history": "Family history of early onset CAD (father, age 52). Prior laparoscopic cholecystectomy in 2017 without surgical complications. Non-smoker, drinks socially.",
        "notes": "SYNTHETIC DEMO RECORD: Primary evaluation case for MedLens clinical intelligence platform.",
        "is_synthetic_demo": True,
        "conditions": [
            {"condition_name": "Essential Hypertension", "status": "ACTIVE", "diagnosed_date": "2021-03-15", "notes": "Managed with Lisinopril"},
            {"condition_name": "Iron Deficiency (Historical)", "status": "HISTORICAL", "diagnosed_date": "2023-08-10", "notes": "Monitored via routine CBC"}
        ],
        "allergies": [
            {"allergen": "Penicillin", "reaction": "Diffuse Urticaria & Wheezing", "severity": "SEVERE"}
        ],
        "medications": [
            {"medication_name": "Lisinopril", "dosage": "10 mg", "frequency": "Once daily", "route": "ORAL"},
            {"medication_name": "Cholecalciferol (Vitamin D3)", "dosage": "2000 IU", "frequency": "Once daily", "route": "ORAL"}
        ],
        "symptoms": [
            {"symptom": "Fatigue upon exertion", "duration": "3 weeks", "severity": "MILD"}
        ]
    },
    {
        "mrn": "SYN-1002",
        "first_name": "Jordan",
        "last_name": "Lee",
        "date_of_birth": "1964-11-28",
        "age": 61,
        "sex": "MALE",
        "contact_phone": "555-0144",
        "contact_email": "jordan.lee.synthetic@example.org",
        "relevant_history": "Maternal history of Type 2 Diabetes and CKD. Prior appendectomy in 1989. Former smoker (quit 2012, 15 pack-year history).",
        "notes": "SYNTHETIC DEMO RECORD: Multi-condition metabolic profile.",
        "is_synthetic_demo": True,
        "conditions": [
            {"condition_name": "Type 2 Diabetes Mellitus", "status": "ACTIVE", "diagnosed_date": "2018-05-19", "notes": "Glycemic control with Metformin"}
        ],
        "allergies": [
            {"allergen": "Sulfa drugs", "reaction": "Maculopapular rash", "severity": "MODERATE"}
        ],
        "medications": [
            {"medication_name": "Metformin", "dosage": "500 mg", "frequency": "Twice daily with meals", "route": "ORAL"},
            {"medication_name": "Atorvastatin", "dosage": "20 mg", "frequency": "Once daily at bedtime", "route": "ORAL"}
        ],
        "symptoms": [
            {"symptom": "Mild peripheral tingling", "duration": "2 months", "severity": "MILD"}
        ]
    },
    {
        "mrn": "SYN-1003",
        "first_name": "Taylor",
        "last_name": "Kim",
        "date_of_birth": "1997-02-14",
        "age": 29,
        "sex": "OTHER",
        "contact_phone": "555-0188",
        "contact_email": "taylor.kim.synthetic@example.org",
        "relevant_history": "Childhood atopic dermatitis and mild reactive airway. No prior surgical interventions. Non-smoker.",
        "notes": "SYNTHETIC DEMO RECORD: Young adult preventive baseline record.",
        "is_synthetic_demo": True,
        "conditions": [
            {"condition_name": "Allergic Rhinitis", "status": "ACTIVE", "diagnosed_date": "2020-04-01", "notes": "Seasonal tree pollen trigger"}
        ],
        "allergies": [
            {"allergen": "NSAIDs", "reaction": "Facial Angioedema", "severity": "SEVERE"}
        ],
        "medications": [
            {"medication_name": "Cetirizine", "dosage": "10 mg", "frequency": "As needed for allergies", "route": "ORAL"}
        ],
        "symptoms": [
            {"symptom": "Nasal congestion", "duration": "1 week", "severity": "MILD"}
        ]
    }
]
