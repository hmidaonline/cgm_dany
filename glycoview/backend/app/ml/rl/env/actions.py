import numpy as np
import gymnasium as gym
from gymnasium.spaces import Box

class ActionMapper:
    """
    Continuous Action Space in [-1.0, 1.0].
    Maps residual RL action into physical basal multiplier:
    multiplier = base_multiplier + action * scale
    
    With base = 1.0 (scheduled basal) and scale = 1.5,
    action = -1.0 -> multiplier = 0.0 (complete basal suspension)
    action =  0.0 -> multiplier = 1.0 (exact scheduled profile)
    action = +1.0 -> multiplier = 2.5 (250% high temp basal)
    clamped to [0.0, max_multiplier] (e.g. 3.0).
    """
    def __init__(self, base_multiplier: float = 1.0, scale: float = 1.5, max_multiplier: float = 3.0):
        self.base_multiplier = base_multiplier
        self.scale = scale
        self.max_multiplier = max_multiplier
        self.action_space = Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)

    def to_multiplier(self, raw_action: np.ndarray | float) -> float:
        val = float(raw_action[0] if isinstance(raw_action, (np.ndarray, list)) else raw_action)
        val = np.clip(val, -1.0, 1.0)
        mult = self.base_multiplier + val * self.scale
        return float(np.clip(mult, 0.0, self.max_multiplier))
