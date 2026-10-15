import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

def extract_clean_fasting_events(df: pd.DataFrame, min_duration_steps: int = 12) -> List[Dict[str, Any]]:
    """
    Identifies clean fasting / nocturnal windows without carbohydrate interference
    to calibrate insulin sensitivity factor (ISF) and isolate it from closed-loop confounders.
    
    Criteria:
    - cob < 1.5g and carbs == 0 over the entire window
    - active IOB > 0.4 U (presence of measurable insulin action)
    - window length >= min_duration_steps (>= 60 min)
    - nocturnal or undisturbed post-absorptive state
    """
    if df.empty or len(df) < min_duration_steps:
        return []

    events = []
    n = len(df)
    i = 0

    while i < n - min_duration_steps:
        # Check window
        window = df.iloc[i : i + min_duration_steps]
        max_cob = window['cob'].max() if 'cob' in window.columns else 0.0
        sum_carbs = window['carbs'].sum() if 'carbs' in window.columns else 0.0
        mean_iob = window['iob'].mean() if 'iob' in window.columns else 0.0

        if max_cob < 1.5 and sum_carbs == 0.0 and mean_iob >= 0.3:
            # We found a candidate clean fasting window
            # Expand window while conditions hold
            end_idx = i + min_duration_steps
            while end_idx < n:
                next_row = df.iloc[end_idx]
                if next_row.get('cob', 0.0) >= 1.5 or next_row.get('carbs', 0.0) > 0.0:
                    break
                end_idx += 1

            full_window = df.iloc[i:end_idx]
            if len(full_window) >= min_duration_steps:
                start_dt = pd.to_datetime(full_window.iloc[0]['datetime'])
                sgv_start = full_window.iloc[0]['sgv']
                sgv_end = full_window.iloc[-1]['sgv']
                delta_sgv = sgv_end - sgv_start

                # Total insulin delivered in this window (bolus + temp basal above/below scheduled)
                bolus_sum = full_window['bolus'].sum() if 'bolus' in full_window.columns else 0.0
                hour = start_dt.hour + start_dt.minute / 60.0

                events.append({
                    "start_idx": i,
                    "end_idx": end_idx,
                    "length_steps": len(full_window),
                    "start_datetime": str(start_dt),
                    "hour": hour,
                    "sgv_start": float(sgv_start),
                    "sgv_end": float(sgv_end),
                    "delta_sgv": float(delta_sgv),
                    "mean_iob": float(mean_iob),
                    "bolus_sum": float(bolus_sum),
                    "window_df": full_window.copy()
                })
            i = end_idx + 1
        else:
            i += 1

    return events

def extract_clean_meal_events(df: pd.DataFrame, post_meal_steps: int = 36) -> List[Dict[str, Any]]:
    """
    Identifies clean isolated meal events (36 steps = 3 hours post-meal)
    without overlapping second meals to calibrate Carb Ratio (CR) and absorption kinetics.
    
    Criteria:
    - Single carb event >= 15g
    - Bolus present within [-15min, +30min] of meal start
    - No subsequent carb entry > 10g in the next 3 hours
    """
    if df.empty or len(df) < post_meal_steps:
        return []

    events = []
    n = len(df)
    carb_indices = df[df['carbs'] >= 15.0].index.tolist()

    for idx in carb_indices:
        pos = df.index.get_loc(idx)
        if pos < 2 or pos + post_meal_steps >= n:
            continue

        # Check pre-meal baseline (15 min prior)
        pre_meal = df.iloc[pos - 2 : pos]
        # Check post-meal window (3h post meal)
        post_window = df.iloc[pos : pos + post_meal_steps]

        # Ensure no second large meal occurs in the post-meal period (after pos+3)
        secondary_carbs = post_window.iloc[3:]['carbs'].sum()
        if secondary_carbs > 10.0:
            continue

        total_carbs = float(post_window.iloc[:3]['carbs'].sum())
        # Total bolus associated with this meal window
        total_bolus = float(df.iloc[pos - 2 : pos + 4]['bolus'].sum())

        if total_bolus <= 0.2:
            # Unannounced / unbolused meal, useful for pure carb absorption tracking
            is_announced = False
        else:
            is_announced = True

        start_dt = pd.to_datetime(df.iloc[pos]['datetime'])
        baseline_sgv = float(pre_meal['sgv'].mean())
        peak_sgv = float(post_window['sgv'].max())
        min_sgv = float(post_window['sgv'].min())
        end_sgv = float(post_window.iloc[-1]['sgv'])

        events.append({
            "meal_idx": pos,
            "datetime": str(start_dt),
            "hour": start_dt.hour + start_dt.minute / 60.0,
            "carbs": total_carbs,
            "bolus": total_bolus,
            "is_announced": is_announced,
            "baseline_sgv": baseline_sgv,
            "peak_sgv": peak_sgv,
            "excursion": peak_sgv - baseline_sgv,
            "end_sgv": end_sgv,
            "window_df": df.iloc[pos - 2 : pos + post_meal_steps].copy()
        })

    return events
