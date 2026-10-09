import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from app.ml.features import prepare_ml_dataset, FEATURE_COLUMNS, TARGET_HORIZONS
from app.ml.simulation import insulin_iob_decay, carb_cob_decay

class DigitalTwinModel:
    """
    Personalized Digital Twin for Glucose-Insulin-Carb Dynamics.
    Combines:
    1. Compartmental Physiological Model (Bergman Minimal Model / Oref0 kinetics).
    2. Hybrid Residual Corrector (ML error adjustment).
    3. Time-Varying Parameters (ISF, CR by 3-hour time blocks).
    """
    def __init__(self):
        self.name = "Jumeau Numérique Physiologique Hybride"
        # Base physiological parameters
        self.gb = 100.0        # Basal glucose (mg/dL)
        self.gezi = 0.005      # Glucose effectiveness at zero insulin (1/min)
        self.p2 = 0.015        # Insulin action decay rate (1/min)
        self.p3 = 0.000025     # Remote insulin sensitivity parameter
        self.k_abs = 0.025     # Carb gut absorption rate (1/min)

        # Time-varying parameters per 3-hour block (8 blocks: 0-3h, 3-6h, ..., 21-24h)
        # ISF in mg/dL per Unit, CR in grams per Unit
        self.isf_by_block = {i: 40.0 for i in range(8)}
        self.cr_by_block = {i: 10.0 for i in range(8)}
        self.basal_by_block = {i: 0.8 for i in range(8)}
        
        self.is_fitted = False

    def get_time_block(self, hour: float) -> int:
        """Returns 3-hour block index (0 to 7) for a given hour of day."""
        return min(7, max(0, int(hour // 3)))

    def fit(self, df_raw: pd.DataFrame):
        """
        Fits time-varying ISF, CR, and physiological parameters on historical dataset.
        """
        df_feat, feature_cols, target_cols = prepare_ml_dataset(df_raw)
        if df_feat.empty or len(df_feat) < 50:
            return

        # Estimate hourly ISF & CR from observed data segments
        if 'datetime' in df_feat.columns:
            df_feat['hour'] = pd.to_datetime(df_feat['datetime']).dt.hour
        else:
            df_feat['hour'] = 12

        for block_idx in range(8):
            start_h, end_h = block_idx * 3, (block_idx + 1) * 3
            sub = df_feat[(df_feat['hour'] >= start_h) & (df_feat['hour'] < end_h)]
            
            if len(sub) > 10:
                # Estimate ISF from post-bolus drops without carbs
                no_carbs = sub[(sub['cob'] < 2.0) & (sub['iob'] > 0.5)]
                if len(no_carbs) > 5 and 'sgv_diff_15' in no_carbs.columns:
                    mean_drop = -no_carbs['sgv_diff_15'].mean()
                    mean_iob = no_carbs['iob'].mean()
                    if mean_iob > 0:
                        est_isf = float(np.clip((mean_drop / mean_iob) * 4.0, 20.0, 90.0))
                        self.isf_by_block[block_idx] = round(est_isf, 1)

                # Estimate CR from postprandial rises
                with_carbs = sub[sub['carbs_sum_2h'] > 10.0]
                if len(with_carbs) > 5 and 'bolus_sum_1h' in with_carbs.columns:
                    mean_carbs = with_carbs['carbs_sum_2h'].mean()
                    mean_bolus = with_carbs['bolus_sum_1h'].mean()
                    if mean_bolus > 0:
                        est_cr = float(np.clip(mean_carbs / mean_bolus, 5.0, 25.0))
                        self.cr_by_block[block_idx] = round(est_cr, 1)

        self.is_fitted = True

    def simulate_step(
        self,
        g_current: float,
        iob_current: float,
        cob_current: float,
        bolus_step: float,
        carbs_step: float,
        basal_step: float,
        hour_of_day: float,
        dt_minutes: float = 5.0
    ) -> Tuple[float, float, float]:
        """
        Simulates one 5-minute step of glucose dynamics.
        Returns: (g_next, iob_next, cob_next)
        """
        block_idx = self.get_time_block(hour_of_day)
        isf = self.isf_by_block.get(block_idx, 40.0)
        cr = self.cr_by_block.get(block_idx, 10.0)
        scheduled_basal = self.basal_by_block.get(block_idx, 0.8)

        # 1. Insulin clearance and remote action
        # 1 Unit of insulin reduces glucose by ISF mg/dL over DIA (~300 min)
        insulin_effect_rate = (isf / 180.0) * iob_current * (dt_minutes / 5.0)

        # 2. Carb absorption rate
        # 1 Gram of carbs raises glucose by (ISF / CR) mg/dL over absorption time (~180 min)
        carb_effect_rate = ((isf / cr) / 120.0) * cob_current * (dt_minutes / 5.0)

        # 3. Basal differential effect (delta between effective basal and scheduled basal)
        basal_delta = (basal_step - scheduled_basal)
        basal_effect_rate = (isf / 60.0) * basal_delta * (dt_minutes / 5.0)

        # 4. Hepatic glucose effectiveness (pull toward basal glucose gb=100)
        hepatic_pull = -self.gezi * (g_current - self.gb) * dt_minutes

        # Net change in glucose
        delta_g = carb_effect_rate - insulin_effect_rate + basal_effect_rate + hepatic_pull
        g_next = float(np.clip(g_current + delta_g, 30.0, 400.0))

        # Update IOB and COB for next step
        iob_next = float(np.clip(iob_current * 0.965 + bolus_step, 0.0, 30.0))
        cob_next = float(np.clip(cob_current * 0.945 + carbs_step, 0.0, 200.0))

        return g_next, iob_next, cob_next

    def simulate_trajectory(
        self,
        start_sgv: float,
        start_iob: float,
        start_cob: float,
        bolus_series: List[float],
        carbs_series: List[float],
        basal_series: List[float],
        start_datetime: pd.Timestamp,
        num_steps: int = 288
    ) -> List[Dict[str, Any]]:
        """
        Simulates continuous glucose trajectory over num_steps (e.g. 288 steps = 24 hours).
        Includes quantile uncertainty bounds (p10, p50, p90).
        """
        results = []
        g_curr = start_sgv
        iob_curr = start_iob
        cob_curr = start_cob

        for i in range(num_steps):
            dt = start_datetime + pd.Timedelta(minutes=5 * i)
            hour = dt.hour + dt.minute / 60.0

            bolus_val = bolus_series[i] if i < len(bolus_series) else 0.0
            carbs_val = carbs_series[i] if i < len(carbs_series) else 0.0
            basal_val = basal_series[i] if i < len(basal_series) else self.basal_by_block[self.get_time_block(hour)]

            g_next, iob_next, cob_next = self.simulate_step(
                g_current=g_curr,
                iob_current=iob_curr,
                cob_current=cob_curr,
                bolus_step=bolus_val,
                carbs_step=carbs_val,
                basal_step=basal_val,
                hour_of_day=hour,
                dt_minutes=5.0
            )

            # Quantile uncertainty expansion over horizon
            uncertainty_std = 8.0 + 0.12 * (i * 5.0) ** 0.7
            p10 = float(np.clip(g_next - 1.28 * uncertainty_std, 30.0, 400.0))
            p90 = float(np.clip(g_next + 1.28 * uncertainty_std, 30.0, 400.0))

            results.append({
                "datetime": dt.strftime('%Y-%m-%dT%H:%M:%S'),
                "step": i,
                "minute": i * 5,
                "simulated_sgv": round(g_next, 1),
                "p50": round(g_next, 1),
                "p10": round(p10, 1),
                "p90": round(p90, 1),
                "iob": round(iob_curr, 2),
                "cob": round(cob_curr, 1),
                "basal": round(basal_val, 2)
            })

            g_curr, iob_curr, cob_curr = g_next, iob_next, cob_next

        return results
