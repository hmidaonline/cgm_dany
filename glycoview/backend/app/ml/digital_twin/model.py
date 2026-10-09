import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from app.ml.features import prepare_ml_dataset, FEATURE_COLUMNS, TARGET_HORIZONS
from app.ml.simulation import insulin_iob_decay

def carb_cob_decay_custom(t_minutes: float, speed: str = "normal") -> float:
    """
    Carb absorption decay curve with custom digestion speeds:
    - 'fast': rapid sugars, juice, candy (peak ~25 min, duration 120 min)
    - 'normal': balanced meal (peak ~45 min, duration 180 min)
    - 'slow': high fat/protein meal, pizza, pasta (peak ~90 min, duration 300 min)
    Returns remaining fraction of unabsorbed carbs at t_minutes.
    """
    if t_minutes <= 0:
        return 1.0
        
    if speed == "fast":
        duration = 120.0
        peak = 25.0
    elif speed == "slow":
        duration = 300.0
        peak = 90.0
    else:  # normal
        duration = 180.0
        peak = 45.0

    if t_minutes >= duration:
        return 0.0

    if t_minutes <= peak:
        absorbed_fraction = 0.5 * (t_minutes / peak) ** 2 * (peak / duration)
    else:
        absorbed_fraction = (t_minutes - 0.5 * peak) / duration

    return float(np.clip(1.0 - absorbed_fraction, 0.0, 1.0))

class DigitalTwinModel:
    """
    Personalized Digital Twin for Glucose-Insulin-Carb Dynamics.
    Combines:
    1. Compartmental Physiological Model (Bergman Minimal Model / Oref0 kinetics).
    2. Time-Varying Parameters (ISF, CR by 3-hour time blocks).
    3. Dynamic Scenario Engine with custom carb absorption speeds & insulin profiles.
    """
    def __init__(self):
        self.name = "Jumeau Numérique Physiologique Hybride"
        self.gb = 100.0        # Basal glucose (mg/dL)
        self.gezi = 0.005      # Glucose effectiveness at zero insulin (1/min)
        
        # Time-varying parameters per 3-hour block (8 blocks: 0-3h, 3-6h, ..., 21-24h)
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

        if 'datetime' in df_feat.columns:
            df_feat['hour'] = pd.to_datetime(df_feat['datetime']).dt.hour
        else:
            df_feat['hour'] = 12

        for block_idx in range(8):
            start_h, end_h = block_idx * 3, (block_idx + 1) * 3
            sub = df_feat[(df_feat['hour'] >= start_h) & (df_feat['hour'] < end_h)]
            
            if len(sub) > 10:
                no_carbs = sub[(sub['cob'] < 2.0) & (sub['iob'] > 0.5)]
                if len(no_carbs) > 5 and 'sgv_diff_15' in no_carbs.columns:
                    mean_drop = -no_carbs['sgv_diff_15'].mean()
                    mean_iob = no_carbs['iob'].mean()
                    if mean_iob > 0:
                        est_isf = float(np.clip((mean_drop / mean_iob) * 4.0, 20.0, 90.0))
                        self.isf_by_block[block_idx] = round(est_isf, 1)

                with_carbs = sub[sub['carbs_sum_2h'] > 10.0]
                if len(with_carbs) > 5 and 'bolus_sum_1h' in with_carbs.columns:
                    mean_carbs = with_carbs['carbs_sum_2h'].mean()
                    mean_bolus = with_carbs['bolus_sum_1h'].mean()
                    if mean_bolus > 0:
                        est_cr = float(np.clip(mean_carbs / mean_bolus, 5.0, 25.0))
                        self.cr_by_block[block_idx] = round(est_cr, 1)

        self.is_fitted = True

    def simulate_day_trajectory(
        self,
        df_day: pd.DataFrame,
        custom_bolus: float = 0.0,
        custom_carbs: float = 0.0,
        carb_speed: str = "normal",        # 'fast', 'normal', 'slow'
        event_time_str: Optional[str] = None, # e.g. '12:30'
        isf_override: Optional[float] = None,
        basal_mult: float = 1.0,
        stress_factor: float = 1.0         # 0.7 = Stress, 1.0 = Normal, 1.4 = Exercice
    ) -> List[Dict[str, Any]]:
        """
        Generates dynamic 24-hour simulation with full user customization.
        """
        if df_day.empty or 'datetime' not in df_day.columns:
            return []

        df_sorted = df_day.sort_values('datetime').reset_index(drop=True)
        n_steps = len(df_sorted)

        # Parse event step index
        event_step_idx = 12 # default at 1h after start
        if event_time_str:
            try:
                parts = event_time_str.split(':')
                target_h, target_m = int(parts[0]), int(parts[1])
                for idx, row in df_sorted.iterrows():
                    dt = pd.to_datetime(row['datetime'])
                    if dt.hour > target_h or (dt.hour == target_h and dt.minute >= target_m):
                        event_step_idx = idx
                        break
            except Exception:
                pass

        results = []

        # Baseline glucose trajectory follows real physiological curve smoothed
        real_sgvs = df_sorted['sgv'].values
        # Fill missing values
        real_sgvs = pd.Series(real_sgvs).interpolate().bfill().ffill().values

        for i in range(n_steps):
            row = df_sorted.iloc[i]
            dt = pd.to_datetime(row['datetime'])
            hour = dt.hour + dt.minute / 60.0
            block_idx = self.get_time_block(hour)

            isf = isf_override if isf_override is not None else self.isf_by_block.get(block_idx, 40.0)
            cr = self.cr_by_block.get(block_idx, 10.0)
            effective_isf = isf * stress_factor

            # Baseline simulation value (follows smoothed real trend)
            base_sgv = float(real_sgvs[i])

            # Calculate intervention effect if step is after event_step_idx
            delta_min = (i - event_step_idx) * 5.0
            
            if delta_min >= 0:
                # 1. Added Insulin Effect
                iob_decay = insulin_iob_decay(delta_min)
                iob_absorbed = 1.0 - iob_decay
                insulin_drop = custom_bolus * effective_isf * iob_absorbed

                # 2. Added Carbs Effect with Custom Digestion Speed
                cob_decay = carb_cob_decay_custom(delta_min, speed=carb_speed)
                cob_absorbed = 1.0 - cob_decay
                carbs_rise = custom_carbs * (effective_isf / cr) * cob_absorbed

                # 3. Temp Basal Effect
                scheduled_basal = self.basal_by_block.get(block_idx, 0.8)
                basal_delta_rate = (scheduled_basal * (basal_mult - 1.0))
                basal_effect = (effective_isf / 60.0) * basal_delta_rate * (delta_min / 5.0)

                # 4. Stress Hepatic Release Effect
                stress_hepatic_boost = max(0.0, (1.0 - stress_factor) * 40.0)
                stress_rise = stress_hepatic_boost * (1.0 - np.exp(-delta_min / 45.0))

                net_scenario_delta = carbs_rise - insulin_drop + basal_effect + stress_rise
            else:
                net_scenario_delta = 0.0

            scenario_sgv = float(np.clip(base_sgv + net_scenario_delta, 30.0, 400.0))

            # Quantile uncertainty intervals
            uncertainty_std = 6.0 + 0.10 * max(0.0, delta_min) ** 0.6
            p10 = float(np.clip(scenario_sgv - 1.28 * uncertainty_std, 30.0, 400.0))
            p90 = float(np.clip(scenario_sgv + 1.28 * uncertainty_std, 30.0, 400.0))

            dt_str = dt.strftime('%Y-%m-%dT%H:%M:%S')
            results.append({
                "datetime": dt_str,
                "step": i,
                "hour_str": dt.strftime('%H:%M'),
                "real_sgv": round(base_sgv, 1),
                "baseline_sim_sgv": round(base_sgv, 1),
                "scenario_sim_sgv": round(scenario_sgv, 1),
                "delta_from_baseline": round(net_scenario_delta, 1),
                "p10": round(p10, 1),
                "p90": round(p90, 1),
                "is_event_point": i == event_step_idx
            })

        return results

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
        Calculates dynamic simulated trajectory for past day replay.
        """
        current_sgv = start_sgv
        res = []

        for i in range(num_steps):
            dt = start_datetime + pd.Timedelta(minutes=5 * i)
            hour = dt.hour + dt.minute / 60.0
            block_idx = self.get_time_block(hour)

            isf = self.isf_by_block.get(block_idx, 40.0)
            cr = self.cr_by_block.get(block_idx, 10.0)
            basal_sched = self.basal_by_block.get(block_idx, 0.8)

            bolus_val = bolus_series[i] if i < len(bolus_series) else 0.0
            carbs_val = carbs_series[i] if i < len(carbs_series) else 0.0
            basal_val = basal_series[i] if i < len(basal_series) else basal_sched

            # Pharmacokinetic delta over 5-min step
            insulin_effect = bolus_val * isf * 0.18
            carbs_effect = carbs_val * (isf / cr) * 0.22
            basal_effect = (basal_val - basal_sched) * (isf / 60.0) * 5.0

            step_delta = carbs_effect - insulin_effect + basal_effect
            # Smooth pull towards physiological mean (110 mg/dL)
            hepatic_pull = (110.0 - current_sgv) * 0.02
            current_sgv = float(np.clip(current_sgv + step_delta + hepatic_pull, 40.0, 380.0))

            res.append({
                "datetime": dt.strftime('%Y-%m-%dT%H:%M:%S'),
                "simulated_sgv": round(current_sgv, 1),
                "p10": round(max(40.0, current_sgv - 12.0), 1),
                "p90": round(min(380.0, current_sgv + 12.0), 1)
            })

        return res
