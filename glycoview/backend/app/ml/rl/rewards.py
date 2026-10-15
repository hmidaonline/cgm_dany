import math
import numpy as np
from typing import Dict, Any, Tuple
from app.ml.rl.config import RewardConfig

class ClinicalRewardCalculator:
    """
    Dense clinical reward calculator based on Kovatchev Blood Glucose Risk Index (BGRI).
    
    Formula:
    f(G) = 1.509 * (ln(G)^1.084 - 5.381)
    Risk(G) = 10 * f(G)^2
    Base Reward = -Risk(G) / 100.0 + offset
    
    Penalties:
    - Severe hypoglycemia (< 54 mg/dL): heavy non-linear penalty
    - Action smoothness (jerk): penalty on (action_t - action_{t-1})^2
    - Insulin stacking: penalty when controller IOB > iob_stacking_threshold
    - Early termination penalty: massive negative reward if episode dies early in severe hypo.
    """
    def __init__(self, config: RewardConfig = None):
        self.config = config or RewardConfig()

    def kovatchev_risk(self, blood_glucose: float) -> Tuple[float, float, float]:
        """
        Calculates Kovatchev Risk Index, LBGI (Low BG Risk), and HBGI (High BG Risk).
        """
        bg = max(20.0, min(500.0, float(blood_glucose)))
        # Transform glucose
        f = 1.509 * ((math.log(bg) ** 1.084) - 5.381)
        risk = 10.0 * (f ** 2)

        lbgi = risk if f < 0 else 0.0
        hbgi = risk if f > 0 else 0.0

        return risk, lbgi, hbgi

    def compute_reward(
        self,
        cgm_reading: float,
        true_bg: float,
        action: float,
        prev_action: float,
        controller_iob: float,
        velocity_15: float = 0.0,
        is_terminated: bool = False
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Computes step reward and diagnostic metrics.
        """
        cgm_reading = float(cgm_reading)
        true_bg = float(true_bg)
        action = float(action.item() if hasattr(action, "item") else action)
        prev_action = float(prev_action.item() if hasattr(prev_action, "item") else prev_action)
        controller_iob = float(controller_iob)
        velocity_15 = float(velocity_15)

        risk, lbgi, hbgi = self.kovatchev_risk(cgm_reading)
        
        # Dense base reward (scaled) + positive offset to prevent suicidal early termination
        risk_scale = getattr(self.config, "bgri_risk_scale", 8.0)
        reward = (-risk / risk_scale) + self.config.reward_offset

        # 1. Standard TIR Bonus (70 - 180 mg/dL)
        tir_bonus = 0.0
        if 70.0 <= cgm_reading <= 180.0:
            tir_bonus = getattr(self.config, "tir_bonus", 0.25)
            reward += tir_bonus

        # 2. Tight TIR Dense Bonus (70 - 140 mg/dL)
        tight_tir_bonus = 0.0
        if 70.0 <= cgm_reading <= 140.0:
            tight_tir_bonus = getattr(self.config, "tight_tir_bonus", 0.50)
            reward += tight_tir_bonus

        # 2. Severe Hypoglycemia Penalty (< 54 mg/dL)
        severe_hypo_penalty = 0.0
        if cgm_reading < self.config.severe_hypo_threshold:
            hypo_gap = (self.config.severe_hypo_threshold - cgm_reading) / 10.0
            severe_hypo_penalty = self.config.severe_hypo_penalty * (1.0 + hypo_gap ** 2)
            reward -= severe_hypo_penalty

        # 3. Action Smoothness Penalty (Jerk) - softly regularized
        action_diff = action - prev_action
        jerk_penalty = self.config.action_smoothness_penalty_weight * (action_diff ** 2)
        reward -= jerk_penalty

        # 4. Insulin Stacking Penalty - ONLY if IOB is high AND glucose is low or falling
        stacking_penalty = 0.0
        if controller_iob > self.config.iob_stacking_threshold and (cgm_reading < 140.0 or velocity_15 < 0.0):
            excess_iob = controller_iob - self.config.iob_stacking_threshold
            stacking_penalty = self.config.iob_stacking_penalty_weight * (excess_iob ** 2)
            reward -= stacking_penalty

        # 5. Terminal Early Failure Penalty
        terminal_penalty = 0.0
        if is_terminated:
            terminal_penalty = self.config.early_termination_penalty
            reward -= terminal_penalty

        diagnostics = {
            "reward": round(reward, 4),
            "bgri": round(risk, 2),
            "lbgi": round(lbgi, 2),
            "hbgi": round(hbgi, 2),
            "tight_tir_bonus": round(tight_tir_bonus, 3),
            "severe_hypo_penalty": round(severe_hypo_penalty, 3),
            "jerk_penalty": round(jerk_penalty, 3),
            "stacking_penalty": round(stacking_penalty, 3),
            "terminal_penalty": round(terminal_penalty, 2),
            "in_target_range": 70.0 <= cgm_reading <= 180.0,
            "in_tight_target": 70.0 <= cgm_reading <= 140.0,
            "is_hypo": cgm_reading < 70.0,
            "is_severe_hypo": cgm_reading < 54.0,
            "is_hyper": cgm_reading > 180.0,
            "is_severe_hyper": cgm_reading > 250.0
        }

        return float(reward), diagnostics
