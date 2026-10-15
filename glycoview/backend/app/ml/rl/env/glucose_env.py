import numpy as np
import gymnasium as gym
from typing import Dict, Any, Tuple, Optional

from app.ml.rl.config import (
    PhysiologicalPriors,
    CGMSensorConfig,
    PatientVariabilityConfig,
    SafetyShieldConfig,
    RewardConfig
)
from app.ml.rl.simulator.virtual_patient import VirtualPatient
from app.ml.rl.simulator.cgm_sensor import CGMSensorModel
from app.ml.rl.env.safety_shield import SafetyShield, ShieldAudit
from app.ml.rl.rewards import ClinicalRewardCalculator
from app.ml.rl.env.observations import ObservationBuilder
from app.ml.rl.env.actions import ActionMapper
from app.ml.rl.scenario_generator import ScenarioGenerator, EpisodeScenario

class GlycoTwinEnv(gym.Env):
    """
    Standard Gymnasium Environment wrapping the Personalized Digital Twin (GlycoTwin).
    Closed-loop basal rate modulation around scheduled profile.
    
    API:
    - reset(seed=..., options=...) -> (obs, info)
    - step(action) -> (obs, reward, terminated, truncated, info)
    """
    metadata = {"render_modes": ["human"], "render_fps": 30}

    def __init__(
        self,
        calibrated_params: Optional[Dict[str, Any]] = None,
        use_shield: bool = True,
        domain_randomization: bool = False,
        episode_steps: int = 288,           # 24 hours at 5-min steps
        seed: Optional[int] = 42
    ):
        super().__init__()
        self.calibrated_params = calibrated_params or {}
        self.use_shield = use_shield
        self.domain_randomization = domain_randomization
        self.episode_steps = episode_steps

        # Components
        self.patient = VirtualPatient(calibrated_params=self.calibrated_params, seed=seed)
        self.sensor = CGMSensorModel(seed=seed)
        self.shield = SafetyShield()
        self.reward_calc = ClinicalRewardCalculator()
        self.obs_builder = ObservationBuilder()
        self.action_mapper = ActionMapper()
        self.scenario_gen = ScenarioGenerator(seed=seed)

        # Spaces
        self.observation_space = self.obs_builder.observation_space
        self.action_space = self.action_mapper.action_space

        # Internal episode state
        self.current_step: int = 0
        self.current_scenario: Optional[EpisodeScenario] = None
        self.current_cgm: float = 110.0
        self.prev_cgm: float = 110.0
        self.velocity_15: float = 0.0
        self.prev_action_mult: float = 1.0
        self.active_basal_mult: float = 1.0
        self.controller_iob: float = 0.0
        self.controller_cob: float = 0.0
        self.time_since_last_bolus_min: float = 120.0
        self.severe_hypo_consecutive_steps: int = 0

        # Episode accumulator metrics
        self.history_cgm: list[float] = []
        self.history_rewards: list[float] = []

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        options = options or {}
        scenario_type = options.get("scenario_type", "standard_day")

        # Generate scenario
        self.current_scenario = self.scenario_gen.generate_scenario(
            scenario_type=scenario_type,
            episode_steps=self.episode_steps,
            seed=seed
        )

        # Reset patient & sensor
        self.patient.reset(
            start_bg=self.current_scenario.start_bg,
            start_iob=self.current_scenario.start_iob,
            start_cob=self.current_scenario.start_cob,
            site_age_days=self.current_scenario.site_age_days,
            autosens_initial=self.current_scenario.autosens_ratio,
            seed=seed
        )

        # Domain Randomization (if enabled for robust RL training)
        if self.domain_randomization:
            rng = self.patient.rng
            # ISF randomized +/- 30%
            isf_scale = rng.uniform(0.70, 1.30)
            self.patient.isf_by_block = {k: v * isf_scale for k, v in self.patient.isf_by_block.items()}
            # CSF (ISF/CR) randomized +/- 25% -> CR varies inversely
            csf_scale = rng.uniform(0.75, 1.25)
            self.patient.cr_by_block = {k: v / csf_scale for k, v in self.patient.cr_by_block.items()}
            # DIA randomized +/- 15%
            self.patient.dia = float(np.clip(self.patient.dia * rng.uniform(0.85, 1.15), 4.0, 9.0))
            # Carb absorption T_max randomized in [30, 75] min
            self.patient.carb_t_max = float(rng.uniform(30.0, 75.0))

        self.sensor.reset(initial_blood_glucose=self.current_scenario.start_bg, seed=seed)

        # Initialize CGM reading
        initial_cgm, _ = self.sensor.step(self.current_scenario.start_bg, hour_of_day=self.current_scenario.start_hour)
        self.current_cgm = initial_cgm if initial_cgm is not None else self.current_scenario.start_bg
        self.prev_cgm = self.current_cgm
        self.velocity_15 = 0.0

        self.current_step = 0
        self.prev_action_mult = 1.0
        self.active_basal_mult = 1.0
        self.controller_iob = self.current_scenario.start_iob
        self.controller_cob = self.current_scenario.start_cob
        self.time_since_last_bolus_min = 120.0
        self.severe_hypo_consecutive_steps = 0
        self.history_cgm = [self.current_cgm]
        self.history_rewards = []

        obs = self.obs_builder.build_observation(
            cgm_reading=self.current_cgm,
            velocity_15=self.velocity_15,
            controller_iob=self.controller_iob,
            controller_cob=self.controller_cob,
            hour_of_day=self.current_scenario.start_hour,
            announced_carbs=0.0,
            active_basal_mult=self.active_basal_mult,
            time_since_last_bolus_hours=self.time_since_last_bolus_min / 60.0
        )

        info = {
            "scenario_id": self.current_scenario.scenario_id,
            "scenario_type": self.current_scenario.scenario_type,
            "start_bg": self.current_scenario.start_bg,
            "initial_cgm": self.current_cgm
        }

        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.current_step += 1
        hour = (self.current_scenario.start_hour + (self.current_step * 5.0) / 60.0) % 24.0
        block_idx = self.patient.get_time_block(hour)
        scheduled_basal = self.patient.basal_by_block.get(block_idx, 0.85)

        # 1. Action Mapping ([-1, 1] -> multiplier)
        proposed_mult = self.action_mapper.to_multiplier(action)

        # 2. Safety Shield (if enabled)
        shield_audit = ShieldAudit(triggered=False, reason="DISABLED", original_action=proposed_mult, safe_action=proposed_mult, penalty=0.0)
        if self.use_shield:
            effective_mult, shield_audit = self.shield.filter_action(
                proposed_action_mult=proposed_mult,
                cgm_reading=self.current_cgm,
                velocity_15=self.velocity_15,
                controller_iob=self.controller_iob,
                current_isf=self.patient.isf_by_block.get(block_idx, 32.0)
            )
        else:
            effective_mult = proposed_mult

        self.active_basal_mult = effective_mult
        delivered_basal_rate = scheduled_basal * effective_mult

        # Check pump occlusion stress scenario
        if self.current_scenario.pump_failure_steps:
            f_start, f_end = self.current_scenario.pump_failure_steps
            if f_start <= self.current_step < f_end:
                delivered_basal_rate = 0.0 # Occlusion!

        # 3. Handle Scheduled Meal and Standard Bolus Calculator
        announced_c = 0.0
        actual_c = 0.0
        bolus_dose = 0.0
        speed = "normal"

        for m in self.current_scenario.meals:
            if m.step == self.current_step:
                announced_c = m.announced_carbs
                actual_c = m.actual_carbs
                speed = m.meal_speed
                if not m.is_bolus_forgotten:
                    bolus_dose = m.bolus_dose
                    self.time_since_last_bolus_min = 0.0
                break

        self.time_since_last_bolus_min += 5.0

        # Check acute exercise trigger
        trigger_ex = (self.current_scenario.exercise_step == self.current_step)

        # 4. Advance Virtual Patient
        true_bg, patient_diag = self.patient.step(
            hour_of_day=hour,
            basal_rate_delivered=delivered_basal_rate,
            bolus_delivered=bolus_dose,
            carbs_consumed=actual_c,
            carb_speed=speed,
            trigger_exercise=trigger_ex
        )

        # 5. Measure via Subcutaneous CGM Sensor
        raw_cgm, sensor_diag = self.sensor.step(true_bg, hour_of_day=hour)
        if raw_cgm is None:
            # Sensor dropout: persist previous reading
            cgm_reading = self.current_cgm
        else:
            cgm_reading = raw_cgm

        # Update trend velocity
        self.velocity_15 = (cgm_reading - self.prev_cgm) / 5.0 # instantaneous step rate
        self.prev_cgm = self.current_cgm
        self.current_cgm = cgm_reading
        self.history_cgm.append(cgm_reading)

        # Update controller IOB and COB estimates
        self.controller_iob = patient_diag["true_iob"]
        self.controller_cob = patient_diag["true_cob"]

        # 6. Check Termination Conditions
        # Terminated if severe hypoglycemia (true BG < 54 mg/dL) for >= 15 min (3 consecutive steps)
        if true_bg < 54.0:
            self.severe_hypo_consecutive_steps += 1
        else:
            self.severe_hypo_consecutive_steps = 0

        terminated = (self.severe_hypo_consecutive_steps >= 3)
        truncated = (self.current_step >= self.episode_steps)

        # 7. Compute Clinical Dense Reward
        reward, reward_diag = self.reward_calc.compute_reward(
            cgm_reading=self.current_cgm,
            true_bg=true_bg,
            action=effective_mult,
            prev_action=self.prev_action_mult,
            controller_iob=self.controller_iob,
            velocity_15=self.velocity_15,
            is_terminated=terminated
        )

        # Subtract small shield intervention penalty if shield had to act
        if shield_audit.triggered:
            reward -= shield_audit.penalty

        self.prev_action_mult = effective_mult
        self.history_rewards.append(reward)

        # 8. Build Next Observation
        obs = self.obs_builder.build_observation(
            cgm_reading=self.current_cgm,
            velocity_15=self.velocity_15,
            controller_iob=self.controller_iob,
            controller_cob=self.controller_cob,
            hour_of_day=hour,
            announced_carbs=announced_c,
            active_basal_mult=effective_mult,
            time_since_last_bolus_hours=self.time_since_last_bolus_min / 60.0
        )

        info = {
            "step": self.current_step,
            "cgm_reading": self.current_cgm,
            "true_bg": true_bg,
            "delivered_basal_rate": round(delivered_basal_rate, 2),
            "effective_mult": round(effective_mult, 2),
            "shield": {
                "triggered": shield_audit.triggered,
                "reason": shield_audit.reason,
                "original_action": round(shield_audit.original_action, 2),
                "safe_action": round(shield_audit.safe_action, 2)
            },
            "sensor": sensor_diag,
            "reward_diag": reward_diag
        }

        # If episode ends, add summary TIR metrics
        if terminated or truncated:
            cgms = np.array(self.history_cgm)
            info["episode_summary"] = {
                "total_steps": self.current_step,
                "mean_cgm": round(float(np.mean(cgms)), 1),
                "tir_70_180_pct": round(float(np.mean((cgms >= 70.0) & (cgms <= 180.0)) * 100.0), 1),
                "tbr_under_70_pct": round(float(np.mean(cgms < 70.0) * 100.0), 1),
                "tbr_under_54_pct": round(float(np.mean(cgms < 54.0) * 100.0), 1),
                "tar_over_180_pct": round(float(np.mean(cgms > 180.0) * 100.0), 1),
                "total_reward": round(float(sum(self.history_rewards)), 2),
                "early_terminated": terminated
            }

        return obs, reward, terminated, truncated, info
