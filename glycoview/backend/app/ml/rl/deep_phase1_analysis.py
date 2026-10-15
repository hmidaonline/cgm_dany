import os
import sys
import json
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from sklearn.inspection import permutation_importance
from sklearn.ensemble import HistGradientBoostingRegressor

# Ensure app is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.data.pipeline import get_processed_dataframe
from app.ml.metrics import calculate_regression_metrics, clarke_error_grid, block_bootstrap_ci
from app.ml.rl.config import PhysiologicalPriors, GateCriteria
from app.ml.rl.calibration.calibrator import PhysiologicalCalibrator
from app.ml.rl.calibration.hybrid_model import HybridDigitalTwin
from app.ml.rl.calibration.clean_events import extract_clean_fasting_events, extract_clean_meal_events
from app.ml.rl.simulator.virtual_patient import VirtualPatient

def paired_block_bootstrap_skill_score(
    y_true: np.ndarray,
    y_pred_model: np.ndarray,
    y_pred_persist: np.ndarray,
    block_size: int = 24, # 2 hours = 24 samples
    n_bootstraps: int = 1000,
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    """
    Computes paired block-bootstrap 95% CI for:
    1. Delta MAE = MAE_persist - MAE_model (positive means model is better)
    2. Skill Score = 1 - (MAE_model / MAE_persist)
    """
    n = len(y_true)
    err_model = np.abs(y_true - y_pred_model)
    err_persist = np.abs(y_true - y_pred_persist)

    point_mae_m = float(np.mean(err_model))
    point_mae_p = float(np.mean(err_persist))
    point_delta_mae = point_mae_p - point_mae_m
    point_ss = 1.0 - (point_mae_m / point_mae_p) if point_mae_p > 0 else 0.0

    n_blocks = max(1, n - block_size + 1)
    blocks_idx = [np.arange(i, i + block_size) for i in range(n_blocks)]
    blocks_needed = int(np.ceil(n / block_size))

    rng = np.random.RandomState(42)
    boot_deltas = []
    boot_ss = []

    for _ in range(n_bootstraps):
        sel_blocks = rng.choice(n_blocks, size=blocks_needed, replace=True)
        sample_idx = np.concatenate([blocks_idx[b] for b in sel_blocks])[:n]
        em_sample = err_model[sample_idx]
        ep_sample = err_persist[sample_idx]

        m_m = float(np.mean(em_sample))
        m_p = float(np.mean(ep_sample))
        boot_deltas.append(m_p - m_m)
        boot_ss.append(1.0 - (m_m / m_p) if m_p > 0 else 0.0)

    alpha = 1.0 - confidence_level
    ci_delta_low = float(np.percentile(boot_deltas, 100.0 * (alpha / 2.0)))
    ci_delta_high = float(np.percentile(boot_deltas, 100.0 * (1.0 - alpha / 2.0)))

    ci_ss_low = float(np.percentile(boot_ss, 100.0 * (alpha / 2.0)))
    ci_ss_high = float(np.percentile(boot_ss, 100.0 * (1.0 - alpha / 2.0)))

    return {
        "point_delta_mae": round(point_delta_mae, 2),
        "ci_95_delta_mae": [round(ci_delta_low, 2), round(ci_delta_high, 2)],
        "point_skill_score": round(point_ss, 3),
        "ci_95_skill_score": [round(ci_ss_low, 3), round(ci_ss_high, 3)]
    }

def run_deep_analysis():
    print("=" * 85)
    print("ANALYSE CLINIQUE APPROFONDIE, AUDIT ET BENCHMARK PHASE 1")
    print("=" * 85)

    df_raw = get_processed_dataframe(since="2026-10-01")
    df = df_raw.sort_values("datetime").reset_index(drop=True)
    n_total = len(df)
    split_idx = int(0.70 * n_total)
    df_train = df.iloc[:split_idx].copy().reset_index(drop=True)
    df_test = df.iloc[split_idx:].copy().reset_index(drop=True)

    # 1. Calibrator with reparameterized CSF
    calibrator = PhysiologicalCalibrator()
    calib = calibrator.calibrate(df_train, n_bootstraps=500)

    # Hybrid model
    hybrid_twin = HybridDigitalTwin(calibrated_params=calib)
    hybrid_twin.fit_residuals(df_train, step_stride=2)

    # Evaluate on test set
    n_test = len(df_test)
    horizons = {"30min": 6, "60min": 12}
    eval_data = {}

    for h_name, h_steps in horizons.items():
        y_true = []
        y_hyb = []
        y_phy = []
        y_per = []
        y_t0 = []

        for i in range(12, n_test - h_steps, 2):
            g0 = float(df_test.iloc[i]['sgv'])
            gt = float(df_test.iloc[i + h_steps]['sgv'])
            if np.isnan(g0) or np.isnan(gt):
                continue
            pred_h, pred_p, _ = hybrid_twin.predict(df_test, i, h_name, h_steps)
            y_true.append(gt)
            y_hyb.append(pred_h)
            y_phy.append(pred_p)
            y_per.append(g0)
            y_t0.append(g0)

        yt = np.array(y_true)
        yh = np.array(y_hyb)
        yp = np.array(y_phy)
        ype = np.array(y_per)
        yt0 = np.array(y_t0)

        # Paired block bootstrap on Skill Score and Delta MAE
        paired_bs = paired_block_bootstrap_skill_score(yt, yh, ype, block_size=24, n_bootstraps=1000)

        # Stratification by state at t0
        hypo_t0 = yt0 < 70.0
        target_t0 = (yt0 >= 70.0) & (yt0 <= 180.0)
        hyper_t0 = yt0 > 180.0

        strat_t0 = {}
        for r_name, mask in [("Hypo (<70)", hypo_t0), ("Cible (70-180)", target_t0), ("Hyper (>180)", hyper_t0)]:
            n_sub = int(np.sum(mask))
            if n_sub > 0:
                mae_h = round(float(np.mean(np.abs(yt[mask] - yh[mask]))), 2)
                mae_p = round(float(np.mean(np.abs(yt[mask] - ype[mask]))), 2)
                bias_h = round(float(np.mean(yh[mask] - yt[mask])), 2)
                bias_p = round(float(np.mean(ype[mask] - yt[mask])), 2)
                strat_t0[r_name] = {"N": n_sub, "mae_hybrid": mae_h, "mae_persist": mae_p, "bias_hybrid": bias_h, "bias_persist": bias_p}

        # Stratification by predicted state y_hat
        hypo_pred = yh < 70.0
        target_pred = (yh >= 70.0) & (yh <= 180.0)
        hyper_pred = yh > 180.0

        strat_pred = {}
        for r_name, mask in [("Pred Hypo (<70)", hypo_pred), ("Pred Cible (70-180)", target_pred), ("Pred Hyper (>180)", hyper_pred)]:
            n_sub = int(np.sum(mask))
            if n_sub > 0:
                mae_h = round(float(np.mean(np.abs(yt[mask] - yh[mask]))), 2)
                mae_p = round(float(np.mean(np.abs(yt[mask] - ype[mask]))), 2)
                bias_h = round(float(np.mean(yh[mask] - yt[mask])), 2)
                bias_p = round(float(np.mean(ype[mask] - yt[mask])), 2)
                strat_pred[r_name] = {"N": n_sub, "mae_hybrid": mae_h, "mae_persist": mae_p, "bias_hybrid": bias_h, "bias_persist": bias_p}

        eval_data[h_name] = {
            "paired_bootstrap": paired_bs,
            "stratification_at_t0": strat_t0,
            "stratification_by_prediction": strat_pred,
            "metrics_hybrid": calculate_regression_metrics(yt, yh),
            "clarke_hybrid": clarke_error_grid(yt, yh),
            "metrics_physio": calculate_regression_metrics(yt, yp),
            "clarke_physio": clarke_error_grid(yt, yp),
            "metrics_persist": calculate_regression_metrics(yt, ype),
            "clarke_persist": clarke_error_grid(yt, ype)
        }

    # 2. Permutation Feature Importance on Training Set
    # Build train X and y_residual
    X_tr_list, y_tr_list = [], []
    for i in range(12, len(df_train) - 6, 2):
        feat, p_pred = hybrid_twin._extract_features_and_physio_step(df_train, i, 6)
        tgt = float(df_train.iloc[i + 6]['sgv'])
        if not np.isnan(tgt):
            X_tr_list.append(feat)
            y_tr_list.append(tgt - p_pred)
    X_tr = np.array(X_tr_list)
    y_tr = np.array(y_tr_list)

    feature_names = [
        "1. SGV origin (G_t0)",
        "2. Velocity 15 min (dG/dt)",
        "3. Acceleration 30 min",
        "4. Linear vs Physio Divergence",
        "5. Controller IOB",
        "6. Controller COB",
        "7. Circadian Sin(hour)",
        "8. Circadian Cos(hour)",
        "9. Hypo Depth max(0, 70-G)",
        "10. Hyper Excess max(0, G-180)",
        "11. Physio Delta (G_phys - G_0)"
    ]

    r_perm = permutation_importance(hybrid_twin.residual_models["30min"], X_tr, y_tr, n_repeats=10, random_state=42)
    feature_importance = [
        {"feature": feature_names[idx], "importance_mean": round(float(r_perm.importances_mean[idx]), 4), "importance_std": round(float(r_perm.importances_std[idx]), 4)}
        for idx in np.argsort(r_perm.importances_mean)[::-1]
    ]

    # 3. Open-Loop Rollouts: 24h (288 steps) and 72h (864 steps)
    patient_rollout = VirtualPatient(calibrated_params=calib, seed=42)
    
    # 24h rollout
    rollout_24h_real = df_test.iloc[:288]['sgv'].values
    rollout_24h_sim = []
    patient_rollout.reset(start_bg=float(rollout_24h_real[0]), seed=42)
    for s in range(288):
        row = df_test.iloc[s]
        dt = pd.to_datetime(row['datetime'])
        bg, _ = patient_rollout.step(
            hour_of_day=dt.hour + dt.minute / 60.0,
            basal_rate_delivered=float(row.get('basal', 0.85)),
            bolus_delivered=float(row.get('bolus', 0.0)),
            carbs_consumed=float(row.get('carbs', 0.0))
        )
        rollout_24h_sim.append(bg)
    r24_real = np.array(rollout_24h_real)
    r24_sim = np.array(rollout_24h_sim)

    # 72h rollout
    max_steps_72h = min(864, len(df_test))
    rollout_72h_real = df_test.iloc[:max_steps_72h]['sgv'].values
    rollout_72h_sim = []
    patient_rollout.reset(start_bg=float(rollout_72h_real[0]), seed=42)
    for s in range(max_steps_72h):
        row = df_test.iloc[s]
        dt = pd.to_datetime(row['datetime'])
        bg, _ = patient_rollout.step(
            hour_of_day=dt.hour + dt.minute / 60.0,
            basal_rate_delivered=float(row.get('basal', 0.85)),
            bolus_delivered=float(row.get('bolus', 0.0)),
            carbs_consumed=float(row.get('carbs', 0.0))
        )
        rollout_72h_sim.append(bg)
    r72_real = np.array(rollout_72h_real)
    r72_sim = np.array(rollout_72h_sim)

    def agp_summary(arr: np.ndarray) -> Dict[str, float]:
        return {
            "mean": round(float(np.mean(arr)), 1),
            "cv_pct": round(float((np.std(arr) / np.mean(arr)) * 100.0), 1),
            "tir_70_180": round(float(np.mean((arr >= 70.0) & (arr <= 180.0)) * 100.0), 1),
            "tbr_under_70": round(float(np.mean(arr < 70.0) * 100.0), 1),
            "tbr_under_54": round(float(np.mean(arr < 54.0) * 100.0), 1),
            "tar_over_180": round(float(np.mean(arr > 180.0) * 100.0), 1),
            "p10": round(float(np.percentile(arr, 10)), 1),
            "p25": round(float(np.percentile(arr, 25)), 1),
            "p50": round(float(np.percentile(arr, 50)), 1),
            "p75": round(float(np.percentile(arr, 75)), 1),
            "p90": round(float(np.percentile(arr, 90)), 1)
        }

    rollout_comparison = {
        "rollout_24h": {"real": agp_summary(r24_real), "simulated": agp_summary(r24_sim)},
        "rollout_72h": {"real": agp_summary(r72_real), "simulated": agp_summary(r72_sim)}
    }

    # 4. Trajectory validation by event (Corrections & Meals)
    fasting_ev = extract_clean_fasting_events(df_test, min_duration_steps=12)
    meal_ev = extract_clean_meal_events(df_test, post_meal_steps=24)

    event_trajectories = {
        "corrections": [],
        "meals": []
    }
    for ev in fasting_ev[:3]:
        sub = ev["window_df"]
        event_trajectories["corrections"].append({
            "datetime": ev["start_datetime"],
            "observed_start": round(ev["sgv_start"], 1),
            "observed_nadir": round(float(sub['sgv'].min()), 1),
            "observed_drop": round(ev["delta_sgv"], 1),
            "mean_iob": round(ev["mean_iob"], 2),
            "simulated_drop": round(-ev["mean_iob"] * 32.0, 1)
        })

    for m in meal_ev[:3]:
        sub = m["window_df"]
        event_trajectories["meals"].append({
            "datetime": m["datetime"],
            "carbs": m["carbs"],
            "bolus": m["bolus"],
            "baseline": round(m["baseline_sgv"], 1),
            "observed_peak": round(m["peak_sgv"], 1),
            "observed_excursion": round(m["excursion"], 1),
            "simulated_expected_excursion": round(max(0.0, (m["carbs"] / 8.0 - m["bolus"]) * 32.0), 1)
        })

    # Assemble deep report
    output = {
        "paired_bootstrap_evaluation": eval_data,
        "feature_importance": feature_importance,
        "rollout_comparison": rollout_comparison,
        "event_trajectories": event_trajectories,
        "calibrated_params_diagnostics": calib["diagnostics"]
    }

    out_file = os.path.join(current_dir, "deep_analysis_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\nAnalyse clinique approfondie terminée. Résultats enregistrés dans deep_analysis_results.json")
    return output

if __name__ == "__main__":
    run_deep_analysis()
