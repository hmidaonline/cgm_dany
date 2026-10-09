from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "glycoview-backend"}

def test_read_entries():
    response = client.get("/api/v1/entries/raw?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "_id" in data[0]
        assert "type" in data[0]

def test_processed_entries():
    response = client.get("/api/v1/entries/processed")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "datetime" in data[0]
        assert "sgv" in data[0]
