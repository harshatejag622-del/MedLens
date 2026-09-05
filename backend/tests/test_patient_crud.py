import pytest
from datetime import datetime, date

def test_patient_create_with_provenance_and_validation(client):
    """
    Test creating a new patient record with complete demographics,
    relevant history, clinical notes, and multi-sub-entity entries.
    Verifies that all manual clinical entries receive USER_PROVIDED provenance.
    """
    payload = {
        "mrn": "SYN-TEST-101",
        "first_name": "Elena",
        "last_name": "Rostova",
        "date_of_birth": "1988-03-24",
        "age": 38,
        "sex": "FEMALE",
        "contact_phone": "555-0324",
        "contact_email": "elena.rostova@example.org",
        "relevant_history": "Paternal history of myocardial infarction at age 48. Previous appendectomy.",
        "notes": "Patient seeking baseline cardiovascular and metabolic risk assessment.",
        "is_synthetic_demo": True,
        "is_archived": False,
        "conditions": [
            {
                "condition_name": "Mild Hyperlipidemia",
                "status": "ACTIVE",
                "diagnosed_date": "2022-01-10",
                "notes": "Dietary management advised"
            }
        ],
        "allergies": [
            {
                "allergen": "Ciprofloxacin",
                "reaction": "Tendon discomfort",
                "severity": "MODERATE"
            }
        ],
        "medications": [
            {
                "medication_name": "CoQ10",
                "dosage": "100 mg",
                "frequency": "Once daily",
                "route": "ORAL"
            }
        ],
        "symptoms": [
            {
                "symptom": "Occasional palpitations",
                "duration": "1 month",
                "severity": "MILD"
            }
        ]
    }

    res = client.post("/api/patients", json=payload)
    assert res.status_code == 201
    data = res.json()

    # Core demographic validation
    assert data["mrn"] == "SYN-TEST-101"
    assert data["first_name"] == "Elena"
    assert data["last_name"] == "Rostova"
    assert data["date_of_birth"] == "1988-03-24"
    assert data["age"] == 38
    assert data["sex"] == "FEMALE"
    assert data["relevant_history"] == "Paternal history of myocardial infarction at age 48. Previous appendectomy."
    assert data["notes"] == "Patient seeking baseline cardiovascular and metabolic risk assessment."
    assert data["is_archived"] is False

    # Provenance enforcement check on every manually created clinical sub-entity
    assert len(data["conditions"]) == 1
    assert data["conditions"][0]["condition_name"] == "Mild Hyperlipidemia"
    assert data["conditions"][0]["provenance"] == "USER_PROVIDED"

    assert len(data["allergies"]) == 1
    assert data["allergies"][0]["allergen"] == "Ciprofloxacin"
    assert data["allergies"][0]["provenance"] == "USER_PROVIDED"

    assert len(data["medications"]) == 1
    assert data["medications"][0]["medication_name"] == "CoQ10"
    assert data["medications"][0]["provenance"] == "USER_PROVIDED"

    assert len(data["symptoms"]) == 1
    assert data["symptoms"][0]["symptom"] == "Occasional palpitations"
    assert data["symptoms"][0]["provenance"] == "USER_PROVIDED"


def test_patient_validation_failures(client):
    """
    Test validation rejections on invalid patient fields.
    """
    # 1. Invalid date of birth format
    bad_dob_payload = {
        "mrn": "SYN-BAD-01",
        "first_name": "Bad",
        "last_name": "Date",
        "date_of_birth": "05/15/1990", # Not YYYY-MM-DD
        "age": 36,
        "sex": "FEMALE"
    }
    res = client.post("/api/patients", json=bad_dob_payload)
    assert res.status_code == 422

    # 2. Future date of birth
    future_dob_payload = {
        "mrn": "SYN-BAD-02",
        "first_name": "Future",
        "last_name": "Person",
        "date_of_birth": "2099-01-01",
        "age": 10,
        "sex": "MALE"
    }
    res = client.post("/api/patients", json=future_dob_payload)
    assert res.status_code == 422

    # 3. Invalid sex enum
    bad_sex_payload = {
        "mrn": "SYN-BAD-03",
        "first_name": "Bad",
        "last_name": "Sex",
        "date_of_birth": "1990-01-01",
        "age": 36,
        "sex": "INVALID_SEX"
    }
    res = client.post("/api/patients", json=bad_sex_payload)
    assert res.status_code == 422

    # 4. Duplicate MRN rejection
    dupe_payload = {
        "mrn": "SYN-1001", # Alex Morgan's existing MRN
        "first_name": "Duplicate",
        "last_name": "MRN",
        "date_of_birth": "1980-01-01",
        "age": 46,
        "sex": "FEMALE"
    }
    res = client.post("/api/patients", json=dupe_payload)
    assert res.status_code == 409


def test_patient_overview_endpoint(client):
    """
    Test comprehensive patient overview endpoint containing:
    Header, Demographics, Symptoms, Conditions, Allergies, Medications,
    Reports, Laboratory Results, Timeline, Conflicts, and Summaries.
    """
    # Get Alex Morgan
    res = client.get("/api/patients")
    alex = next(p for p in res.json() if p["mrn"] == "SYN-1001")

    overview_res = client.get(f"/api/patients/{alex['id']}")
    assert overview_res.status_code == 200
    overview = overview_res.json()

    # 1. Header & Demographics
    assert overview["mrn"] == "SYN-1001"
    assert overview["first_name"] == "Alex"
    assert overview["last_name"] == "Morgan"
    assert overview["date_of_birth"] == "1981-04-12"
    assert overview["age"] == 45
    assert overview["sex"] == "FEMALE"
    assert "CAD" in overview["relevant_history"]

    # 2. Symptoms
    assert len(overview["symptoms"]) >= 1
    assert overview["symptoms"][0]["provenance"] == "USER_PROVIDED"

    # 3. Conditions
    assert len(overview["conditions"]) >= 1
    assert any("Hypertension" in c["condition_name"] for c in overview["conditions"])

    # 4. Allergies
    assert len(overview["allergies"]) >= 1
    assert any("Penicillin" in a["allergen"] for a in overview["allergies"])

    # 5. Medications
    assert len(overview["medications"]) >= 1
    assert any("Lisinopril" in m["medication_name"] for m in overview["medications"])

    # 6. Reports / Documents
    assert len(overview["documents"]) >= 1
    doc = overview["documents"][0]
    assert doc["filename"] is not None
    assert doc["sha256_checksum"] is not None

    # 7. Laboratory results
    assert len(overview["lab_results"]) >= 1
    lab = overview["lab_results"][0]
    assert lab["test_name"] is not None
    assert lab["flag"] in ["LOW", "NORMAL", "HIGH", "UNKNOWN"]

    # 8. Conflicts
    assert len(overview["conflicts"]) >= 1
    conflict = overview["conflicts"][0]
    assert conflict["conflict_type"] is not None
    assert conflict["severity"] in ["INFO", "WARNING", "HIGH"]

    # 9. Summary
    assert len(overview["summaries"]) >= 1
    summary = overview["summaries"][0]
    assert len(summary["content"]) > 10

    # 10. Timeline (Chronologically synthesized)
    assert len(overview["timeline"]) >= 5
    # Verify timeline items are sorted descending by date
    dates = [t["date"] for t in overview["timeline"]]
    assert dates == sorted(dates, reverse=True)


def test_patient_edit_update(client):
    """
    Test editing patient demographics, relevant history, and clinical profile.
    Verifies that updated clinical items maintain USER_PROVIDED provenance.
    """
    # Create patient
    create_payload = {
        "mrn": "SYN-EDIT-01",
        "first_name": "Jordan",
        "last_name": "Original",
        "date_of_birth": "1994-06-10",
        "age": 32,
        "sex": "MALE",
        "relevant_history": "Original history",
        "notes": "Original notes",
        "conditions": [{"condition_name": "Mild Asthma", "status": "ACTIVE"}],
        "allergies": [],
        "medications": [],
        "symptoms": []
    }
    c_res = client.post("/api/patients", json=create_payload)
    assert c_res.status_code == 201
    patient_id = c_res.json()["id"]

    # Update patient demographics and add new allergy + med
    update_payload = {
        "last_name": "Updated",
        "age": 33,
        "relevant_history": "Updated clinical history with family details.",
        "notes": "Updated clinician notes.",
        "allergies": [
            {"allergen": "Sulfa", "reaction": "Hives", "severity": "MODERATE"}
        ],
        "medications": [
            {"medication_name": "Albuterol", "dosage": "90mcg", "frequency": "PRN"}
        ]
    }
    u_res = client.put(f"/api/patients/{patient_id}", json=update_payload)
    assert u_res.status_code == 200
    updated = u_res.json()

    assert updated["last_name"] == "Updated"
    assert updated["age"] == 33
    assert updated["relevant_history"] == "Updated clinical history with family details."
    assert updated["notes"] == "Updated clinician notes."
    assert len(updated["allergies"]) == 1
    assert updated["allergies"][0]["allergen"] == "Sulfa"
    assert updated["allergies"][0]["provenance"] == "USER_PROVIDED"


def test_patient_archive_and_unarchive(client):
    """
    Test archiving and unarchiving patient records.
    Verifies that archived records are excluded from default search unless include_archived=True.
    """
    # Create patient
    create_payload = {
        "mrn": "SYN-ARCHIVE-01",
        "first_name": "Archivable",
        "last_name": "Person",
        "date_of_birth": "1975-01-01",
        "age": 51,
        "sex": "MALE"
    }
    c_res = client.post("/api/patients", json=create_payload)
    assert c_res.status_code == 201
    patient_id = c_res.json()["id"]

    # Archive patient
    arch_res = client.post(f"/api/patients/{patient_id}/archive")
    assert arch_res.status_code == 200
    assert arch_res.json()["is_archived"] is True

    # Check default list_patients: should NOT include archived patient
    list_res = client.get("/api/patients")
    assert list_res.status_code == 200
    active_mrns = [p["mrn"] for p in list_res.json()]
    assert "SYN-ARCHIVE-01" not in active_mrns

    # Query with include_archived=True: should include archived patient
    list_arch_res = client.get("/api/patients?include_archived=true")
    assert list_arch_res.status_code == 200
    all_mrns = [p["mrn"] for p in list_arch_res.json()]
    assert "SYN-ARCHIVE-01" in all_mrns

    # Unarchive patient
    unarch_res = client.post(f"/api/patients/{patient_id}/unarchive")
    assert unarch_res.status_code == 200
    assert unarch_res.json()["is_archived"] is False

    # Now default list_patients includes it
    list_after = client.get("/api/patients")
    assert "SYN-ARCHIVE-01" in [p["mrn"] for p in list_after.json()]


def test_patient_search_and_filter(client):
    """
    Test searching by keyword and multi-criteria filtering by sex and age.
    """
    # Search by MRN
    res_mrn = client.get("/api/patients?search=SYN-1001")
    assert res_mrn.status_code == 200
    assert len(res_mrn.json()) == 1
    assert res_mrn.json()[0]["first_name"] == "Alex"

    # Search by Name
    res_name = client.get("/api/patients?search=Jordan")
    assert res_name.status_code == 200
    assert any(p["first_name"] == "Jordan" for p in res_name.json())

    # Filter by Sex
    res_sex = client.get("/api/patients?sex=FEMALE")
    assert res_sex.status_code == 200
    for p in res_sex.json():
        assert p["sex"] == "FEMALE"

    # Filter by Age Range
    res_age = client.get("/api/patients?age_min=50&age_max=70")
    assert res_age.status_code == 200
    for p in res_age.json():
        assert 50 <= p["age"] <= 70


def test_patient_delete_cascade(client):
    """
    Test deleting a patient and verifying cascade deletion of all child records.
    """
    # Create patient with clinical items
    create_payload = {
        "mrn": "SYN-DEL-01",
        "first_name": "Deletable",
        "last_name": "Test",
        "date_of_birth": "1999-12-12",
        "age": 27,
        "sex": "OTHER",
        "conditions": [{"condition_name": "Temporary Condition", "status": "ACTIVE"}],
        "allergies": [{"allergen": "Dust mites", "reaction": "Sneezing", "severity": "MILD"}]
    }
    c_res = client.post("/api/patients", json=create_payload)
    assert c_res.status_code == 201
    patient_id = c_res.json()["id"]

    # Verify patient exists
    assert client.get(f"/api/patients/{patient_id}").status_code == 200

    # Delete patient
    del_res = client.delete(f"/api/patients/{patient_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify patient record no longer exists
    assert client.get(f"/api/patients/{patient_id}").status_code == 404
