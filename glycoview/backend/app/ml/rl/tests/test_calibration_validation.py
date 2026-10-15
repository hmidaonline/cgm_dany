import pytest
import pandas as pd
import numpy as np
from app.ml.rl.calibration.calibrator import PhysiologicalCalibrator
from app.ml.rl.calibration.validator import DigitalTwinValidator
from app.ml.rl.calibration.clean_events import extract_clean_fasting_events, extract_clean_meal_events

@pytest.fixture
def synthetic_history():
    """Generates synthetic 5-min dataset for calibration and validation testing."""
    n = 300
    times = pd.date_range("2026-10-01", periods=n, freq="5min")
    sgv = 110.0 + 20.0 * np.sin(np.linspace(0, 4 * np.pi, n)) + np.random.normal(0, 3, n)
    carbs = [0.0] * n
    bolus = [0.0] * n
    # Add a meal at step 50
    carbs[50] = 45.0
    bolus[50] = 4.5
    # Add another meal at step 150
    carbs[150] = 30.0
    bolus[150] = 3.0

    return pd.DataFrame({
        "datetime": times,
        "sgv": np.clip(sgv, 60, 250),
        "carbs": carbs,
        "bolus": bolus,
        "iob": np.clip(0.5 + 0.3 * np.cos(np.linspace(0, 4 * np.pi, n)), 0, 4),
        "cob": [10.0 if 50 <= i < 80 else 0.0 for i in range(n)],
        "basal": 0.85
    })

def test_event_extraction(synthetic_history):
    fasting = extract_clean_fasting_events(synthetic_history)
    meals = extract_clean_meal_events(synthetic_history)
    assert isinstance(fasting, list)
    assert isinstance(meals, list)
    assert len(meals) >= 1

def test_calibrator_and_validator(synthetic_history):
    calibrator = PhysiologicalCalibrator()
    calib = calibrator.calibrate(synthetic_history, n_bootstraps=50)

    assert "isf_by_block" in calib
    assert "cr_by_block" in calib
    assert "diagnostics" in calib
    assert "isf_base" in calib["diagnostics"]

    validator = DigitalTwinValidator(calibrated_params=calib)
    val = validator.validate(synthetic_history, synthetic_history, horizons_steps={"30min": 6})

    assert "horizons" in val
    assert "30min" in val["horizons"]
    assert "clarke" in val["horizons"]["30min"]["hybrid"]
    assert val["horizons"]["30min"]["hybrid"]["clarke"]["zone_ab"] >= 70.0
