import pytest
import numpy as np
from app.ml.rl.simulator.virtual_patient import VirtualPatient

def test_causal_insulin_monotonicity():
    """
    Causal Test: From identical fasting states (G=160 mg/dL, zero COB),
    sweeping insulin dose (0.0, 0.5, 1.0, 2.0 U) must produce strictly monotonic glucose drops at +2h and +4h.
    Any violation (e.g. 2U producing higher BG than 1U) is a severe physiological bug.
    """
    doses = [0.0, 0.5, 1.0, 2.0]
    outcomes_2h = {}
    outcomes_4h = {}

    for dose in doses:
        patient = VirtualPatient(seed=42)
        patient.reset(start_bg=160.0, start_iob=0.0, start_cob=0.0, seed=42)

        # Step 0: deliver dose
        # 24 steps = 2h, 48 steps = 4h
        for s in range(48):
            b = dose if s == 0 else 0.0
            bg, _ = patient.step(hour_of_day=14.0 + (s * 5.0) / 60.0, basal_rate_delivered=0.85, bolus_delivered=b)
            if s == 23: # 2 hours
                outcomes_2h[dose] = bg
            if s == 47: # 4 hours
                outcomes_4h[dose] = bg

    print(f"\n[CAUSAL TEST INSULIN] At +2h: {outcomes_2h}")
    print(f"[CAUSAL TEST INSULIN] At +4h: {outcomes_4h}")

    # Verify strict monotonicity: G(0.0) > G(0.5) > G(1.0) > G(2.0)
    for i in range(len(doses) - 1):
        d1, d2 = doses[i], doses[i + 1]
        assert outcomes_2h[d1] > outcomes_2h[d2], f"Violation at +2h: dose {d1} ({outcomes_2h[d1]}) <= dose {d2} ({outcomes_2h[d2]})"
        assert outcomes_4h[d1] > outcomes_4h[d2], f"Violation at +4h: dose {d1} ({outcomes_4h[d1]}) <= dose {d2} ({outcomes_4h[d2]})"

def test_causal_carb_monotonicity():
    """
    Causal Test: From identical states (G=110 mg/dL, zero IOB),
    sweeping carbs (0, 20, 40, 60 g) with fixed bolus must produce strictly monotonic glucose rises at +2h and +4h.
    """
    carbs_list = [0.0, 20.0, 40.0, 60.0]
    outcomes_2h = {}
    outcomes_4h = {}

    for c_val in carbs_list:
        patient = VirtualPatient(seed=42)
        patient.reset(start_bg=110.0, start_iob=0.0, start_cob=0.0, seed=42)

        for s in range(48):
            c = c_val if s == 0 else 0.0
            bg, _ = patient.step(hour_of_day=12.0 + (s * 5.0) / 60.0, basal_rate_delivered=0.85, bolus_delivered=0.0, carbs_consumed=c)
            if s == 23:
                outcomes_2h[c_val] = bg
            if s == 47:
                outcomes_4h[c_val] = bg

    print(f"\n[CAUSAL TEST CARBS] At +2h: {outcomes_2h}")
    print(f"[CAUSAL TEST CARBS] At +4h: {outcomes_4h}")

    # Verify strict monotonicity: G(0g) < G(20g) < G(40g) < G(60g)
    for i in range(len(carbs_list) - 1):
        c1, c2 = carbs_list[i], carbs_list[i + 1]
        assert outcomes_2h[c1] < outcomes_2h[c2], f"Violation at +2h: carbs {c1} ({outcomes_2h[c1]}) >= carbs {c2} ({outcomes_2h[c2]})"
        assert outcomes_4h[c1] < outcomes_4h[c2], f"Violation at +4h: carbs {c1} ({outcomes_4h[c1]}) >= carbs {c2} ({outcomes_4h[c2]})"
