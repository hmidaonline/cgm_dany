import numpy as np
import pandas as pd
from typing import Dict, List, Any

from app.ml.features import prepare_ml_dataset, FEATURE_COLUMNS, TARGET_HORIZONS
from app.ml.baselines import PersistenceBaseline, LinearExtrapolationBaseline
from app.ml.lightgbm_model import LightGBMPredictor
from app.ml.deep_models import DeepPredictor
from app.ml.aaps_predictions import AAPSPredictor
from app.ml.metrics import calculate_regression_metrics, clarke_error_grid

def evaluate_all_models(df_raw: pd.DataFrame) -> Dict[str, Any]:
    """
    Chronological train/val/test evaluation benchmark comparing all prediction models:
    - Persistence Baseline
    - Linear Extrapolation
    - LightGBM (Gradient Boosted Trees)
    - Deep Learning (GRU / Neural Net)
    - AAPS Loop PredBGs
    
    Prevents temporal data leakage using a 2-hour purge gap between splits.
    """
    df_feat, feature_cols, target_cols = prepare_ml_dataset(df_raw)
    
    if df_feat.empty or len(df_feat) < 100:
        return {
            "status": "error",
            "message": "Insuffisant de données pour l'évaluation des modèles (minimum 100 points requis).",
            "models": {}
        }

    n = len(df_feat)
    train_end = int(n * 0.60)
    # Purge window of 2 hours = 24 steps
    purge_steps = 24
    val_start = train_end + purge_steps
    val_end = val_start + int(n * 0.20)
    test_start = val_end + purge_steps

    train_df = df_feat.iloc[:train_end].reset_index(drop=True)
    test_df = df_feat.iloc[test_start:].reset_index(drop=True)

    if len(test_df) < 20:
        test_df = df_feat.iloc[train_end:].reset_index(drop=True)

    # Instantiate models
    lgb_model = LightGBMPredictor()
    lgb_model.fit(train_df, feature_cols)

    deep_model = DeepPredictor()
    deep_model.fit(train_df, feature_cols)

    persistence_model = PersistenceBaseline()
    linear_model = LinearExtrapolationBaseline()
    aaps_model = AAPSPredictor()

    # Generate predictions on Test dataset
    preds_pers = persistence_model.predict(test_df, TARGET_HORIZONS)
    preds_lin = linear_model.predict(test_df, TARGET_HORIZONS)
    preds_lgb = lgb_model.predict(test_df, feature_cols)
    preds_deep = deep_model.predict(test_df, feature_cols)
    preds_aaps = aaps_model.predict(test_df, TARGET_HORIZONS)

    models_eval = {
        "persistence": {"name": "1. Persistance (T-0)", "preds": preds_pers},
        "linear": {"name": "2. Réf. Temporelle Simple (Linéaire)", "preds": preds_lin},
        "aaps": {"name": "3. Modèle Physiologique (AAPS/Oref0)", "preds": preds_aaps},
        "lightgbm": {"name": "4. Modèle Hybride Personnalisé (LightGBM)", "preds": preds_lgb},
        "deep": {"name": "4b. Modèle Hybride Deep Learning (GRU)", "preds": preds_deep},
    }

    report: Dict[str, Any] = {
        "status": "success",
        "protocol_header": {
            "title": "AAPS-DT Pilot v1.0",
            "date": "12 octobre 2026",
            "institution": "Hôpital Militaire Oued Eddahab - Agadir",
            "patient_subject": "Ahmed DANY (Étude N-of-1)",
            "principal_investigator": "Médecin Commandant Lhoussaine Abainou",
            "primary_endpoint": "MAE à 30 minutes avec IC à 95% (Block Bootstrap)",
            "benchmark_rule": "Supériorité requise face au modèle de persistance (Delta MAE > 0)"
        },
        "sample_counts": {
            "total": n,
            "train": len(train_df),
            "test": len(test_df),
            "purge_gap_hours": 2
        },
        "horizons": TARGET_HORIZONS,
        "models": {},
        "primary_endpoint_summary": {},
        "feature_importance": lgb_model.feature_importances_
    }

    # First compute persistence MAE at 30 min as baseline reference
    target_30m = test_df['target_30m'].values if 'target_30m' in test_df else test_df['sgv'].values
    pers_30m_pred = preds_pers[30]["p50"] if isinstance(preds_pers[30], dict) else preds_pers[30]
    pers_30m_mae = float(np.mean(np.abs(target_30m - pers_30m_pred)))

    for key, model_info in models_eval.items():
        name = model_info["name"]
        model_preds = model_info["preds"]
        
        horizon_results = {}
        for h in TARGET_HORIZONS:
            target_col = f'target_{h}m'
            y_true = test_df[target_col].values
            
            p_dict = model_preds[h]
            y_pred = p_dict["p50"] if isinstance(p_dict, dict) else p_dict

            reg_metrics = calculate_regression_metrics(y_true, y_pred)
            clarke_metrics = clarke_error_grid(y_true, y_pred)
            from app.ml.metrics import block_bootstrap_ci, calculate_glycemic_stratified_metrics
            ci_95 = block_bootstrap_ci(y_true, y_pred, block_size=24, n_bootstraps=300)
            stratified = calculate_glycemic_stratified_metrics(y_true, y_pred)

            # Delta MAE vs persistence baseline (filtering NaNs)
            p_ref_h = preds_pers[h]["p50"] if isinstance(preds_pers[h], dict) else preds_pers[h]
            mask_h = ~np.isnan(y_true) & ~np.isnan(p_ref_h)
            pers_mae_h = float(np.mean(np.abs(y_true[mask_h] - p_ref_h[mask_h]))) if np.any(mask_h) else 0.0
            
            delta_mae_pct = round(((pers_mae_h - reg_metrics["mae"]) / max(pers_mae_h, 0.001)) * 100.0, 1)

            horizon_results[f"{h}m"] = {
                **reg_metrics,
                "ci_95": ci_95,
                "delta_mae_pct_vs_persistence": delta_mae_pct,
                "clarke": clarke_metrics,
                "stratified": stratified
            }

        report["models"][key] = {
            "name": name,
            "horizons": horizon_results
        }

    # Primary endpoint synthesis (30 min)
    primary_models = {}
    pers_30_ref = report["models"]["persistence"]["horizons"]["30m"]["mae"]
    for k, v in report["models"].items():
        h30 = v["horizons"]["30m"]
        primary_models[k] = {
            "name": v["name"],
            "mae": h30["mae"],
            "ci_95": f"[{h30['ci_95']['ci_low']} - {h30['ci_95']['ci_high']}]",
            "delta_mae_pct": h30["delta_mae_pct_vs_persistence"],
            "rmse": h30["rmse"],
            "bias": h30["bias"],
            "clarke_ab": h30["clarke"]["zone_ab"],
            "beats_persistence": bool(h30["mae"] < pers_30_ref)
        }
    report["primary_endpoint_summary"] = {
        "horizon": "30 minutes",
        "persistence_baseline_mae": pers_30_ref,
        "results": primary_models
    }

    return report
