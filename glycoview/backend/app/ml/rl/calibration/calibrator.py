import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from app.ml.rl.config import PhysiologicalPriors
from app.ml.rl.calibration.clean_events import extract_clean_fasting_events, extract_clean_meal_events

class PhysiologicalCalibrator:
    """
    Calibrates patient parameters with reduced, robust parameterization:
    - Global ISF + smooth circadian modulation (day vs night)
    - Meal-based CR: breakfast (06h-11h), lunch (11h-16h), dinner (18h-23h), other
    - Fixed physiological EGP baseline = 110 mg/dL (prevents artificial hyper bias)
    - Transparently reports raw bootstrap distribution, flags boundary hits,
      and distinguishes data-informed vs prior-dominated parameters.
    """
    def __init__(self, priors: Optional[PhysiologicalPriors] = None):
        self.priors = priors or PhysiologicalPriors()

    def get_meal_category(self, hour: float) -> str:
        if 6.0 <= hour < 11.0:
            return "breakfast"
        elif 11.0 <= hour < 16.0:
            return "lunch"
        elif 18.0 <= hour < 23.0:
            return "dinner"
        else:
            return "other"

    def calibrate(self, df_train: pd.DataFrame, n_bootstraps: int = 500) -> Dict[str, Any]:
        if df_train.empty:
            raise ValueError("Training DataFrame cannot be empty for calibration.")

        fasting_events = extract_clean_fasting_events(df_train)
        meal_events = extract_clean_meal_events(df_train)

        param_diagnostics = {}

        # 1. Calibrate Base ISF and Circadian Variation
        # Gather all clean fasting events
        isf_samples = []
        isf_night_samples = []
        isf_day_samples = []

        for ev in fasting_events:
            delta_g = -ev['delta_sgv']
            net_insulin = ev['mean_iob'] * (ev['length_steps'] * 5.0 / 60.0)
            if net_insulin > 0.25 and delta_g > 3.0:
                s_isf = delta_g / net_insulin
                if 15.0 <= s_isf <= 75.0:
                    isf_samples.append(s_isf)
                    h = ev['hour']
                    if (h >= 22.0) or (h < 7.0):
                        isf_night_samples.append(s_isf)
                    else:
                        isf_day_samples.append(s_isf)

        # Base ISF estimation
        rng = np.random.RandomState(42)
        prior_isf = self.priors.isf_base
        if len(isf_samples) >= 3:
            emp_median = float(np.median(isf_samples))
            point_isf = round(0.40 * prior_isf + 0.60 * emp_median, 1)
            boot_means = [
                float(np.mean(rng.choice(isf_samples, size=len(isf_samples), replace=True)))
                for _ in range(n_bootstraps)
            ]
            ci_low = round(float(np.percentile(boot_means, 2.5)), 1)
            ci_high = round(float(np.percentile(boot_means, 97.5)), 1)
            status_isf = "DATA_INFORMED"
            at_bound = (point_isf <= 16.0) or (point_isf >= 74.0)
        else:
            point_isf = prior_isf
            ci_low = round(prior_isf * 0.85, 1)
            ci_high = round(prior_isf * 1.15, 1)
            status_isf = "PRIOR_DOMINATED"
            at_bound = False
            boot_means = [prior_isf]

        param_diagnostics["isf_base"] = {
            "point_estimate": point_isf,
            "prior": prior_isf,
            "status": status_isf,
            "n_events": len(isf_samples),
            "ci_95": [ci_low, ci_high],
            "raw_distribution": {
                "p2_5": ci_low,
                "p25": round(float(np.percentile(boot_means, 25)), 1),
                "p50": round(float(np.percentile(boot_means, 50)), 1),
                "p75": round(float(np.percentile(boot_means, 75)), 1),
                "p97_5": ci_high
            },
            "at_boundary": at_bound
        }

        # 2. Calibrate Meal-based CRs
        meal_cr_samples = {"breakfast": [], "lunch": [], "dinner": [], "other": []}
        for m in meal_events:
            c = m['carbs']
            b = m['bolus']
            excursion = m['excursion']
            cat = self.get_meal_category(m['hour'])
            if b > 0.4 and c >= 15.0:
                est_b = b + (excursion / point_isf)
                if est_b > 0.2:
                    s_cr = c / est_b
                    if 4.0 <= s_cr <= 22.0:
                        meal_cr_samples[cat].append(s_cr)

        priors_cr = {
            "breakfast": self.priors.cr_breakfast,
            "lunch": self.priors.cr_lunch,
            "dinner": self.priors.cr_dinner,
            "other": self.priors.cr_other
        }

        calibrated_crs = {}
        for cat, samples in meal_cr_samples.items():
            prior_val = priors_cr[cat]
            if len(samples) >= 3:
                emp_cr = float(np.median(samples))
                pt_cr = round(0.40 * prior_val + 0.60 * emp_cr, 1)
                b_cr = [
                    float(np.mean(rng.choice(samples, size=len(samples), replace=True)))
                    for _ in range(n_bootstraps)
                ]
                c_low = round(float(np.percentile(b_cr, 2.5)), 1)
                c_high = round(float(np.percentile(b_cr, 97.5)), 1)
                st = "DATA_INFORMED"
                bound = (pt_cr <= 4.2) or (pt_cr >= 21.8)
            else:
                pt_cr = prior_val
                c_low = round(prior_val * 0.88, 1)
                c_high = round(prior_val * 1.12, 1)
                st = "PRIOR_DOMINATED"
                bound = False
                b_cr = [prior_val]

            calibrated_crs[cat] = pt_cr
            param_diagnostics[f"cr_{cat}"] = {
                "point_estimate": pt_cr,
                "prior": prior_val,
                "status": st,
                "n_events": len(samples),
                "ci_95": [c_low, c_high],
                "raw_distribution": {
                    "p2_5": c_low,
                    "p25": round(float(np.percentile(b_cr, 25)), 1),
                    "p50": round(float(np.percentile(b_cr, 50)), 1),
                    "p75": round(float(np.percentile(b_cr, 75)), 1),
                    "p97_5": c_high
                },
                "at_boundary": bound
            }

        # Build hourly schedules (0..7 blocks) from compact parameters for downstream models
        isf_by_block = {}
        cr_by_block = {}
        for b in range(8):
            mid_hour = b * 3.0 + 1.5
            # Smooth cosine circadian modulation (higher sensitivity at night)
            circadian_mod = self.priors.isf_circadian_amp * math.cos(2.0 * math.pi * (mid_hour - self.priors.isf_peak_hour) / 24.0)
            isf_by_block[b] = round(point_isf + circadian_mod, 1)
            cat = self.get_meal_category(mid_hour)
            cr_by_block[b] = calibrated_crs[cat]

        return {
            "status": "calibrated",
            "dia": self.priors.dia_hours,
            "egp_baseline": self.priors.egp_baseline_sgv, # fixed to healthy 110.0 mg/dL
            "isf_base": point_isf,
            "isf_by_block": isf_by_block,
            "cr_by_block": cr_by_block,
            "cr_by_meal": calibrated_crs,
            "basal_by_block": self.priors.basal_by_block,
            "diagnostics": param_diagnostics,
            "n_fasting_events_extracted": len(fasting_events),
            "n_meal_events_extracted": len(meal_events),
            "total_train_steps": len(df_train)
        }
