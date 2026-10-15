import math
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from app.ml.rl.config import PatientVariabilityConfig, PhysiologicalPriors
from app.ml.digital_twin.model import carb_cob_decay_custom
from app.ml.simulation import insulin_iob_decay

class VirtualPatient:
    """
    Physiological Digital Twin patient with realistic metabolic perturbations:
    1. Inter-day sensitivity drift (Ornstein-Uhlenbeck autosens in [0.7, 1.3]).
    2. Carb counting errors (+/- 20-30%) & delayed gastric emptying for high-fat meals.
    3. Infusion site progressive degradation (age 0-4 days).
    4. Acute physical exercise and illness/stress hepatic surges.
    5. Homeostatic Endogenous Glucose Production (EGP).
    """
    def __init__(
        self,
        calibrated_params: Optional[Dict[str, Any]] = None,
        config: Optional[PatientVariabilityConfig] = None,
        seed: Optional[int] = None
    ):
        self.config = config or PatientVariabilityConfig()
        self.rng = np.random.RandomState(seed if seed is not None else 42)
        
        # Load parameters or fall back to priors
        params = calibrated_params or {}
        priors = PhysiologicalPriors()
        self.dia = float(params.get("dia", priors.dia_hours))
        default_isf = {i: priors.isf_base for i in range(8)}
        default_cr = {i: priors.cr_lunch for i in range(8)}
        self.isf_by_block = params.get("isf_by_block", default_isf)
        self.cr_by_block = params.get("cr_by_block", default_cr)
        self.basal_by_block = params.get("basal_by_block", priors.basal_by_block)
        self.egp_baseline = float(params.get("egp_baseline", priors.egp_baseline_sgv))
        self.egp_rate = priors.egp_pull_rate

        # Dynamic state variables
        self.current_bg: float = 110.0
        self.autosens_ratio: float = 1.0
        self.site_age_days: float = 1.0
        self.exercise_steps_remaining: int = 0
        self.post_exercise_steps_remaining: int = 0
        self.stress_factor: float = 1.0

        # Circular history of past boluses and carbs for continuous convolutions
        # DIA in 5-min steps (e.g. 7.5h * 12 = 90 steps)
        self.max_lookback = int(math.ceil(self.dia * 12)) + 24
        self.past_boluses: List[float] = [0.0] * self.max_lookback
        self.past_carbs: List[Tuple[float, str]] = [(0.0, "normal")] * self.max_lookback
        self.carb_t_max: float = 45.0

    def carb_cob_decay(self, t_minutes: float, speed: str = "normal") -> float:
        """Calculates active COB fraction remaining at t_minutes with dynamic T_max."""
        if t_minutes <= 0:
            return 1.0
        if speed == "fast":
            peak = 25.0
            duration = 90.0
        elif speed == "slow":
            peak = max(75.0, self.carb_t_max * 1.6)
            duration = 240.0
        else: # normal
            peak = self.carb_t_max
            duration = max(120.0, peak * 3.2)
        if t_minutes >= duration:
            return 0.0
        tau = peak * (1.0 - peak / duration) / (1.0 - 2.0 * peak / duration)
        num = (1.0 + t_minutes / tau) * math.exp(-t_minutes / tau) - (1.0 + duration / tau) * math.exp(-duration / tau)
        den = 1.0 - (1.0 + duration / tau) * math.exp(-duration / tau)
        return float(np.clip(num / den, 0.0, 1.0))

    def reset(
        self,
        start_bg: float = 110.0,
        start_iob: float = 0.0,
        start_cob: float = 0.0,
        site_age_days: Optional[float] = None,
        autosens_initial: Optional[float] = None,
        carb_t_max: Optional[float] = None,
        seed: Optional[int] = None
    ):
        if seed is not None:
            self.rng = np.random.RandomState(seed)
        self.current_bg = float(start_bg)
        self.start_iob = max(0.0, float(start_iob))
        self.start_cob = max(0.0, float(start_cob))
        self.steps_since_reset = 0
        self.autosens_ratio = float(autosens_initial) if autosens_initial is not None else float(self.rng.uniform(0.85, 1.15))
        self.site_age_days = float(site_age_days) if site_age_days is not None else float(self.rng.uniform(0.2, 3.5))
        self.carb_t_max = float(carb_t_max) if carb_t_max is not None else 45.0
        self.exercise_steps_remaining = 0
        self.post_exercise_steps_remaining = 0
        self.stress_factor = 1.0
        self.past_boluses = [0.0] * self.max_lookback
        self.past_carbs = [(0.0, "normal")] * self.max_lookback

    def get_time_block(self, hour: float) -> int:
        return min(7, max(0, int(hour // 3)))

    def apply_carb_imprecision(self, announced_carbs: float, meal_speed: str = "normal") -> Tuple[float, str]:
        """Applies realistic +/- 20-30% carb estimation error and fat-delayed absorption."""
        if announced_carbs <= 0:
            return 0.0, meal_speed
        
        # Carb counting error
        error_ratio = self.rng.normal(0, self.config.carb_count_error_std)
        error_ratio = np.clip(error_ratio, -0.30, 0.30)
        actual_carbs = float(max(0.0, announced_carbs * (1.0 + error_ratio)))

        # 20% probability of high-fat delayed absorption
        actual_speed = meal_speed
        if self.rng.rand() < self.config.carb_delayed_absorption_prob and meal_speed != "slow":
            actual_speed = "slow"

        return actual_carbs, actual_speed

    def step(
        self,
        hour_of_day: float,
        basal_rate_delivered: float, # U/h actually delivered during this 5-min step
        bolus_delivered: float = 0.0, # U administered at this step
        carbs_consumed: float = 0.0,  # actual grams entering digestive system
        carb_speed: str = "normal",
        trigger_exercise: bool = False,
        trigger_stress: bool = False
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Advances the virtual patient by one 5-minute timestep in pure physiological open-loop.
        Returns:
            (new_true_blood_glucose, info_dict)
        """
        block_idx = self.get_time_block(hour_of_day)
        scheduled_basal = self.basal_by_block.get(block_idx, 0.85)
        base_isf = self.isf_by_block.get(block_idx, 32.0)
        base_cr = self.cr_by_block.get(block_idx, 9.0)

        # 1. Update Ornstein-Uhlenbeck Autosens Drift
        # dS = theta * (1.0 - S) * dt + sigma * dW
        ou_drift = self.config.drift_ou_theta * (1.0 - self.autosens_ratio)
        ou_noise = self.rng.normal(0, 0.015)
        self.autosens_ratio = float(np.clip(
            self.autosens_ratio + ou_drift + ou_noise,
            self.config.autosens_min,
            self.config.autosens_max
        ))

        # 2. Infusion Site Age Degradation (loss of efficacy after 48h)
        self.site_age_days += (5.0 / 1440.0) # 5 min in days
        site_efficiency = 1.0
        if self.site_age_days > 2.0:
            site_efficiency = max(0.65, 1.0 - (self.site_age_days - 2.0) * self.config.infusion_site_decay_rate)

        # 3. Exercise & Stress Modulation
        if trigger_exercise:
            self.exercise_steps_remaining = int(self.config.exercise_duration_min // 5) # 45 min = 9 steps
            self.post_exercise_steps_remaining = int(4.0 * 60 // 5) # 4 hours = 48 steps
        
        is_exercising = False
        exercise_glucose_burn = 0.0
        if self.exercise_steps_remaining > 0:
            self.exercise_steps_remaining -= 1
            is_exercising = True
            # Captation musculaire directe de glucose : 1.5 à 2.5 mg/dL par pas de 5 min pendant l'effort
            exercise_glucose_burn = float(self.rng.uniform(1.5, 2.5))

        # Hausse d'ISF de 50% pendant l'effort et sur 4h post-effort
        exercise_isf_mult = 1.0
        if is_exercising or self.post_exercise_steps_remaining > 0:
            exercise_isf_mult = 1.50
            if not is_exercising and self.post_exercise_steps_remaining > 0:
                self.post_exercise_steps_remaining -= 1

        effective_stress = 0.75 if trigger_stress else 1.0
        effective_isf = base_isf * self.autosens_ratio * site_efficiency * exercise_isf_mult * effective_stress
        # CSF (Carb Sensitivity Factor in mg/dL per g) is an intrinsic gut property: ISF / CR
        csf = base_isf / base_cr

        # Record inputs into FIFO history (insert at front, pop oldest)
        effective_bolus = bolus_delivered * site_efficiency
        self.past_boluses.insert(0, effective_bolus)
        self.past_boluses.pop()

        self.past_carbs.insert(0, (carbs_consumed, carb_speed))
        self.past_carbs.pop()

        # 3b. Acute Hyperglycemia Resistance (Glucotoxicity saturation)
        if self.current_bg > 180.0:
            hyper_resistance = 1.0 / (1.0 + 0.0025 * (self.current_bg - 180.0))
            effective_isf *= hyper_resistance

        # 4. Incremental Drop from all past active boluses
        bolus_drop_step = 0.0
        lookback_b = min(len(self.past_boluses) - 1, int(self.dia * 12))
        for k in range(lookback_b):
            b_val = self.past_boluses[k + 1] # past step (k+1 steps ago)
            if b_val > 0:
                t_prev = k * 5.0
                t_curr = (k + 1) * 5.0
                d_frac = max(0.0, insulin_iob_decay(t_prev, dia_hours=self.dia) - insulin_iob_decay(t_curr, dia_hours=self.dia))
                bolus_drop_step += b_val * effective_isf * d_frac

        # 5. Incremental Rise from all past active carbs
        carbs_rise_step = 0.0
        lookback_c = min(len(self.past_carbs) - 1, 60) # up to 5 hours
        for k in range(lookback_c):
            c_val, speed = self.past_carbs[k + 1]
            if c_val > 0:
                t_prev = k * 5.0
                t_curr = (k + 1) * 5.0
                d_frac = max(0.0, self.carb_cob_decay(t_prev, speed=speed) - self.carb_cob_decay(t_curr, speed=speed))
                carbs_rise_step += c_val * csf * d_frac

        self.steps_since_reset += 1
        t_prev_reset = (self.steps_since_reset - 1) * 5.0
        t_curr_reset = self.steps_since_reset * 5.0

        # Incremental drop from preexisting IOB present at reset
        if self.start_iob > 0:
            d_iob_start = max(0.0, insulin_iob_decay(t_prev_reset, dia_hours=self.dia) - insulin_iob_decay(t_curr_reset, dia_hours=self.dia))
            bolus_drop_step += self.start_iob * effective_isf * d_iob_start

        # Incremental rise from preexisting COB present at reset
        if self.start_cob > 0:
            d_cob_start = max(0.0, self.carb_cob_decay(t_prev_reset, speed="normal") - self.carb_cob_decay(t_curr_reset, speed="normal"))
            carbs_rise_step += self.start_cob * csf * d_cob_start

        # 6. Basal Rate Delta vs Scheduled (U/h * 5min / 60min)
        basal_delta_units = (basal_rate_delivered - scheduled_basal) * (5.0 / 60.0) * site_efficiency
        basal_drop_step = basal_delta_units * effective_isf

        # 7. Endogenous Glucose Production (EGP) Homeostasis
        # Hepatic production is suppressed when glucose > 110. Only counter-regulatory release occurs when glucose < 100.
        if self.current_bg < 100.0:
            egp_delta = min(2.5, (100.0 - self.current_bg) * 0.015)
        else:
            egp_delta = 0.0

        # 8. Hepatic stress release
        stress_hepatic = 0.0
        if trigger_stress or effective_stress < 1.0:
            stress_hepatic = 2.5 # mg/dL/5min surge

        # Net forward physical step
        net_delta = carbs_rise_step - bolus_drop_step - basal_drop_step + egp_delta - exercise_glucose_burn + stress_hepatic
        self.current_bg = float(np.clip(self.current_bg + net_delta, 25.0, 450.0))

        # Compute true instantaneous IOB and COB currently active
        true_iob = sum(
            self.past_boluses[k] * insulin_iob_decay(k * 5.0, dia_hours=self.dia)
            for k in range(len(self.past_boluses)) if self.past_boluses[k] > 0
        )
        true_cob = sum(
            self.past_carbs[k][0] * self.carb_cob_decay(k * 5.0, speed=self.past_carbs[k][1])
            for k in range(len(self.past_carbs)) if self.past_carbs[k][0] > 0
        )

        diagnostics = {
            "true_blood_glucose": round(self.current_bg, 1),
            "net_delta": round(net_delta, 2),
            "carbs_rise_step": round(carbs_rise_step, 2),
            "bolus_drop_step": round(bolus_drop_step, 2),
            "basal_drop_step": round(basal_drop_step, 2),
            "egp_delta": round(egp_delta, 2),
            "exercise_burn": round(exercise_glucose_burn, 2),
            "true_iob": round(true_iob, 2),
            "true_cob": round(true_cob, 1),
            "autosens_ratio": round(self.autosens_ratio, 3),
            "site_age_days": round(self.site_age_days, 2),
            "site_efficiency": round(site_efficiency, 3),
            "is_exercising": is_exercising
        }

        return self.current_bg, diagnostics
