import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_glycemic_metrics(df: pd.DataFrame, target_low: int = 70, target_high: int = 180) -> Dict[str, Any]:
    """Calculate standard glycemic metrics from a dataframe of SGV values."""
    if df.empty or "sgv" not in df.columns:
        return {}

    # Drop nulls for calculation
    sgv = df["sgv"].dropna()
    if len(sgv) == 0:
        return {}

    total_readings = len(sgv)
    
    # Time in Ranges (TIR, TAR, TBR)
    very_low = len(sgv[sgv < 54])
    low = len(sgv[(sgv >= 54) & (sgv < target_low)])
    in_range = len(sgv[(sgv >= target_low) & (sgv <= target_high)])
    high = len(sgv[(sgv > target_high) & (sgv <= 250)])
    very_high = len(sgv[sgv > 250])

    # Percentages
    pct_very_low = (very_low / total_readings) * 100
    pct_low = (low / total_readings) * 100
    pct_in_range = (in_range / total_readings) * 100
    pct_high = (high / total_readings) * 100
    pct_very_high = (very_high / total_readings) * 100

    # Mean and SD
    mean_sgv = sgv.mean()
    sd_sgv = sgv.std()
    
    # CV (Coefficient of Variation)
    cv = (sd_sgv / mean_sgv) * 100 if mean_sgv > 0 else 0

    import datetime
    
    # GMI (Glucose Management Indicator) - equivalent to estimated HbA1c
    # Formula: GMI (%) = 3.31 + (0.02392 * mean_glucose_in_mg_dl)
    gmi = 3.31 + (0.02392 * mean_sgv)
    
    # Calculate daily statistics
    df_daily = df.copy()
    # Add a date string column (YYYY-MM-DD) based on local timezone if possible, here using UTC date
    df_daily['date_str'] = df_daily.index.strftime('%Y-%m-%d')
    
    daily_stats = []
    grouped = df_daily.groupby('date_str')
    for date, group in grouped:
        sgv_day = group['sgv'].dropna()
        if len(sgv_day) > 0:
            tot = len(sgv_day)
            low_pct = len(sgv_day[sgv_day < target_low]) / tot * 100
            in_pct = len(sgv_day[(sgv_day >= target_low) & (sgv_day <= target_high)]) / tot * 100
            high_pct = len(sgv_day[sgv_day > target_high]) / tot * 100
            
            daily_stats.append({
                "date": date,
                "low": round(low_pct, 1),
                "target": round(in_pct, 1),
                "high": round(high_pct, 1)
            })
            
    # Sort daily stats descending (newest first)
    daily_stats.reverse()

    return {
        "tir": round(pct_in_range, 1),
        "tar": round(pct_high + pct_very_high, 1),
        "tbr": round(pct_low + pct_very_low, 1),
        "details": {
            "very_low": round(pct_very_low, 1),
            "low": round(pct_low, 1),
            "target": round(pct_in_range, 1),
            "high": round(pct_high, 1),
            "very_high": round(pct_very_high, 1),
        },
        "mean": round(mean_sgv, 1),
        "sd": round(sd_sgv, 1),
        "cv": round(cv, 1),
        "gmi": round(gmi, 1),
        "readings_count": total_readings,
        "daily": daily_stats
    }
