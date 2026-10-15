import pytest
from app.ml.rl.env.safety_shield import SafetyShield

def test_shield_low_glucose_suspend():
    shield = SafetyShield()
    # Glucose < 80 -> Must suspend basal (safe_action = 0.0)
    safe_mult, audit = shield.filter_action(
        proposed_action_mult=2.0,
        cgm_reading=75.0,
        velocity_15=0.0,
        controller_iob=1.0
    )
    assert safe_mult == 0.0
    assert audit.triggered is True
    assert audit.reason == "LOW_GLUCOSE_SUSPEND"

def test_shield_predictive_low_suspend():
    shield = SafetyShield()
    # Glucose 90, dropping at -1.5 mg/dL/min -> projected at 30 min is 90 - 45 = 45 < 70 -> Must suspend
    safe_mult, audit = shield.filter_action(
        proposed_action_mult=1.5,
        cgm_reading=90.0,
        velocity_15=-1.5,
        controller_iob=1.0
    )
    assert safe_mult == 0.0
    assert audit.triggered is True
    assert audit.reason == "PREDICTIVE_LOW_SUSPEND"

def test_shield_iob_cap():
    shield = SafetyShield()
    # IOB = 8.0 > max_iob_cap (7.0) -> Multiplier > 1.0 must be throttled to 1.0
    safe_mult, audit = shield.filter_action(
        proposed_action_mult=2.5,
        cgm_reading=140.0,
        velocity_15=0.0,
        controller_iob=8.0
    )
    assert safe_mult == 1.0
    assert audit.triggered is True
    assert audit.reason == "IOB_CAP_EXCEEDED"

def test_shield_normal_passthrough():
    shield = SafetyShield()
    # Normal safe state (CGM = 130, IOB = 1.5, velocity = 0)
    safe_mult, audit = shield.filter_action(
        proposed_action_mult=1.8,
        cgm_reading=130.0,
        velocity_15=0.0,
        controller_iob=1.5
    )
    assert safe_mult == 1.8
    assert audit.triggered is False
    assert audit.reason == "NONE"
