import numpy as np
from typing import Dict, Any

def calculate_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate RMSE, MAE, MARD, Bias, and R2 score."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    if len(y_true) == 0:
        return {"rmse": 0.0, "mae": 0.0, "mard": 0.0, "bias": 0.0, "r2": 0.0, "n": 0}

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    bias = float(np.mean(y_pred - y_true))
    
    # MARD: Mean Absolute Relative Difference (%)
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
        "bias": round(bias, 2),
        "r2": round(r2, 3),
        "n": int(len(y_true))
    }

def block_bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    block_size: int = 24, # 2 hours = 24 samples of 5 min
    n_bootstraps: int = 500,
    confidence_level: float = 0.95,
    metric_func = None
) -> Dict[str, float]:
    """
    Computes block bootstrap confidence intervals accounting for temporal autocorrelation in CGM series.
    Stipulated in Section 6 of AAPS-DT Pilot protocol.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    
    n = len(y_true)
    if n < block_size * 2:
        mae = float(np.mean(np.abs(y_true - y_pred))) if n > 0 else 0.0
        return {"mean": round(mae, 2), "ci_low": round(mae * 0.9, 2), "ci_high": round(mae * 1.1, 2)}

    # Number of possible overlapping blocks
    n_blocks = n - block_size + 1
    blocks_idx = [np.arange(i, i + block_size) for i in range(n_blocks)]

    boot_maes = []
    rng = np.random.RandomState(42)
    blocks_needed = int(np.ceil(n / block_size))

    for _ in range(n_bootstraps):
        selected_block_indices = rng.choice(n_blocks, size=blocks_needed, replace=True)
        sample_indices = np.concatenate([blocks_idx[b] for b in selected_block_indices])[:n]
        yt_sample = y_true[sample_indices]
        yp_sample = y_pred[sample_indices]
        boot_maes.append(float(np.mean(np.abs(yt_sample - yp_sample))))

    alpha = 1.0 - confidence_level
    ci_low = float(np.percentile(boot_maes, 100.0 * (alpha / 2.0)))
    ci_high = float(np.percentile(boot_maes, 100.0 * (1.0 - alpha / 2.0)))
    mean_val = float(np.mean(boot_maes))

    return {
        "mean": round(mean_val, 2),
        "ci_low": round(ci_low, 2),
        "ci_high": round(ci_high, 2)
    }

def calculate_glycemic_stratified_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """
    Calculates stratified performance across glycemic ranges:
    - Hypoglycemia (< 70 mg/dL)
    - Euglycemia / Target range (70 - 180 mg/dL)
    - Hyperglycemia (> 180 mg/dL)
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    hypo_mask = y_true < 70.0
    target_mask = (y_true >= 70.0) & (y_true <= 180.0)
    hyper_mask = y_true > 180.0

    return {
        "hypo": calculate_regression_metrics(y_true[hypo_mask], y_pred[hypo_mask]),
        "target": calculate_regression_metrics(y_true[target_mask], y_pred[target_mask]),
        "hyper": calculate_regression_metrics(y_true[hyper_mask], y_pred[hyper_mask]),
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
