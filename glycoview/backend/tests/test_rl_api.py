import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_rl_benchmarks_endpoint():
    response = client.get("/api/rl/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert "phase4" in data
    assert "banc_a_residual_results" in data["phase4"]
    assert "Residual_PPO_WithShield" in data["phase4"]["banc_a_residual_results"]
    assert "wilcoxon_vs_oref0" in data["phase4"]

def test_rl_shadow_audit_endpoint():
    payload = {"date": "2026-10-12"}
    response = client.post("/api/rl/shadow-audit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-10-12"
    assert "summary" in data
    assert "mean_cgm" in data["summary"]
    assert "steps" in data
    assert len(data["steps"]) > 0
    step0 = data["steps"][0]
    assert "cgm" in step0
    assert "aaps_basal_rate" in step0
    assert "oref0_basal_rate" in step0
    assert "residual_ppo_basal_rate" in step0
    assert "shield_triggered" in step0

def test_rl_counterfactual_sim_endpoint():
    payload = {
        "scenario_type": "high_fat",
        "seed": 1042
    }
    response = client.post("/api/rl/counterfactual-sim", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["scenario"] == "high_fat_meal"
    assert data["seed"] == 1042
    assert "comparison_table" in data
    assert len(data["comparison_table"]) == 4
    
    ctrl_ids = [c["controller_id"] for c in data["comparison_table"]]
    assert "open_loop" in ctrl_ids
    assert "pid_shield" in ctrl_ids
    assert "oref0_shield" in ctrl_ids
    assert "residual_ppo_shield" in ctrl_ids

    assert "time_series" in data
    assert "residual_ppo_shield" in data["time_series"]
    assert len(data["time_series"]["residual_ppo_shield"]) == 288
