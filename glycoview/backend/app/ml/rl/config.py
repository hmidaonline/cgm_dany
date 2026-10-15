from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

@dataclass
class PhysiologicalPriors:
    """AAPS Profile priors for Ahmed DANY (HMOE Agadir study)."""
    dia_hours: float = 7.5
    
    # Compact reduced parameterization
    isf_base: float = 32.0                 # Global ISF prior
    isf_circadian_amp: float = 4.0         # Amplitude of circadian ISF variation (+/- 4 mg/dL)
    isf_peak_hour: float = 23.0            # Hour of highest sensitivity (late evening/night)
    
    # Meal-based CR priors
    cr_breakfast: float = 8.5              # Morning (06h - 11h)
    cr_lunch: float = 8.0                  # Noon (11h - 16h)
    cr_dinner: float = 9.5                 # Evening (18h - 23h)
    cr_other: float = 9.0                  # Afternoon / Night
    
    # Scheduled basal profile (flat-averaged or by block)
    basal_rate_default: float = 0.85       # U/h
    basal_by_block: Dict[int, float] = field(default_factory=lambda: {
        0: 0.85, 1: 0.90, 2: 0.90, 3: 0.80,
        4: 0.80, 5: 0.80, 6: 0.80, 7: 0.80
    })

    target_bg: float = 100.0
    egp_baseline_sgv: float = 110.0        # True physiological homeostatic baseline (110 mg/dL)
    egp_pull_rate: float = 0.015           # Gentle homeostatic liver pull rate

@dataclass
class GateCriteria:
    """A priori non-negotiable validation criteria for Phase 1 acceptance."""
    min_skill_score_30min: float = 0.0     # SS >= 0 vs Persistence (MAE_twin <= MAE_persist)
    min_skill_score_60min: float = 0.0     # SS >= 0 vs Persistence
    max_zone_e_60min_pct: float = 0.5      # Zone E <= 0.5% at 60 min
    hypo_signed_bias_min: float = -15.0    # Signed bias in hypo in [-15, +15] mg/dL
    hypo_signed_bias_max: float = 15.0

@dataclass
class CGMSensorConfig:
    """Interstitium-to-sensor dynamics and error characteristics."""
    lag_time_minutes: float = 8.0          # 5 to 15 min physiological lag
    sensor_noise_std: float = 3.5          # mg/dL white noise standard deviation
    arma_phi: float = 0.70                 # AR(1) temporal autocorrelation of sensor error
    dropout_probability: float = 0.005     # 0.5% chance of missed transmission
    dropout_max_duration_steps: int = 3    # up to 15 min dropout
    compression_low_prob: float = 0.002    # 0.2% chance per nocturnal step
    compression_drop_mgdl: float = 30.0    # sudden dip magnitude
    compression_duration_steps: int = 6    # ~30 min dip

@dataclass
class PatientVariabilityConfig:
    """Inter-day, circadian drift, behavioral and infusion site perturbations."""
    autosens_min: float = 0.70             # Min autosens ratio (resistance)
    autosens_max: float = 1.30             # Max autosens ratio (sensibilité accrue)
    drift_ou_theta: float = 0.05           # Ornstein-Uhlenbeck mean-reverting speed
    carb_count_error_std: float = 0.15     # +/- 15-30% error on carb estimation
    carb_delayed_absorption_prob: float = 0.20 # 20% of meals are high fat/protein (slow)
    infusion_site_age_days: float = 2.0    # 0 to 4 days
    infusion_site_decay_rate: float = 0.08 # Loss of insulin effectiveness per day after day 2
    exercise_prob: float = 0.05            # Probability of exercise event
    exercise_intensity: float = 1.35       # Sensitivity multiplier during exercise
    exercise_duration_min: float = 45.0    # Duration of acute exercise

@dataclass
class SafetyShieldConfig:
    """Out-of-network deterministic safety guardrails."""
    low_glucose_suspend_mgdl: float = 80.0
    predictive_low_suspend_mgdl: float = 70.0
    predictive_horizon_min: float = 30.0
    max_basal_multiplier: float = 3.0
    max_iob_cap: float = 7.0               # Max allowable IOB in Units
    shield_activation_penalty: float = 0.01 # Strongly reduced to prevent penalizing proactive suspensions

@dataclass
class RewardConfig:
    """Kovatchev Risk Index dense reward parameters."""
    target_low: float = 70.0
    target_high: float = 180.0
    severe_hypo_threshold: float = 54.0
    severe_hypo_penalty: float = 20.0
    bgri_risk_scale: float = 8.0                   # Scaled so clinical glycemic risk dominates
    action_smoothness_penalty_weight: float = 0.001 # Minimal smoothness penalty to avoid penalizing meal reactivity
    iob_stacking_threshold: float = 4.0
    iob_stacking_penalty_weight: float = 0.01       # Strongly reduced conditional penalty
    tir_bonus: float = 0.25                        # Dense bonus for standard target [70, 180] mg/dL
    tight_tir_bonus: float = 0.50                  # Dense bonus for tight target [70, 140] mg/dL
    early_termination_penalty: float = 100.0
    reward_offset: float = 2.0                     # Positive baseline to prevent suicidal early termination
