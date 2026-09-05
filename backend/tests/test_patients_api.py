def test_list_synthetic_patients(client):
    response = client.get("/api/patients")
    assert response.status_code == 200
    patients = response.json()
    assert len(patients) >= 3
    mrns = [p["mrn"] for p in patients]
    assert "SYN-1001" in mrns # Alex Morgan

def test_get_alex_morgan_details(client):
    response = client.get("/api/patients")
    alex = next(p for p in response.json() if p["mrn"] == "SYN-1001")
    
    detail_res = client.get(f"/api/patients/{alex['id']}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["first_name"] == "Alex"
    assert data["last_name"] == "Morgan"
    assert len(data["allergies"]) >= 1
    assert any("Penicillin" in a["allergen"] for a in data["allergies"])

def test_create_new_patient_intake(client):
    new_patient_data = {
        "mrn": "SYN-9999",
        "first_name": "Casey",
        "last_name": "Rivera",
        "date_of_birth": "1990-05-15",
        "age": 36,
        "sex": "FEMALE",
        "contact_phone": "555-9012",
        "contact_email": "casey.rivera.synthetic@example.org",
        "notes": "SYNTHETIC TEST INTAKE",
        "is_synthetic_demo": True,
        "conditions": [
            {"condition_name": "Asthma", "status": "ACTIVE", "diagnosed_date": "2015-06-20"}
        ],
        "allergies": [
            {"allergen": "Latex", "reaction": "Contact dermatitis", "severity": "MILD"}
        ],
        "medications": [
            {"medication_name": "Albuterol inhaler", "dosage": "90 mcg", "frequency": "As needed"}
        ],
        "symptoms": []
    }

    create_res = client.post("/api/patients", json=new_patient_data)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["mrn"] == "SYN-9999"
    assert len(created["conditions"]) == 1
    assert created["conditions"][0]["provenance"] == "USER_PROVIDED"

def test_operational_stats(client):
    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_patients"] >= 3
    assert stats["demo_mode"] is True
