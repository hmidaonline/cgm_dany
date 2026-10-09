import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

from app.ml.features import prepare_ml_dataset, FEATURE_COLUMNS, TARGET_HORIZONS
from app.ml.lightgbm_model import LightGBMPredictor
from app.ml.deep_models import DeepPredictor

def insulin_iob_decay(t_minutes: float, dia_hours: float = 5.0, peak_minutes: float = 55.0) -> float:
    """
    Standard OpenAPS/Nightscout exponential insulin decay curve.
    Returns fraction of insulin remaining active at t_minutes.
    """
    if t_minutes <= 0:
        return 1.0
    if t_minutes >= dia_hours * 60.0:
        return 0.0
    
    tau = peak_minutes * (1.0 - peak_minutes / (dia_hours * 60.0)) / (1.0 - 2.0 * peak_minutes / (dia_hours * 60.0))
    a = 2.0 * tau / (dia_hours * 60.0)
    S = 1.0 / (1.0 - a + (a - 1.0) * np.exp(-dia_hours * 60.0 / tau))
    t = t_minutes
    return float(1.0 - S * (1.0 - a) * (t / (dia_hours * 60.0)) - S * (a - 1.0) * np.exp(-t / tau))

def carb_cob_decay(t_minutes: float, duration_minutes: float = 180.0, peak_minutes: float = 45.0) -> float:
    """
    Standard carb absorption curve.
    Returns fraction of carbs remaining to absorb at t_minutes.
    """
    if t_minutes <= 0:
        return 1.0
    if t_minutes >= duration_minutes:
        return 0.0
    
    # Linear-quadratic absorption profile
    if t_minutes <= peak_minutes:
        absorbed_fraction = 0.5 * (t_minutes / peak_minutes) ** 2 * (peak_minutes / duration_minutes)
    else:
        absorbed_fraction = (t_minutes - 0.5 * peak_minutes) / duration_minutes
    return float(np.clip(1.0 - absorbed_fraction, 0.0, 1.0))

def simulate_what_if_scenario(
    df_raw: pd.DataFrame,
    lgb_model: LightGBMPredictor,
    deep_model: DeepPredictor,
    bolus_u: float = 0.0,
    carbs_g: float = 0.0,
    sensitivity_factor: float = 1.0,  # <1.0 = stress/resistance, >1.0 = physical activity/exercise
    model_type: str = "lightgbm",
    horizons: List[int] = TARGET_HORIZONS
) -> Dict[str, Any]:
    """
    Simulates a 'What-If' clinical scenario on the latest data point.
    Calculates physiological impact of extra insulin, carbs, and stress/activity on glucose trajectory.
    """
    df_feat, feature_cols, target_cols = prepare_ml_dataset(df_raw)
    
    if df_feat.empty:
        return {"status": "error", "message": "Données insuffisantes pour la simulation"}

    latest_row = df_feat.iloc[-1].copy()
    latest_dt = pd.to_datetime(latest_row['datetime'])
    base_sgv = float(latest_row['sgv'])
    base_iob = float(latest_row.get('iob', 0.0))
    base_cob = float(latest_row.get('cob', 0.0))

    # 1. Compute baseline prediction (without simulation inputs)
    if model_type == "deep" and deep_model.is_trained:
        base_preds_raw = deep_model.predict(df_feat.tail(1), feature_cols)
    else:
        base_preds_raw = lgb_model.predict(df_feat.tail(1), feature_cols)

    baseline_points = [{
        "datetime": latest_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        "horizon_min": 0,
        "sgv": round(base_sgv, 1)
    }]

    for h in horizons:
        val = float(base_preds_raw[h]["p50"][-1])
        dt_str = (latest_dt + pd.Timedelta(minutes=h)).strftime('%Y-%m-%dT%H:%M:%S')
        baseline_points.append({
            "datetime": dt_str,
            "horizon_min": h,
            "sgv": round(val, 1)
        })

    # 2. Compute physiological impact of simulated parameters
    # Default parameters: ISF (Insulin Sensitivity Factor) ~ 40 mg/dL per Unit, CR (Carb Ratio) ~ 10 g per Unit (4 mg/dL per gram)
    default_isf = 40.0  # mg/dL drop per 1 Unit of insulin
    default_cr_impact = 3.5  # mg/dL rise per 1 gram of carbs

    # Stress effect increases baseline hepatic glucose release (+5 to +30 mg/dL depending on stress factor < 1.0)
    # Physical activity increases insulin sensitivity (sensitivity_factor > 1.0)
    effective_isf = default_isf * sensitivity_factor
    stress_hepatic_boost = max(0.0, (1.0 - sensitivity_factor) * 45.0)

    simulated_points = [{
        "datetime": latest_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        "horizon_min": 0,
        "sgv": round(base_sgv, 1),
        "delta_from_baseline": 0.0,
        "iob_added": 0.0,
        "cob_added": 0.0
    }]

    # Build continuous simulation trajectory for +5m to +120m
    future_mins = list(range(5, 125, 5))
    
    # Interpolate baseline continuous curve
    base_mins = [0] + horizons
    base_vals = [base_sgv] + [float(base_preds_raw[h]["p50"][-1]) for h in horizons]
    interp_base = np.interp(future_mins, base_mins, base_vals)

    min_sim_sgv = base_sgv
    max_sim_sgv = base_sgv

    for m, base_val in zip(future_mins, interp_base):
        dt_str = (latest_dt + pd.Timedelta(minutes=m)).strftime('%Y-%m-%dT%H:%M:%S')

        # Active insulin remaining from added bolus
        iob_remaining_frac = insulin_iob_decay(m)
        iob_absorbed_frac = 1.0 - iob_remaining_frac
        insulin_glucose_drop = bolus_u * effective_isf * iob_absorbed_frac

        # Active carbs absorbed from added carbs
        cob_remaining_frac = carb_cob_decay(m)
        cob_absorbed_frac = 1.0 - cob_remaining_frac
        carbs_glucose_rise = carbs_g * default_cr_impact * cob_absorbed_frac

        # Stress hepatic glucose release curve
        stress_rise = stress_hepatic_boost * (1.0 - np.exp(-m / 40.0))

        # Net simulated glucose
        net_delta = carbs_glucose_rise - insulin_glucose_drop + stress_rise
        sim_sgv = float(np.clip(base_val + net_delta, 30.0, 400.0))

        min_sim_sgv = min(min_sim_sgv, sim_sgv)
        max_sim_sgv = max(max_sim_sgv, sim_sgv)

        simulated_points.append({
            "datetime": dt_str,
            "horizon_min": m,
            "sgv": round(sim_sgv, 1),
            "baseline_sgv": round(float(base_val), 1),
            "delta_from_baseline": round(float(net_delta), 1),
            "iob_added": round(float(bolus_u * iob_remaining_frac), 2),
            "cob_added": round(float(carbs_g * cob_remaining_frac), 1)
        })

    # Summary analysis of scenario
    final_point = simulated_points[-1]
    peak_delta = max(simulated_points, key=lambda x: abs(x["delta_from_baseline"]))

    return {
        "status": "success",
        "inputs": {
            "bolus_u": bolus_u,
            "carbs_g": carbs_g,
            "sensitivity_factor": sensitivity_factor,
            "model_type": model_type
        },
        "latest_sgv": round(base_sgv, 1),
        "baseline_trajectory": baseline_points,
        "simulated_trajectory": simulated_points,
        "impact_summary": {
            "min_projected_sgv": round(min_sim_sgv, 1),
            "max_projected_sgv": round(max_sim_sgv, 1),
            "final_projected_sgv_120m": round(final_point["sgv"], 1),
            "max_impact_delta": round(peak_delta["delta_from_baseline"], 1),
            "max_impact_horizon_min": peak_delta["horizon_min"],
            "risk_hypo": min_sim_sgv < 70.0,
            "risk_hyper": max_sim_sgv > 180.0
        }
    }
