import numpy as np
from typing import Dict, Any

def calculate_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate RMSE, MAE, MARD, and R2 score."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    if len(y_true) == 0:
        return {"rmse": 0.0, "mae": 0.0, "mard": 0.0, "r2": 0.0}

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    
    # MARD: Mean Absolute Relative Difference (%)
    # Avoid division by zero by clipping denominator to 1
    safe_true = np.clip(y_true, 1.0, None)
    mard = float(np.mean(np.abs(y_true - y_pred) / safe_true) * 100.0)

    # R2 score
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    return {
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "mard": round(mard, 2),
        "r2": round(r2, 3),
    }

def clarke_error_grid(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Clarke Error Grid Analysis (EGA) for blood glucose measurements.
    
    Zones:
    - Zone A: Clinically accurate (within 20% of reference or both <= 70 mg/dL)
    - Zone B: Benign errors (outside 20% but would not lead to inappropriate treatment)
    - Zone C: Overcorrection (would result in unnecessary treatment)
    - Zone D: Dangerous failure to detect hypoglycemia or hyperglycemia
    - Zone E: Erroneous treatment (opposite of correct treatment)
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    total = len(y_true)
    if total == 0:
        return {"zone_a": 0.0, "zone_b": 0.0, "zone_c": 0.0, "zone_d": 0.0, "zone_e": 0.0, "zone_ab": 0.0}

    zones = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}

    for ref, pred in zip(y_true, y_pred):
        # Zone A: within 20% or both <= 70
        if (ref <= 70 and pred <= 70) or (abs(ref - pred) <= 0.20 * ref):
            zones["A"] += 1
        # Zone E: Opposite treatment
        elif (ref >= 180 and pred <= 70) or (ref <= 70 and pred >= 180):
            zones["E"] += 1
        # Zone C: Unnecessary corrections
        elif (70 <= ref <= 180 and pred > 180) or (70 <= ref <= 180 and pred < 70):
            if (ref >= 130 and pred > 180) or (ref <= 100 and pred < 70):
                zones["C"] += 1
            else:
                zones["B"] += 1
        # Zone D: Failure to detect
        elif (ref < 70 and pred > 70) or (ref > 240 and 70 <= pred <= 180):
            zones["D"] += 1
        else:
            zones["B"] += 1

    pct_a = round((zones["A"] / total) * 100.0, 1)
    pct_b = round((zones["B"] / total) * 100.0, 1)
    pct_c = round((zones["C"] / total) * 100.0, 1)
    pct_d = round((zones["D"] / total) * 100.0, 1)
    pct_e = round((zones["E"] / total) * 100.0, 1)
    pct_ab = round(pct_a + pct_b, 1)

    return {
        "zone_a": pct_a,
        "zone_b": pct_b,
        "zone_c": pct_c,
        "zone_d": pct_d,
        "zone_e": pct_e,
        "zone_ab": pct_ab,
        "sample_count": total
    }
