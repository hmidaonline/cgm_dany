import numpy as np
from typing import Dict, Any, Optional
import gymnasium as gym
from gymnasium.spaces import Box

class ObservationBuilder:
    """
    POMDP Observation Builder for GlycoTwinEnv.
    Returns normalized 1D vector:
    [0] CGM glucose (normalized [40, 400] -> [0, 1])
    [1] 15-min velocity (normalized [-5, +5] mg/dL/min -> [-1, 1])
    [2] Controller IOB (normalized [0, 10] U -> [0, 1])
    [3] Controller COB (normalized [0, 120] g -> [0, 1])
    [4] Sin(hour) [-1, 1]
    [5] Cos(hour) [-1, 1]
    [6] Announced carbs at current step (normalized [0, 100] g -> [0, 1])
    [7] Current active basal multiplier (normalized [0, 3] -> [0, 1])
    [8] Time since last bolus (normalized [0, 8] hours -> [0, 1])
    Total dimension = 9 features.
    """
    def __init__(self):
        self.observation_space = Box(
            low=np.array([0.0, -1.0, 0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32
        )

    def build_observation(
        self,
        cgm_reading: float,
        velocity_15: float,
        controller_iob: float,
        controller_cob: float,
        hour_of_day: float,
        announced_carbs: float,
        active_basal_mult: float,
        time_since_last_bolus_hours: float
    ) -> np.ndarray:
        # Safe normalization
        norm_cgm = float(np.clip((cgm_reading - 40.0) / (400.0 - 40.0), 0.0, 1.0))
        norm_vel = float(np.clip(velocity_15 / 5.0, -1.0, 1.0))
        norm_iob = float(np.clip(controller_iob / 10.0, 0.0, 1.0))
        norm_cob = float(np.clip(controller_cob / 120.0, 0.0, 1.0))
        sin_h = float(np.sin(2.0 * np.pi * hour_of_day / 24.0))
        cos_h = float(np.cos(2.0 * np.pi * hour_of_day / 24.0))
        norm_carbs = float(np.clip(announced_carbs / 100.0, 0.0, 1.0))
        norm_basal = float(np.clip(active_basal_mult / 3.0, 0.0, 1.0))
        norm_ts_bolus = float(np.clip(time_since_last_bolus_hours / 8.0, 0.0, 1.0))

        obs = np.array([
            norm_cgm,
            norm_vel,
            norm_iob,
            norm_cob,
            sin_h,
            cos_h,
            norm_carbs,
            norm_basal,
            norm_ts_bolus
        ], dtype=np.float32)

        return obs
