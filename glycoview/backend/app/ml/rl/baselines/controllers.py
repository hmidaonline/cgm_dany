import numpy as np
from typing import Dict, Any, Tuple, Optional

class OpenLoopBolusWizardPolicy:
    """
    Baseline 1: Open-Loop Pump with Scheduled Basal & Standard Bolus Wizard.
    Action = 0.0 -> exact 100% scheduled basal profile.
    Meal boluses are calculated and delivered by the patient / wizard in GlycoTwinEnv.
    """
    def __init__(self):
        self.name = "OpenLoop_BolusWizard"

    def reset(self):
        pass

    def predict(self, obs: np.ndarray, state: Any = None, deterministic: bool = True) -> Tuple[np.ndarray, Any]:
        # Action 0.0 corresponds to multiplier 1.0 (exact scheduled basal)
        action = np.array([0.0], dtype=np.float32)
        return action, state

class PIDControllerPolicy:
    """
    Baseline 2: Clinical Closed-Loop PID Controller on Temp Basal.
    Includes:
    - Anti-windup on integral term
    - Derivative action on CGM velocity
    - Direct negative IOB feedback to prevent insulin stacking
    """
    def __init__(
        self,
        target_bg: float = 110.0,
        kp: float = 0.020,
        ki: float = 0.00015,
        kd: float = 0.20,
        gamma_iob: float = 0.25
    ):
        self.name = "PID_Controller"
        self.target_bg = target_bg
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.gamma_iob = gamma_iob
        self.integral = 0.0

    def reset(self):
        self.integral = 0.0

    def predict(self, obs: np.ndarray, state: Any = None, deterministic: bool = True) -> Tuple[np.ndarray, Any]:
        # Unpack observation features
        cgm = float(obs[0] * 360.0 + 40.0)
        vel = float(obs[1] * 5.0) # mg/dL/min
        iob = float(obs[2] * 10.0)

        error = cgm - self.target_bg
        # Integrate with anti-windup clamping
        self.integral = float(np.clip(self.integral + error * 5.0, -800.0, 800.0))

        # PID formulation with IOB feedback
        p_term = self.kp * error
        i_term = self.ki * self.integral
        d_term = self.kd * vel
        iob_penalty = self.gamma_iob * iob

        multiplier = 1.0 + p_term + i_term + d_term - iob_penalty
        multiplier = float(np.clip(multiplier, 0.0, 3.0))

        # Map to action space [-1.0, 1.0] where mult = 1.0 + action * 1.5
        action_val = (multiplier - 1.0) / 1.5
        action = np.array([np.clip(action_val, -1.0, 1.0)], dtype=np.float32)
        return action, state

class Oref0HeuristicPolicy:
    """
    Baseline 3: Algorithmic Controller inspired by OpenAPS / AndroidAPS oref0.
    Calculates eventual glucose projection including IOB, COB and UAM deviations,
    then adjusts temp basal rate in [0.0, 3.0 x basal] with Low Glucose Suspend (LGS).
    """
    def __init__(
        self,
        target_bg: float = 110.0,
        isf: float = 32.0,
        cr: float = 8.5
    ):
        self.name = "Oref0_Heuristic"
        self.target_bg = target_bg
        self.isf = isf
        self.cr = cr

    def reset(self):
        pass

    def predict(self, obs: np.ndarray, state: Any = None, deterministic: bool = True) -> Tuple[np.ndarray, Any]:
        cgm = float(obs[0] * 360.0 + 40.0)
        vel = float(obs[1] * 5.0) # mg/dL/min
        iob = float(obs[2] * 10.0)
        cob = float(obs[3] * 120.0)

        # 1. Projected eventual blood glucose
        eventual_bg = cgm - (iob * self.isf)

        # 2. Add carb absorption impact if COB > 0
        if cob > 0.0:
            carb_impact = (cob / self.cr) * self.isf
            pred_bg = eventual_bg + carb_impact
        elif vel > 0.5 and cgm > 110.0:
            # Unannounced carb / UAM absorption proxy
            uam_impact = vel * 15.0 * 1.5
            pred_bg = eventual_bg + uam_impact
        else:
            pred_bg = eventual_bg

        # 3. Low Glucose Suspend / Predictive Low Glucose Suspend
        min_pred = min(cgm + vel * 15.0, pred_bg)
        if cgm < 80.0 or min_pred < 72.0:
            # Complete basal suspension
            target_mult = 0.0
        elif pred_bg > self.target_bg:
            # High glucose: calculate required insulin
            insulin_req = (pred_bg - self.target_bg) / self.isf
            # Aim to deliver over 30 min temp basal (0.5h * sched_basal)
            # sched_basal is approx 0.85 U/h
            target_mult = 1.0 + (insulin_req / (0.5 * 0.85))
            target_mult = float(np.clip(target_mult, 1.0, 3.0))
        else:
            # Moderate low: reduce basal rate
            deficit = (self.target_bg - pred_bg) / self.isf
            target_mult = max(0.0, 1.0 - (deficit / (0.5 * 0.85)))

        # Map to action space [-1.0, 1.0]
        action_val = (target_mult - 1.0) / 1.5
        action = np.array([np.clip(action_val, -1.0, 1.0)], dtype=np.float32)
        return action, state
