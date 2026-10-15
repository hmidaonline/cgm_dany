from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
from app.ml.rl.config import SafetyShieldConfig

@dataclass
class ShieldAudit:
    triggered: bool
    reason: str
    original_action: float
    safe_action: float
    penalty: float

class SafetyShield:
    """
    Deterministic out-of-network safety guardrail:
    1. Low Glucose Suspend (LGS) when CGM < 80 mg/dL -> Action forced to 0.0 (basal suspended).
    2. Predictive Low Glucose Suspend (PLGS) when projected CGM at 30 min < 70 mg/dL -> Action forced to 0.0.
    3. Insulin On Board (IOB) Hard Cap: blocks additional basal if controller IOB > max_iob_cap.
    4. Maximum Basal Multiplier Cap: clamps multiplier to <= max_basal_multiplier (3.0).
    5. Returns audit record with penalty for reinforcement learning alignment.
    """
    def __init__(self, config: Optional[SafetyShieldConfig] = None):
        self.config = config or SafetyShieldConfig()

    def filter_action(
        self,
        proposed_action_mult: float, # Multiplier in [0.0, 3.0]
        cgm_reading: float,
        velocity_15: float,          # mg/dL per min
        controller_iob: float,
        current_isf: float = 32.0
    ) -> Tuple[float, ShieldAudit]:
        # 1. Check Low Glucose Suspend (CGM < 80 mg/dL)
        if cgm_reading < self.config.low_glucose_suspend_mgdl:
            return 0.0, ShieldAudit(
                triggered=True,
                reason="LOW_GLUCOSE_SUSPEND",
                original_action=proposed_action_mult,
                safe_action=0.0,
                penalty=self.config.shield_activation_penalty
            )

        # 2. Check Predictive Low Glucose Suspend (at 30 min)
        # Simplified momentum projection: G_proj = G + 30 * vel - (IOB * ISF * 0.3)
        proj_30 = cgm_reading + (self.config.predictive_horizon_min * velocity_15) - (controller_iob * current_isf * 0.25)
        if proj_30 < self.config.predictive_low_suspend_mgdl:
            return 0.0, ShieldAudit(
                triggered=True,
                reason="PREDICTIVE_LOW_SUSPEND",
                original_action=proposed_action_mult,
                safe_action=0.0,
                penalty=self.config.shield_activation_penalty
            )

        # 3. Check IOB Hard Cap
        if controller_iob >= self.config.max_iob_cap and proposed_action_mult > 1.0:
            # Throttle basal back to 1.0 (no extra insulin above scheduled profile)
            return 1.0, ShieldAudit(
                triggered=True,
                reason="IOB_CAP_EXCEEDED",
                original_action=proposed_action_mult,
                safe_action=1.0,
                penalty=self.config.shield_activation_penalty * 0.5
            )

        # 4. Check Maximum Basal Multiplier Cap
        safe_mult = float(min(self.config.max_basal_multiplier, max(0.0, proposed_action_mult)))
        if safe_mult != proposed_action_mult:
            return safe_mult, ShieldAudit(
                triggered=True,
                reason="MAX_BASAL_EXCEEDED",
                original_action=proposed_action_mult,
                safe_action=safe_mult,
                penalty=self.config.shield_activation_penalty * 0.25
            )

        # Normal operation: no shield intervention needed
        return safe_mult, ShieldAudit(
            triggered=False,
            reason="NONE",
            original_action=proposed_action_mult,
            safe_action=safe_mult,
            penalty=0.0
        )
