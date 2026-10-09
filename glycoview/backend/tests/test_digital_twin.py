from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_twin_replay():
    response = client.get("/api/v1/twin/replay")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "timeline" in data
    assert "metrics" in data

def test_twin_simulate_scenario():
    response = client.post("/api/v1/twin/simulate-scenario", json={
        "bolus_delta_u": 1.0,
        "carbs_delta_g": 20.0,
        "basal_multiplier": 1.1
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "timeline" in data
    assert "disclaimer" in data

def test_twin_settings_analysis():
    response = client.get("/api/v1/twin/settings-analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "blocks" in data
    assert len(data["blocks"]) == 8

def test_twin_meals():
    response = client.get("/api/v1/twin/meals")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "meals" in data

def test_twin_validation_report():
    response = client.get("/api/v1/twin/validation-report")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "validation_metrics" in data
