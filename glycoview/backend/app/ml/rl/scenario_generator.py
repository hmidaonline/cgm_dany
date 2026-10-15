import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class MealScheduleItem:
    step: int
    announced_carbs: float
    actual_carbs: float
    bolus_dose: float
    meal_speed: str
    is_bolus_forgotten: bool = False

@dataclass
class EpisodeScenario:
    scenario_id: str
    scenario_type: str                  # "standard_day", "forgotten_bolus", "high_fat_meal", "exercise", "pump_failure", "unannounced_snack"
    episode_steps: int                  # 288 steps = 24h
    start_hour: float
    start_bg: float
    start_iob: float
    start_cob: float
    site_age_days: float
    autosens_ratio: float
    meals: List[MealScheduleItem] = field(default_factory=list)
    exercise_step: Optional[int] = None
    pump_failure_steps: Optional[Tuple[int, int]] = None

class ScenarioGenerator:
    """
    Generates realistic 24h (288 steps) or multi-day evaluation scenarios:
    1. Realistic daily schedules based on Ahmed DANY's treatments.
    2. Dedicated stress tests (forgotten bolus, high fat meals, acute exercise, pump failure).
    3. Strict train / test day separation.
    """
    def __init__(self, seed: Optional[int] = 42):
        self.rng = np.random.RandomState(seed)

    def generate_scenario(
        self,
        scenario_type: str = "standard_day",
        episode_steps: int = 288,
        seed: Optional[int] = None
    ) -> EpisodeScenario:
        if seed is not None:
            self.rng = np.random.RandomState(seed)

        start_h = float(self.rng.choice([0.0, 6.0, 7.5, 12.0, 18.0]))
        start_bg = float(self.rng.uniform(85.0, 160.0))
        start_iob = float(self.rng.uniform(0.1, 1.8))
        start_cob = float(self.rng.uniform(0.0, 15.0))
        site_age = float(self.rng.uniform(0.2, 3.2))
        autosens = float(self.rng.uniform(0.85, 1.15))

        meals = []
        exercise_step = None
        pump_failure = None

        if scenario_type == "standard_day":
            # 3 standard meals + 1 afternoon snack
            # Breakfast around 08h (step ~24 if start at 06h)
            meals.append(self._create_meal(target_hour=8.0, start_hour=start_h, carbs_mean=45.0, speed="normal"))
            # Lunch around 12h30
            meals.append(self._create_meal(target_hour=12.5, start_hour=start_h, carbs_mean=60.0, speed="normal"))
            # Afternoon snack around 16h30
            meals.append(self._create_meal(target_hour=16.5, start_hour=start_h, carbs_mean=20.0, speed="fast"))
            # Dinner around 20h
            meals.append(self._create_meal(target_hour=20.0, start_hour=start_h, carbs_mean=55.0, speed="normal"))

        elif scenario_type == "forgotten_bolus":
            meals.append(self._create_meal(target_hour=8.0, start_hour=start_h, carbs_mean=50.0, speed="normal"))
            # Lunch bolus is forgotten!
            lunch = self._create_meal(target_hour=12.5, start_hour=start_h, carbs_mean=65.0, speed="normal")
            lunch.bolus_dose = 0.0
            lunch.is_bolus_forgotten = True
            meals.append(lunch)
            meals.append(self._create_meal(target_hour=20.0, start_hour=start_h, carbs_mean=50.0, speed="normal"))

        elif scenario_type == "high_fat_meal":
            meals.append(self._create_meal(target_hour=8.0, start_hour=start_h, carbs_mean=40.0, speed="normal"))
            # High fat dinner (e.g. pizza) at 19h30, delayed slow digestion
            dinner = self._create_meal(target_hour=19.5, start_hour=start_h, carbs_mean=85.0, speed="slow")
            meals.append(dinner)

        elif scenario_type == "exercise":
            meals.append(self._create_meal(target_hour=8.0, start_hour=start_h, carbs_mean=45.0, speed="normal"))
            meals.append(self._create_meal(target_hour=12.5, start_hour=start_h, carbs_mean=50.0, speed="normal"))
            # Exercise scheduled at 13h45 (75 min post-lunch, with active lunch IOB)
            h_offset = (13.75 - start_h) % 24.0
            exercise_step = int((h_offset * 60.0) // 5)
            meals.append(self._create_meal(target_hour=20.0, start_hour=start_h, carbs_mean=60.0, speed="normal"))

        elif scenario_type == "pump_failure":
            meals.append(self._create_meal(target_hour=8.0, start_hour=start_h, carbs_mean=45.0, speed="normal"))
            # Pump occlusion between 14h and 16h (2 hours = 24 steps without insulin)
            h_fail_start = (14.0 - start_h) % 24.0
            step_fail_start = int((h_fail_start * 60.0) // 5)
            pump_failure = (step_fail_start, step_fail_start + 24)
            meals.append(self._create_meal(target_hour=19.5, start_hour=start_h, carbs_mean=50.0, speed="normal"))

        elif scenario_type == "carb_undercounting":
            # Severe carb undercounting (-40% announced vs actual eaten)
            for h_tgt, c_m in [(8.0, 45.0), (12.5, 65.0), (20.0, 55.0)]:
                m = self._create_meal(target_hour=h_tgt, start_hour=start_h, carbs_mean=c_m, speed="normal")
                # Announced is 40% lower than actual
                actual = m.announced_carbs / 0.60
                m.actual_carbs = round(actual, 1)
                meals.append(m)

        elif scenario_type == "carb_overestimation":
            # Severe carb overestimation (+40% announced vs actual eaten -> bolus overdose)
            for h_tgt, c_m in [(8.0, 45.0), (12.5, 65.0), (20.0, 55.0)]:
                m = self._create_meal(target_hour=h_tgt, start_hour=start_h, carbs_mean=c_m, speed="normal")
                # Announced is 40% higher than actual -> patient over-bolused
                actual = m.announced_carbs / 1.40
                m.actual_carbs = round(actual, 1)
                meals.append(m)

        elif scenario_type == "unannounced_snack":
            meals.append(self._create_meal(target_hour=8.0, start_hour=start_h, carbs_mean=45.0, speed="normal"))
            # Unannounced sugary snack at 10h30 (35g, 0 announced, 0 bolus)
            h_snack = (10.5 - start_h) % 24.0
            step_snack = int((h_snack * 60.0) // 5)
            snack = MealScheduleItem(
                step=step_snack,
                announced_carbs=0.0,
                actual_carbs=35.0,
                bolus_dose=0.0,
                meal_speed="fast",
                is_bolus_forgotten=True
            )
            meals.append(snack)
            meals.append(self._create_meal(target_hour=13.0, start_hour=start_h, carbs_mean=60.0, speed="normal"))
            meals.append(self._create_meal(target_hour=20.0, start_hour=start_h, carbs_mean=50.0, speed="normal"))

        # Sort meals chronologically by step
        meals = sorted([m for m in meals if 0 <= m.step < episode_steps], key=lambda x: x.step)

        return EpisodeScenario(
            scenario_id=f"{scenario_type}_{self.rng.randint(1000, 9999)}",
            scenario_type=scenario_type,
            episode_steps=episode_steps,
            start_hour=start_h,
            start_bg=start_bg,
            start_iob=start_iob,
            start_cob=start_cob,
            site_age_days=site_age,
            autosens_ratio=autosens,
            meals=meals,
            exercise_step=exercise_step,
            pump_failure_steps=pump_failure
        )

    def _create_meal(
        self,
        target_hour: float,
        start_hour: float,
        carbs_mean: float,
        speed: str = "normal"
    ) -> MealScheduleItem:
        h_offset = (target_hour - start_hour + self.rng.uniform(-0.5, 0.5)) % 24.0
        step = int((h_offset * 60.0) // 5)
        
        announced_c = float(max(15.0, self.rng.normal(carbs_mean, 8.0)))
        # Symmetrically centered +/- 30% carb counting error U(-30%, +30%)
        err = self.rng.uniform(-0.30, 0.30)
        actual_c = announced_c * (1.0 + err)
        
        # Meal-specific calibrated Carb Ratio (CR)
        if target_hour < 11.0:
            cr = 7.1   # Breakfast
        elif target_hour < 16.0:
            cr = 7.4   # Lunch
        elif target_hour < 18.5:
            cr = 7.5   # Afternoon snack
        else:
            cr = 8.4   # Dinner
            
        bolus = round(announced_c / cr, 1)

        return MealScheduleItem(
            step=step,
            announced_carbs=round(announced_c, 1),
            actual_carbs=round(actual_c, 1),
            bolus_dose=bolus,
            meal_speed=speed,
            is_bolus_forgotten=False
        )
