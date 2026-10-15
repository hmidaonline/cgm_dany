import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from sklearn.ensemble import HistGradientBoostingRegressor
from app.ml.rl.simulator.virtual_patient import VirtualPatient

class HybridDigitalTwin:
    """
    Hybrid Digital Twin combining:
    1. Mechanistic Physiological PK/PD simulation (VirtualPatient with calibrated ISF/CR/DIA/EGP).
    2. Learned Non-Linear Residual Corrector (HistGradientBoosting on training residuals)
       capturing sensor inertia, immediate momentum, and eliminating regime-specific systematic bias.
    """
    def __init__(self, calibrated_params: Dict[str, Any]):
        self.calibrated_params = calibrated_params
        self.patient = VirtualPatient(calibrated_params=calibrated_params, seed=42)
        # Residual non-linear correctors for 30min and 60min horizons
        self.residual_models: Dict[str, HistGradientBoostingRegressor] = {
            "30min": HistGradientBoostingRegressor(max_iter=100, max_depth=4, l2_regularization=5.0, random_state=42),
            "60min": HistGradientBoostingRegressor(max_iter=100, max_depth=4, l2_regularization=10.0, random_state=42)
        }
        self.is_fitted: bool = False

    def _extract_features_and_physio_step(
        self,
        df: pd.DataFrame,
        i: int,
        h_steps: int
    ) -> Tuple[np.ndarray, float]:
        origin_sgv = float(df.iloc[i]['sgv'])
        dt = pd.to_datetime(df.iloc[i]['datetime'])
        hour = dt.hour + dt.minute / 60.0

        # Velocity over past 15 min (3 steps) and past 30 min (6 steps)
        past_3_sgv = float(df.iloc[max(0, i - 3)]['sgv'])
        past_6_sgv = float(df.iloc[max(0, i - 6)]['sgv'])
        velocity_15 = (origin_sgv - past_3_sgv) / 15.0
        accel_30 = (velocity_15 - (past_3_sgv - past_6_sgv) / 15.0) / 15.0

        iob = float(df.iloc[i].get('iob', 0.0))
        cob = float(df.iloc[i].get('cob', 0.0))

        # Reset patient to origin point and pre-warm history
        self.patient.reset(start_bg=origin_sgv, start_iob=iob, start_cob=cob, seed=42 + i)
        lookback = min(i, 36)
        for k in range(lookback):
            idx_past = i - 1 - k
            self.patient.past_boluses[k] = float(df.iloc[idx_past].get('bolus', 0.0))
            self.patient.past_carbs[k] = (float(df.iloc[idx_past].get('carbs', 0.0)), "normal")

        # Roll forward h_steps with actual delivered insulin and carbs
        sim_bg = origin_sgv
        for step_offset in range(1, h_steps + 1):
            row = df.iloc[i + step_offset]
            h_curr = (hour + (step_offset * 5.0) / 60.0) % 24.0
            b_deliv = float(row.get('bolus', 0.0))
            c_deliv = float(row.get('carbs', 0.0))
            basal_deliv = float(row.get('basal', 0.85))

            sim_bg, _ = self.patient.step(
                hour_of_day=h_curr,
                basal_rate_delivered=basal_deliv,
                bolus_delivered=b_deliv,
                carbs_consumed=c_deliv,
                carb_speed="normal"
            )

        physio_delta = sim_bg - origin_sgv
        linear_projection = origin_sgv + velocity_15 * (h_steps * 5.0) * 0.75
        hypo_depth = max(0.0, 70.0 - origin_sgv)
        hyper_excess = max(0.0, origin_sgv - 180.0)

        features = np.array([
            origin_sgv,
            velocity_15,
            accel_30,
            linear_projection - sim_bg, # divergence between linear momentum and PK/PD simulation
            iob,
            cob,
            np.sin(2.0 * np.pi * hour / 24.0),
            np.cos(2.0 * np.pi * hour / 24.0),
            hypo_depth,
            hyper_excess,
            physio_delta
        ], dtype=float)

        return features, sim_bg

    def fit_residuals(self, df_train: pd.DataFrame, step_stride: int = 2):
        df = df_train.reset_index(drop=True)
        n = len(df)
        horizons = {"30min": 6, "60min": 12}

        for h_name, h_steps in horizons.items():
            X_list = []
            y_res_list = []

            for i in range(12, n - h_steps, step_stride):
                origin_sgv = float(df.iloc[i]['sgv'])
                target_sgv = float(df.iloc[i + h_steps]['sgv'])
                if np.isnan(origin_sgv) or np.isnan(target_sgv):
                    continue

                feat, physio_pred = self._extract_features_and_physio_step(df, i, h_steps)
                residual = target_sgv - physio_pred
                X_list.append(feat)
                y_res_list.append(residual)

            if len(X_list) > 30:
                X = np.array(X_list)
                y_res = np.array(y_res_list)
                self.residual_models[h_name].fit(X, y_res)

        self.is_fitted = True

    def predict(
        self,
        df: pd.DataFrame,
        i: int,
        h_name: str,
        h_steps: int
    ) -> Tuple[float, float, float]:
        feat, physio_pred = self._extract_features_and_physio_step(df, i, h_steps)
        if self.is_fitted and h_name in self.residual_models:
            res_corr = float(self.residual_models[h_name].predict(feat.reshape(1, -1))[0])
            # Allow residual corrector to compensate for unannounced absorption and closed-loop bias
            res_corr = float(np.clip(res_corr, -100.0, 100.0))
        else:
            res_corr = 0.0

        hybrid_pred = float(np.clip(physio_pred + res_corr, 30.0, 400.0))
        return hybrid_pred, physio_pred, res_corr
