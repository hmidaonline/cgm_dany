import gymnasium as gym
from gymnasium.spaces import Box
import numpy as np
from typing import Dict, Any, Tuple, Optional

from app.ml.rl.env.glucose_env import GlycoTwinEnv
from app.ml.rl.baselines.controllers import Oref0HeuristicPolicy

class ResidualGlycoTwinEnv(gym.Env):
    """
    Residual RL Environment wrapping GlycoTwinEnv around Oref0 Heuristic Controller.
    
    Mathematical Formulation:
    u_t = clip(u_oref0(s_t) + alpha * a_t^RL, 0.0, 3.0)
    followed by deterministic SafetyShield filtering.
    
    When a_t^RL = 0, the policy acts identically to Oref0 (+ SafetyShield).
    The RL policy only learns corrective bounded residuals to optimize
    clinical outcomes (TIR, Tight TIR, BGRI) beyond the heuristic baseline.
    """
    metadata = {"render_modes": []}

    def __init__(
        self,
        alpha: float = 0.50, # Residual scaling (bounds adjustment to +/- 50% of nominal basal)
        is_training: bool = True,
        use_shield: bool = True,
        domain_randomization: bool = True,
        episode_steps: int = 288,
        calibrated_params: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None
    ):
        super().__init__()
        self.alpha = float(alpha)
        self.is_training = is_training
        self.use_shield = use_shield
        self.domain_randomization = domain_randomization
        self.episode_steps = episode_steps
        self.calibrated_params = calibrated_params or {}
        self.rng = np.random.RandomState(seed if seed is not None else 42)

        # Underlying physiological twin environment
        self.base_env = GlycoTwinEnv(
            calibrated_params=self.calibrated_params,
            use_shield=self.use_shield,
            domain_randomization=self.domain_randomization,
            episode_steps=self.episode_steps,
            seed=seed
        )

        # Baseline heuristic controller (frozen prior)
        self.oref0_policy = Oref0HeuristicPolicy()

        # Observation and Action spaces
        self.observation_space = self.base_env.observation_space
        # Bounded residual action in [-1.0, 1.0]
        self.action_space = Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)

        # Track single-step base observation for Oref0 heuristic
        self._last_raw_obs: Optional[np.ndarray] = None

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self.rng = np.random.RandomState(seed)

        # Scenario selection curriculum
        scenario_type = "standard_day"
        if options and "scenario_type" in options:
            scenario_type = options["scenario_type"]
        elif self.is_training:
            # 50% nominal / 50% stress curriculum
            if self.rng.rand() < 0.50:
                scenario_type = "standard_day"
            else:
                stress_choices = [
                    "forgotten_bolus",
                    "high_fat_meal",
                    "exercise",
                    "carb_undercounting",
                    "carb_overestimation"
                ]
                scenario_type = str(self.rng.choice(stress_choices))

        obs, info = self.base_env.reset(seed=seed, options={"scenario_type": scenario_type})
        self._last_raw_obs = obs.copy()
        self.oref0_policy.reset()

        info["scenario_type"] = scenario_type
        info["controller_type"] = "Residual_Oref0"
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        # 1. Compute baseline Oref0 action from last observation
        oref0_action, _ = self.oref0_policy.predict(self._last_raw_obs)
        # Convert Oref0 action in [-1, 1] to target multiplier in [0, 3]
        oref0_mult = self.base_env.action_mapper.to_multiplier(oref0_action)

        # 2. Extract and scale bounded residual
        rl_action_val = float(action[0] if isinstance(action, (np.ndarray, list)) else action)
        rl_action_val = float(np.clip(rl_action_val, -1.0, 1.0))
        residual_delta = self.alpha * rl_action_val

        # 3. Combine into effective multiplier: u_t = clip(u_oref0 + alpha * a_rl, 0, 3)
        combined_mult = float(np.clip(oref0_mult + residual_delta, 0.0, 3.0))

        # Convert back to [-1, 1] for base_env.action_mapper
        # Since mult = 1.0 + action_val * 1.5, action_val = (mult - 1.0) / 1.5
        mapped_action_val = (combined_mult - 1.0) / 1.5
        mapped_action = np.array([np.clip(mapped_action_val, -1.0, 1.0)], dtype=np.float32)

        # 4. Advance base environment (which handles SafetyShield filtering and physiological step)
        obs, reward, terminated, truncated, info = self.base_env.step(mapped_action)
        self._last_raw_obs = obs.copy()

        # Add residual diagnostics
        info["residual_info"] = {
            "oref0_mult": round(oref0_mult, 3),
            "rl_residual_action": round(rl_action_val, 4),
            "residual_delta": round(residual_delta, 3),
            "combined_mult": round(combined_mult, 3),
            "final_delivered_mult": round(info.get("basal_multiplier", combined_mult), 3)
        }

        return obs, reward, terminated, truncated, info
