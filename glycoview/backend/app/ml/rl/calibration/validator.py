import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from app.ml.metrics import calculate_regression_metrics, clarke_error_grid, block_bootstrap_ci
from app.ml.rl.config import GateCriteria
from app.ml.rl.calibration.hybrid_model import HybridDigitalTwin
from app.ml.rl.calibration.clean_events import extract_clean_fasting_events, extract_clean_meal_events

class DigitalTwinValidator:
    """
    Validates both Pure Physiological and Hybrid Digital Twin on held-out test data in strict OPEN-LOOP.
    Checks a priori non-negotiable gate criteria:
    - Skill Score >= 0 vs Persistence at +30 and +60 min
    - Zone E <= 0.5% at +60 min
    - Hypo Signed Bias within [-15, +15] mg/dL
    Computes signed bias by regime and by 6-hour window, and validates event trajectories.
    """
    def __init__(self, calibrated_params: Dict[str, Any], gate_criteria: Optional[GateCriteria] = None):
        self.calibrated_params = calibrated_params
        self.gate = gate_criteria or GateCriteria()
        self.hybrid_twin = HybridDigitalTwin(calibrated_params=calibrated_params)

    def validate(
        self,
        df_train: pd.DataFrame,
        df_test: pd.DataFrame,
        horizons_steps: Dict[str, int] = None,
        step_stride: int = 3
    ) -> Dict[str, Any]:
        if horizons_steps is None:
            horizons_steps = {"30min": 6, "60min": 12}

        # 1. Fit residual corrector on train data
        self.hybrid_twin.fit_residuals(df_train, step_stride=step_stride)

        df = df_test.copy().reset_index(drop=True)
        n = len(df)
        max_h = max(horizons_steps.values())

        results_by_horizon = {}
        gate_checks = {}

        for h_name, h_steps in horizons_steps.items():
            y_true = []
            y_hybrid = []
            y_physio = []
            y_persist = []
            y_linear = []
            sample_hours = []

            for i in range(12, n - max_h, step_stride):
                origin_sgv = float(df.iloc[i]['sgv'])
                target_sgv = float(df.iloc[i + h_steps]['sgv'])
                if np.isnan(origin_sgv) or np.isnan(target_sgv):
                    continue

                dt = pd.to_datetime(df.iloc[i]['datetime'])
                hour = dt.hour + dt.minute / 60.0

                # Baselines
                pred_persist = origin_sgv
                past_3_sgv = float(df.iloc[max(0, i - 3)]['sgv'])
                delta_per_min = (origin_sgv - past_3_sgv) / 15.0
                damping = 0.80 if h_name == "30min" else 0.60
                pred_linear = float(np.clip(origin_sgv + delta_per_min * (h_steps * 5.0) * damping, 30.0, 400.0))

                # Hybrid & Pure Physio
                pred_hyb, pred_phy, _ = self.hybrid_twin.predict(df, i, h_name, h_steps)

                y_true.append(target_sgv)
                y_hybrid.append(pred_hyb)
                y_physio.append(pred_phy)
                y_persist.append(pred_persist)
                y_linear.append(pred_linear)
                sample_hours.append(hour)

            yt = np.array(y_true)
            yh = np.array(y_hybrid)
            yp = np.array(y_physio)
            y_pe = np.array(y_persist)
            y_li = np.array(y_linear)
            hours = np.array(sample_hours)

            m_hyb = calculate_regression_metrics(yt, yh)
            m_phy = calculate_regression_metrics(yt, yp)
            m_pe = calculate_regression_metrics(yt, y_pe)
            m_li = calculate_regression_metrics(yt, y_li)

            c_hyb = clarke_error_grid(yt, yh)
            c_phy = clarke_error_grid(yt, yp)
            c_pe = clarke_error_grid(yt, y_pe)

            # Skill Score vs Persistence: SS = 1 - (MAE_model / MAE_persist)
            ss_hybrid = round(1.0 - (m_hyb["mae"] / m_pe["mae"]), 3)
            ss_physio = round(1.0 - (m_phy["mae"] / m_pe["mae"]), 3)

            # Signed Bias by Glycemic Regime
            hypo_mask = yt < 70.0
            target_mask = (yt >= 70.0) & (yt <= 180.0)
            hyper_mask = yt > 180.0

            signed_bias_overall = round(float(np.mean(yh - yt)), 2)
            signed_bias_hypo = round(float(np.mean(yh[hypo_mask] - yt[hypo_mask])), 2) if np.sum(hypo_mask) > 0 else 0.0
            signed_bias_target = round(float(np.mean(yh[target_mask] - yt[target_mask])), 2) if np.sum(target_mask) > 0 else 0.0
            signed_bias_hyper = round(float(np.mean(yh[hyper_mask] - yt[hyper_mask])), 2) if np.sum(hyper_mask) > 0 else 0.0

            # Signed Bias by 6-hour Window
            w1 = (hours >= 0.0) & (hours < 6.0)
            w2 = (hours >= 6.0) & (hours < 12.0)
            w3 = (hours >= 12.0) & (hours < 18.0)
            w4 = (hours >= 18.0) & (hours < 24.0)

            bias_by_hour = {
                "night_00h_06h": round(float(np.mean(yh[w1] - yt[w1])), 2) if np.sum(w1) > 0 else None,
                "morning_06h_12h": round(float(np.mean(yh[w2] - yt[w2])), 2) if np.sum(w2) > 0 else None,
                "afternoon_12h_18h": round(float(np.mean(yh[w3] - yt[w3])), 2) if np.sum(w3) > 0 else None,
                "evening_18h_24h": round(float(np.mean(yh[w4] - yt[w4])), 2) if np.sum(w4) > 0 else None
            }

            # Paired Bootstrap CI on Delta MAE
            diff_hyb_pe = np.abs(yt - y_pe) - np.abs(yt - yh)
            ci_vs_persist = block_bootstrap_ci(np.zeros_like(diff_hyb_pe), diff_hyb_pe)

            results_by_horizon[h_name] = {
                "n_samples": len(yt),
                "hybrid": {
                    **m_hyb,
                    "skill_score_vs_persist": ss_hybrid,
                    "clarke": c_hyb,
                    "signed_bias": signed_bias_overall,
                    "signed_bias_by_regime": {
                        "hypo": signed_bias_hypo,
                        "target": signed_bias_target,
                        "hyper": signed_bias_hyper
                    },
                    "signed_bias_by_hour": bias_by_hour,
                    "mae_by_regime": {
                        "hypo": round(float(np.mean(np.abs(yt[hypo_mask] - yh[hypo_mask]))), 2) if np.sum(hypo_mask) > 0 else None,
                        "target": round(float(np.mean(np.abs(yt[target_mask] - yh[target_mask]))), 2) if np.sum(target_mask) > 0 else None,
                        "hyper": round(float(np.mean(np.abs(yt[hyper_mask] - yh[hyper_mask]))), 2) if np.sum(hyper_mask) > 0 else None,
                    }
                },
                "pure_physio": {
                    **m_phy,
                    "skill_score_vs_persist": ss_physio,
                    "clarke": c_phy,
                    "signed_bias": round(float(np.mean(yp - yt)), 2)
                },
                "persistence": {
                    **m_pe,
                    "clarke": c_pe,
                    "mae_by_regime": {
                        "hypo": round(float(np.mean(np.abs(yt[hypo_mask] - y_pe[hypo_mask]))), 2) if np.sum(hypo_mask) > 0 else None,
                        "target": round(float(np.mean(np.abs(yt[target_mask] - y_pe[target_mask]))), 2) if np.sum(target_mask) > 0 else None,
                        "hyper": round(float(np.mean(np.abs(yt[hyper_mask] - y_pe[hyper_mask]))), 2) if np.sum(hyper_mask) > 0 else None,
                    }
                },
                "linear": m_li,
                "delta_mae_gain_vs_persist": {
                    "mean_gain": round(float(np.mean(diff_hyb_pe)), 2),
                    "ci_95": [ci_vs_persist["ci_low"], ci_vs_persist["ci_high"]]
                }
            }

        # 2. Event-by-Event Trajectory Validation
        event_validation = self._validate_events(df_test)

        # Check Gate Criteria
        ss30 = results_by_horizon.get("30min", {}).get("hybrid", {}).get("skill_score_vs_persist", 0.0)
        ss60 = results_by_horizon.get("60min", {}).get("hybrid", {}).get("skill_score_vs_persist", 0.0)
        zone_e_60 = results_by_horizon.get("60min", {}).get("hybrid", {}).get("clarke", {}).get("zone_e", 0.0)
        hypo_bias_30 = results_by_horizon.get("30min", {}).get("hybrid", {}).get("signed_bias_by_regime", {}).get("hypo", 0.0)

        if "30min" in results_by_horizon:
            gate_checks["skill_score_30min"] = {"value": ss30, "target": ">= 0.0", "passed": ss30 >= self.gate.min_skill_score_30min}
            gate_checks["hypo_signed_bias_30min"] = {
                "value": hypo_bias_30,
                "target": f"[{self.gate.hypo_signed_bias_min}, {self.gate.hypo_signed_bias_max}]",
                "passed": self.gate.hypo_signed_bias_min <= hypo_bias_30 <= self.gate.hypo_signed_bias_max
            }
        if "60min" in results_by_horizon:
            gate_checks["skill_score_60min"] = {"value": ss60, "target": ">= 0.0", "passed": ss60 >= self.gate.min_skill_score_60min}
            gate_checks["zone_e_60min"] = {"value": zone_e_60, "target": "<= 0.5%", "passed": zone_e_60 <= self.gate.max_zone_e_60min_pct}

        all_passed = all(g["passed"] for g in gate_checks.values())

        return {
            "is_acceptable": all_passed,
            "gate_checks": gate_checks,
            "horizons": results_by_horizon,
            "event_validation": event_validation
        }

    def _validate_events(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validates simulated vs observed trajectories on isolated correction & meal events."""
        fasting = extract_clean_fasting_events(df, min_duration_steps=12)
        meals = extract_clean_meal_events(df, post_meal_steps=24)

        # Correction / Fasting Drops
        corr_errors = []
        for ev in fasting[:10]:
            sub = ev["window_df"]
            observed_drop = ev["delta_sgv"]
            sim_drop = -(sub['iob'].mean() * self.calibrated_params.get("isf_base", 32.0))
            corr_errors.append(abs(observed_drop - sim_drop))

        # Meal Excursions
        meal_errors = []
        for m in meals[:10]:
            obs_excursion = m["excursion"]
            c = m["carbs"]
            b = m["bolus"]
            # expected excursion
            cr = self.calibrated_params.get("cr_by_meal", {}).get(self.hybrid_twin.patient.get_time_block(m["hour"]), 8.5)
            isf = self.calibrated_params.get("isf_base", 32.0)
            expected_excursion = max(0.0, (c / cr - b) * isf)
            meal_errors.append(abs(obs_excursion - expected_excursion))

        return {
            "n_test_fasting_events": len(fasting),
            "mean_correction_error_mgdl": round(float(np.mean(corr_errors)), 1) if corr_errors else None,
            "n_test_meal_events": len(meals),
            "mean_meal_excursion_error_mgdl": round(float(np.mean(meal_errors)), 1) if meal_errors else None
        }
