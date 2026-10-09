import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional

from app.ml.digital_twin.model import DigitalTwinModel
from app.ml.metrics import calculate_regression_metrics, clarke_error_grid

def replay_past_day(
    df_raw: pd.DataFrame,
    twin_model: DigitalTwinModel,
    target_date: str
) -> Dict[str, Any]:
    """
    Replays a full past 24-hour day using the Digital Twin.
    Compares real recorded SGV against digital twin simulated trajectory.
    """
    if df_raw.empty or 'datetime' not in df_raw.columns:
        return {"status": "error", "message": "Données absentes pour le rejeu de journée"}

    data = df_raw.copy()
    data['date_str'] = pd.to_datetime(data['datetime']).dt.strftime('%Y-%m-%d')
    day_df = data[data['date_str'] == target_date].sort_values('datetime').reset_index(drop=True)

    if day_df.empty or len(day_df) < 12:
        return {
            "status": "error",
            "message": f"Pas assez de données pour la journée du {target_date} (minimum 12 points requis)."
        }

    # Extract initial conditions at 00:00 or first available point
    first_row = day_df.iloc[0]
    start_dt = pd.to_datetime(first_row['datetime'])
    start_sgv = float(first_row['sgv']) if not np.isnan(first_row['sgv']) else 110.0
    start_iob = float(first_row.get('iob', 0.0))
    start_cob = float(first_row.get('cob', 0.0))

    # Align inputs for 288 steps (5-min resolution)
    full_times = [start_dt + pd.Timedelta(minutes=5 * i) for i in range(len(day_df))]
    
    bolus_series = day_df['bolus'].fillna(0.0).values if 'bolus' in day_df.columns else np.zeros(len(day_df))
    carbs_series = day_df['carbs'].fillna(0.0).values if 'carbs' in day_df.columns else np.zeros(len(day_df))
    basal_series = day_df['basal'].fillna(0.8).values if 'basal' in day_df.columns else np.full(len(day_df), 0.8)

    # Run digital twin simulation
    sim_points = twin_model.simulate_trajectory(
        start_sgv=start_sgv,
        start_iob=start_iob,
        start_cob=start_cob,
        bolus_series=list(bolus_series),
        carbs_series=list(carbs_series),
        basal_series=list(basal_series),
        start_datetime=start_dt,
        num_steps=len(day_df)
    )

    # Combine real and simulated series
    combined_timeline = []
    y_true_list = []
    y_pred_list = []

    for idx, row in day_df.iterrows():
        real_val = float(row['sgv']) if not np.isnan(row['sgv']) else None
        sim_val = sim_points[idx]['simulated_sgv']
        p10 = sim_points[idx]['p10']
        p90 = sim_points[idx]['p90']

        if real_val is not None:
            y_true_list.append(real_val)
            y_pred_list.append(sim_val)

        dt_str = pd.to_datetime(row['datetime']).strftime('%Y-%m-%dT%H:%M:%S')
        combined_timeline.append({
            "datetime": dt_str,
            "real_sgv": round(real_val, 1) if real_val is not None else None,
            "simulated_sgv": sim_val,
            "p10": p10,
            "p90": p90,
            "residual": round(real_val - sim_val, 1) if real_val is not None else 0.0,
            "bolus": round(float(row.get('bolus', 0.0)), 2),
            "carbs": round(float(row.get('carbs', 0.0)), 1)
        })

    # Compute regression & clinical safety metrics
    y_true = np.array(y_true_list)
    y_pred = np.array(y_pred_list)

    reg_metrics = calculate_regression_metrics(y_true, y_pred)
    clarke_metrics = clarke_error_grid(y_true, y_pred)

    return {
        "status": "success",
        "date": target_date,
        "metrics": {
            **reg_metrics,
            "clarke": clarke_metrics
        },
        "timeline": combined_timeline
    }
