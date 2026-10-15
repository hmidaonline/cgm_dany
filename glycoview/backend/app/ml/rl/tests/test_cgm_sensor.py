import pytest
import numpy as np
from app.ml.rl.simulator.cgm_sensor import CGMSensorModel
from app.ml.rl.config import CGMSensorConfig

def test_cgm_sensor_delay_and_noise():
    config = CGMSensorConfig(lag_time_minutes=10.0, sensor_noise_std=3.0, dropout_probability=0.0, compression_low_prob=0.0)
    sensor = CGMSensorModel(config=config, seed=42)
    sensor.reset(initial_blood_glucose=100.0)

    # Step at constant blood glucose
    readings = []
    for _ in range(20):
        val, diag = sensor.step(blood_glucose=100.0, hour_of_day=14.0)
        assert val is not None
        readings.append(val)

    # Readings should fluctuate around 100 with noise std ~ 3
    mean_val = float(np.mean(readings))
    assert 95.0 <= mean_val <= 105.0

def test_cgm_sensor_compression_low():
    config = CGMSensorConfig(lag_time_minutes=5.0, sensor_noise_std=1.0, dropout_probability=0.0, compression_low_prob=1.0)
    sensor = CGMSensorModel(config=config, seed=42)
    sensor.reset(initial_blood_glucose=120.0)

    # Trigger at night (hour 2.0)
    val, diag = sensor.step(blood_glucose=120.0, hour_of_day=2.0)
    assert diag["is_compression"] is True
    assert diag["compression_drop"] > 20.0
    assert val < 105.0 # Noticeable drop

def test_cgm_sensor_dropout():
    config = CGMSensorConfig(dropout_probability=1.0, dropout_max_duration_steps=2)
    sensor = CGMSensorModel(config=config, seed=42)
    sensor.reset(initial_blood_glucose=120.0)

    val, diag = sensor.step(blood_glucose=120.0, hour_of_day=12.0)
    assert val is None
    assert diag["is_dropout"] is True
