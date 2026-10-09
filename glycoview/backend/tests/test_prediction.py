from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)

def test_prediction_status():
    response = client.get("/api/v1/prediction/status")
    assert response.status_code == 200
    data = response.json()
    assert "lightgbm" in data
    assert "deep_learning" in data
    assert "baselines" in data

def test_prediction_predict_lightgbm():
    response = client.get("/api/v1/prediction/predict?model_type=lightgbm&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["model_type"] == "lightgbm"
    assert "historical" in data
    assert "future_trajectory" in data
    assert len(data["future_trajectory"]) > 0
    # Check intermediate points in future trajectory
    p0 = data["future_trajectory"][0]
    assert "p50" in p0
    assert "p10" in p0
    assert "p90" in p0

def test_prediction_predict_deep():
    response = client.get("/api/v1/prediction/predict?model_type=deep&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["model_type"] == "deep"

def test_prediction_evaluate():
    response = client.get("/api/v1/prediction/evaluate")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "models" in data
    assert "lightgbm" in data["models"]
    assert "deep" in data["models"]
    assert "persistence" in data["models"]

def test_prediction_simulate():
    response = client.post("/api/v1/prediction/simulate", json={
        "bolus_u": 2.0,
        "carbs_g": 30.0,
        "sensitivity_factor": 0.8,
        "model_type": "lightgbm"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "baseline_trajectory" in data
    assert "simulated_trajectory" in data
    assert "impact_summary" in data
    assert "min_projected_sgv" in data["impact_summary"]

