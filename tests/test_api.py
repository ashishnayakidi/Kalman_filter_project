"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_tick():
    """Test tick endpoint."""
    response = client.post(
        "/ekf/tick",
        json={"I_A": 1.2, "V_V": 3.9, "T_C": 25.0, "dt_s": 1.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert "soc" in data
    assert "v_pred" in data
    assert 0.0 <= data["soc"] <= 1.0


def test_state():
    """Test state endpoint."""
    # First process a tick
    client.post("/ekf/tick", json={"I_A": 1.0, "V_V": 3.8, "T_C": 25.0, "dt_s": 1.0})
    
    response = client.get("/ekf/state")
    assert response.status_code == 200
    data = response.json()
    assert "soc" in data
    assert "params" in data

