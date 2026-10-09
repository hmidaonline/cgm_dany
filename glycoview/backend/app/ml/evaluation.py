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
        "persistence": {"name": "Persistance (T-0)", "preds": preds_pers},
        "linear": {"name": "Extrapolation Linéaire", "preds": preds_lin},
        "lightgbm": {"name": "LightGBM (Gradient Boosting)", "preds": preds_lgb},
        "deep": {"name": "Deep Learning (GRU / ResNet)", "preds": preds_deep},
        "aaps": {"name": "AAPS Loop PredBGs", "preds": preds_aaps},
    }

    report: Dict[str, Any] = {
        "status": "success",
        "sample_counts": {
            "total": n,
            "train": len(train_df),
            "test": len(test_df)
        },
        "horizons": TARGET_HORIZONS,
        "models": {},
        "feature_importance": lgb_model.feature_importances_
    }

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

            horizon_results[f"{h}m"] = {
                **reg_metrics,
                "clarke": clarke_metrics
            }

        report["models"][key] = {
            "name": name,
            "horizons": horizon_results
        }

    return report
