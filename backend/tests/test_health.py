def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data

def test_readiness_check_endpoint(client):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert "disclaimer" in data
