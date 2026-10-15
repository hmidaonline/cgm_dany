import pytest
import numpy as np
from app.ml.rl.simulator.virtual_patient import VirtualPatient

def test_virtual_patient_meal_bolus_dynamics():
    patient = VirtualPatient(seed=42)
    patient.reset(start_bg=100.0)

    # 1. Administer a 50g meal with no bolus -> Glucose should rise significantly
    bg_after_meal = 100.0
    for step in range(12): # 1 hour
        c = 50.0 if step == 0 else 0.0
        bg, diag = patient.step(hour_of_day=12.0 + step * 5.0 / 60.0, basal_rate_delivered=0.80, bolus_delivered=0.0, carbs_consumed=c)
        bg_after_meal = bg

    assert bg_after_meal > 130.0 # Clear post-meal spike

    # 2. Reset and administer a 50g meal with adequate bolus (e.g. 5.5 Units) -> Spike should be moderated
    patient.reset(start_bg=100.0)
    bg_with_bolus = 100.0
    for step in range(12):
        c = 50.0 if step == 0 else 0.0
        b = 5.5 if step == 0 else 0.0
        bg, diag = patient.step(hour_of_day=12.0 + step * 5.0 / 60.0, basal_rate_delivered=0.80, bolus_delivered=b, carbs_consumed=c)
        bg_with_bolus = bg

    assert bg_with_bolus < bg_after_meal # Bolus effectively mitigated the peak

def test_virtual_patient_exercise_effect():
    patient = VirtualPatient(seed=42)
    patient.reset(start_bg=140.0)

    # Trigger exercise at step 0
    bg_series = []
    for step in range(8): # 40 min
        bg, diag = patient.step(hour_of_day=16.0, basal_rate_delivered=0.80, trigger_exercise=(step == 0))
        bg_series.append(bg)

    # Glucose must drop during exercise
    assert bg_series[-1] < bg_series[0]
