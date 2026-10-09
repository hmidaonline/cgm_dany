import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import lightgbm as lgb
from sklearn.ensemble import HistGradientBoostingRegressor

from app.ml.features import FEATURE_COLUMNS, TARGET_HORIZONS

class LightGBMPredictor:
    """
    Gradient Boosted Decision Trees predictor for multi-horizon glucose forecasting.
    Includes quantile regressors for confidence intervals (10%, 50%, 90%).
    """
    def __init__(self):
        self.name = "LightGBM (Gradient Boosting)"
        self.horizons = TARGET_HORIZONS
        # Dict mapping horizon -> {"p50": model, "p10": model, "p90": model}
        self.models: Dict[int, Dict[str, Any]] = {}
        self.is_trained = False
        self.feature_importances_: Dict[int, Dict[str, float]] = {}

    def fit(self, train_df: pd.DataFrame, feature_cols: List[str] = FEATURE_COLUMNS):
        """Fit models for each horizon and quantile."""
        X = train_df[feature_cols].values
        
        for h in self.horizons:
            target_col = f'target_{h}m'
            if target_col not in train_df.columns:
                continue
                
            y = train_df[target_col].values
            valid_mask = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
            X_clean, y_clean = X[valid_mask], y[valid_mask]
            
            if len(X_clean) < 10:
                continue

            self.models[h] = {}
            
            # 1. Main model (Mean / Median p50)
            try:
                model_p50 = lgb.LGBMRegressor(
                    n_estimators=150,
                    learning_rate=0.05,
                    num_leaves=31,
                    max_depth=6,
                    random_state=42,
                    verbosity=-1
                )
                model_p50.fit(X_clean, y_clean)
                
                # Quantile models for uncertainty
                model_p10 = lgb.LGBMRegressor(
                    objective='quantile',
                    alpha=0.10,
                    n_estimators=100,
                    learning_rate=0.05,
                    num_leaves=31,
                    random_state=42,
                    verbosity=-1
                )
                model_p10.fit(X_clean, y_clean)

                model_p90 = lgb.LGBMRegressor(
                    objective='quantile',
                    alpha=0.90,
                    n_estimators=100,
                    learning_rate=0.05,
                    num_leaves=31,
                    random_state=42,
                    verbosity=-1
                )
                model_p90.fit(X_clean, y_clean)

                # Store importances
                importances = model_p50.feature_importances_
                tot = sum(importances) if sum(importances) > 0 else 1
                self.feature_importances_[h] = {
                    col: round(float(imp / tot * 100.0), 2)
                    for col, imp in zip(feature_cols, importances)
                }

            except Exception as e:
                # Fallback to Scikit-Learn HistGradientBoostingRegressor if LightGBM has issues
                model_p50 = HistGradientBoostingRegressor(max_iter=100, random_state=42)
                model_p50.fit(X_clean, y_clean)
                
                model_p10 = HistGradientBoostingRegressor(loss='quantile', quantile=0.10, max_iter=80, random_state=42)
                model_p10.fit(X_clean, y_clean)

                model_p90 = HistGradientBoostingRegressor(loss='quantile', quantile=0.90, max_iter=80, random_state=42)
                model_p90.fit(X_clean, y_clean)
                
                self.feature_importances_[h] = {col: 1.0 for col in feature_cols}

            self.models[h]['p50'] = model_p50
            self.models[h]['p10'] = model_p10
            self.models[h]['p90'] = model_p90

        self.is_trained = len(self.models) > 0

    def predict(
        self,
        df: pd.DataFrame,
        feature_cols: List[str] = FEATURE_COLUMNS
    ) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Returns predictions for each horizon:
        {horizon: {"p50": np.array, "p10": np.array, "p90": np.array}}
        """
        if not self.is_trained:
            # Return current SGV persistence as fallback if not trained
            sgv = df['sgv'].values
            return {h: {"p50": sgv, "p10": np.maximum(sgv - 15, 40), "p90": sgv + 15} for h in self.horizons}

        X = df[feature_cols].values
        # Fill NAs in features with 0.0 or median
        X = np.nan_to_num(X, nan=0.0)

        results = {}
        for h in self.horizons:
            if h in self.models:
                p50 = np.clip(self.models[h]['p50'].predict(X), 30.0, 400.0)
                p10 = np.clip(self.models[h]['p10'].predict(X), 30.0, 400.0)
                p90 = np.clip(self.models[h]['p90'].predict(X), 30.0, 400.0)
                # Ensure p10 <= p50 <= p90
                p10 = np.minimum(p10, p50)
                p90 = np.maximum(p90, p50)
                results[h] = {"p50": p50, "p10": p10, "p90": p90}
            else:
                sgv = df['sgv'].values
                results[h] = {"p50": sgv, "p10": sgv - 10, "p90": sgv + 10}

        return results

    def save(self, filepath: str):
        """Save model artifact to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({
            "models": self.models,
            "is_trained": self.is_trained,
            "feature_importances": self.feature_importances_
        }, filepath)

    def load(self, filepath: str) -> bool:
        """Load model artifact from disk."""
        if os.path.exists(filepath):
            data = joblib.load(filepath)
            self.models = data.get("models", {})
            self.is_trained = data.get("is_trained", False)
            self.feature_importances_ = data.get("feature_importances", {})
            return True
        return False
