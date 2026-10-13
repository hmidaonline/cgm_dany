import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from app.ml.features import prepare_ml_dataset, FEATURE_COLUMNS, TARGET_HORIZONS
from app.ml.simulation import insulin_iob_decay
from app.core.profile_service import get_active_profile

import math

def carb_cob_decay_custom(t_minutes: float, speed: str = "normal") -> float:
    """
    Carb absorption decay curve with custom digestion speeds:
    - 'fast': rapid sugars, juice, candy (peak ~25 min, duration 120 min)
    - 'normal': balanced meal (peak ~45 min, duration 180 min)
    - 'slow': high fat/protein meal, pizza, pasta (peak ~75 min, duration 300 min)
    Returns remaining fraction of unabsorbed carbs (active COB fraction) at t_minutes in [0.0, 1.0].
    Strictly continuous and decays smoothly to 0.0 at duration.
    """
    if t_minutes <= 0:
        return 1.0

    if speed == "fast":
        duration = 120.0
        peak = 25.0
    elif speed == "slow":
        duration = 300.0
        peak = 75.0
    else:  # normal
        duration = 180.0
        peak = 45.0

    if t_minutes >= duration:
        return 0.0

    # Rate of appearance peaks at peak with smooth decay to duration
    tau = peak * (1.0 - peak / duration) / (1.0 - 2.0 * peak / duration)
    num = (1.0 + t_minutes / tau) * math.exp(-t_minutes / tau) - (1.0 + duration / tau) * math.exp(-duration / tau)
    den = 1.0 - (1.0 + duration / tau) * math.exp(-duration / tau)
    return float(np.clip(num / den, 0.0, 1.0))

class DigitalTwinModel:
    """
    Personalized Digital Twin for Glucose-Insulin-Carb Dynamics.
    Combines:
    1. Compartmental Physiological Model (Bergman Minimal Model / Oref0 kinetics).
    2. Time-Varying Parameters (ISF, CR, Basal, DIA dynamically initialized from Nightscout profile).
    3. Dynamic Scenario Engine with custom carb absorption speeds & insulin profiles.
    """
    def __init__(self):
        self.name = "Jumeau Numérique Physiologique Hybride"
        self.gb = 100.0        # Basal glucose (mg/dL)
        self.gezi = 0.005      # Glucose effectiveness at zero insulin (1/min)
        
        # Load user settings from profile
        user_prof = get_active_profile()
        self.dia = float(user_prof.get("dia", 7.0))
        self.isf_by_block = user_prof.get("isf_schedule", {i: 35.0 for i in range(8)})
        self.cr_by_block = user_prof.get("cr_schedule", {i: 9.0 for i in range(8)})
        self.basal_by_block = user_prof.get("basal_schedule", {i: 0.85 for i in range(8)})
        
        self.is_fitted = False

    def get_time_block(self, hour: float) -> int:
        """Returns 3-hour block index (0 to 7) for a given hour of day."""
        return min(7, max(0, int(hour // 3)))

    def fit(self, df_raw: pd.DataFrame):
        """
        Fits time-varying ISF, CR, and physiological parameters on historical dataset,
        adjusting baseline profile settings with empirical evidence.
        """
        # Always refresh base profile
        user_prof = get_active_profile()
        self.dia = float(user_prof.get("dia", 7.0))
        for k, v in user_prof.get("isf_schedule", {}).items():
            self.isf_by_block[k] = v
        for k, v in user_prof.get("cr_schedule", {}).items():
            self.cr_by_block[k] = v
        for k, v in user_prof.get("basal_schedule", {}).items():
            self.basal_by_block[k] = v

        df_feat, feature_cols, target_cols = prepare_ml_dataset(df_raw)
        if df_feat.empty or len(df_feat) < 50:
            self.is_fitted = True
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
                        est_isf = float(np.clip((mean_drop / mean_iob) * 4.0, 15.0, 90.0))
                        # Blend profile ISF with observed data
                        self.isf_by_block[block_idx] = round(0.5 * self.isf_by_block.get(block_idx, 35.0) + 0.5 * est_isf, 1)

                with_carbs = sub[sub['carbs_sum_2h'] > 10.0]
                if len(with_carbs) > 5 and 'bolus_sum_1h' in with_carbs.columns:
                    mean_carbs = with_carbs['carbs_sum_2h'].mean()
                    mean_bolus = with_carbs['bolus_sum_1h'].mean()
                    if mean_bolus > 0:
                        est_cr = float(np.clip(mean_carbs / mean_bolus, 4.0, 25.0))
                        self.cr_by_block[block_idx] = round(0.5 * self.cr_by_block.get(block_idx, 9.0) + 0.5 * est_cr, 1)

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

            isf = isf_override if isf_override is not None else self.isf_by_block.get(block_idx, 35.0)
            cr = self.cr_by_block.get(block_idx, 9.0)
            effective_isf = isf * stress_factor

            # Baseline simulation value (follows smoothed real trend)
            base_sgv = float(real_sgvs[i])

            # Calculate intervention effect if step is after event_step_idx
            delta_min = (i - event_step_idx) * 5.0
            
            if delta_min >= 0:
                # 1. Added Insulin Effect with accurate DIA
                iob_decay = insulin_iob_decay(delta_min, dia_hours=self.dia)
                iob_absorbed = 1.0 - iob_decay
                insulin_drop = custom_bolus * effective_isf * iob_absorbed

                # 2. Added Carbs Effect with Custom Digestion Speed
                cob_decay = carb_cob_decay_custom(delta_min, speed=carb_speed)
                cob_absorbed = 1.0 - cob_decay
                carbs_rise = custom_carbs * (effective_isf / cr) * cob_absorbed

                # 3. Temp Basal Effect (more basal insulin = drop, less basal insulin = rise)
                scheduled_basal = self.basal_by_block.get(block_idx, 0.85)
                basal_delta_rate = (scheduled_basal * (basal_mult - 1.0))
                basal_insulin_drop = (effective_isf * basal_delta_rate * (delta_min / 60.0))

                # 4. Stress Hepatic Release Effect
                stress_hepatic_boost = max(0.0, (1.0 - stress_factor) * 40.0)
                stress_rise = stress_hepatic_boost * (1.0 - np.exp(-delta_min / 45.0))

                net_scenario_delta = carbs_rise - insulin_drop - basal_insulin_drop + stress_rise
            else:
                net_scenario_delta = 0.0
                iob_decay = 0.0
                cob_decay = 0.0

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
                "simulated_iob": round(custom_bolus * iob_decay, 2) if delta_min >= 0 else 0.0,
                "simulated_cob": round(custom_carbs * cob_decay, 1) if delta_min >= 0 else 0.0,
                "is_event_point": i == event_step_idx
            })

        return results

    def simulate_full_planned_day(
        self,
        start_sgv: float = 110.0,
        basal_rate: Optional[float] = None,
        meals_and_boluses: Optional[List[Dict[str, Any]]] = None,
        isf_override: Optional[float] = None,
        cr_override: Optional[float] = None,
        stress_factor: float = 1.0,
        date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simulates an entire 24-hour day (288 steps of 5 min, 00:00 to 23:55)
        based on user-programmed Basal, multiple Boluses, and Carbs meals.
        Returns continuous simulated trajectory, TIR metrics, and hypo/hyper risk markers.
        """
        num_steps = 288
        base_date = pd.to_datetime(date_str) if date_str else pd.Timestamp.now().normalize()
        
        bolus_grid = [0.0] * num_steps
        carbs_grid = [0.0] * num_steps
        speeds_grid = ["normal"] * num_steps

        # Map planned meals and boluses onto the 5-min timeline
        if meals_and_boluses:
            for item in meals_and_boluses:
                t_str = item.get("time", "12:00")
                try:
                    parts = t_str.split(":")
                    h, m = int(parts[0]), int(parts[1])
                    step_idx = min(num_steps - 1, max(0, (h * 60 + m) // 5))
                    b_val = float(item.get("bolus", 0.0))
                    c_val = float(item.get("carbs", 0.0))
                    spd = item.get("speed", "normal")
                    bolus_grid[step_idx] += b_val
                    carbs_grid[step_idx] += c_val
                    speeds_grid[step_idx] = spd
                except Exception:
                    pass

        timeline = []
        curr_sgv = float(start_sgv)
        dia = self.dia

        for i in range(num_steps):
            dt = base_date + pd.Timedelta(minutes=5 * i)
            hour = (i * 5) / 60.0
            block_idx = self.get_time_block(hour)

            isf = isf_override if isf_override is not None else self.isf_by_block.get(block_idx, 35.0)
            cr = cr_override if cr_override is not None else self.cr_by_block.get(block_idx, 9.0)
            sched_basal = self.basal_by_block.get(block_idx, 0.85)
            effective_isf = isf * stress_factor

            # Incremental drop from all active past boluses
            total_bolus_drop = 0.0
            lookback_b = int(min(i, dia * 12))
            for k in range(lookback_b):
                past_idx = i - 1 - k
                b = bolus_grid[past_idx]
                if b > 0:
                    t_min_curr = (k + 1) * 5.0
                    t_min_prev = k * 5.0
                    frac_absorbed_step = insulin_iob_decay(t_min_prev, dia_hours=dia) - insulin_iob_decay(t_min_curr, dia_hours=dia)
                    total_bolus_drop += b * effective_isf * max(0.0, frac_absorbed_step)

            # Incremental rise from all active past carbs
            total_carbs_rise = 0.0
            lookback_c = int(min(i, 60))
            for k in range(lookback_c):
                past_idx = i - 1 - k
                c = carbs_grid[past_idx]
                if c > 0:
                    spd = speeds_grid[past_idx]
                    t_min_curr = (k + 1) * 5.0
                    t_min_prev = k * 5.0
                    frac_absorbed_step = carb_cob_decay_custom(t_min_prev, speed=spd) - carb_cob_decay_custom(t_min_curr, speed=spd)
                    total_carbs_rise += c * (effective_isf / cr) * max(0.0, frac_absorbed_step)

            # Active continuous IOB and COB on board at step i
            current_iob = sum(bolus_grid[k] * insulin_iob_decay((i - k) * 5.0, dia_hours=dia) for k in range(i + 1) if bolus_grid[k] > 0)
            current_cob = sum(carbs_grid[k] * carb_cob_decay_custom((i - k) * 5.0, speed=speeds_grid[k]) for k in range(i + 1) if carbs_grid[k] > 0)

            # Basal delta (positive if active_basal > sched_basal -> extra insulin -> drop in glucose)
            active_basal = basal_rate if basal_rate is not None else sched_basal
            basal_insulin_drop_step = (active_basal - sched_basal) * (effective_isf / 60.0) * 5.0

            # Stress hepatic release
            stress_hepatic = max(0.0, (1.0 - stress_factor) * 20.0) * (5.0 / 60.0)

            # Homeostatic hepatic liver balance
            homeostasis = (105.0 - curr_sgv) * 0.015

            step_delta = total_carbs_rise - total_bolus_drop - basal_insulin_drop_step + stress_hepatic + homeostasis
            curr_sgv = float(np.clip(curr_sgv + step_delta, 35.0, 380.0))

            uncertainty = 8.0 + min(20.0, abs(total_carbs_rise - total_bolus_drop) * 0.4)
            sim_val = round(curr_sgv, 1)

            timeline.append({
                "datetime": dt.strftime('%Y-%m-%dT%H:%M:%S'),
                "step": i,
                "hour_str": dt.strftime('%H:%M'),
                "simulated_sgv": sim_val,
                "p10": round(max(35.0, sim_val - uncertainty), 1),
                "p90": round(min(380.0, sim_val + uncertainty), 1),
                "bolus": round(bolus_grid[i], 2),
                "carbs": round(carbs_grid[i], 1),
                "iob": round(current_iob, 2),
                "cob": round(current_cob, 1)
            })

        sgv_vals = [pt["simulated_sgv"] for pt in timeline]
        tir = round(float(sum(1 for s in sgv_vals if 70.0 <= s <= 180.0) / len(sgv_vals) * 100.0), 1)
        tbr = round(float(sum(1 for s in sgv_vals if s < 70.0) / len(sgv_vals) * 100.0), 1)
        tar = round(float(sum(1 for s in sgv_vals if s > 180.0) / len(sgv_vals) * 100.0), 1)
        mean_g = round(float(np.mean(sgv_vals)), 1)
        min_g = round(float(min(sgv_vals)), 1)
        max_g = round(float(max(sgv_vals)), 1)

        return {
            "status": "success",
            "summary": {
                "tir": tir,
                "tbr": tbr,
                "tar": tar,
                "mean_sgv": mean_g,
                "min_sgv": min_g,
                "max_sgv": max_g,
                "total_bolus": round(sum(bolus_grid), 2),
                "total_carbs": round(sum(carbs_grid), 1),
                "max_iob": round(max(pt["iob"] for pt in timeline), 2),
                "max_cob": round(max(pt["cob"] for pt in timeline), 1)
            },
            "timeline": timeline
        }

    def simulate_trajectory(
        self,
        start_sgv: float,
        start_iob: float,
        start_cob: float,
        bolus_series: List[float],
        carbs_series: List[float],
        basal_series: List[float],
        start_datetime: pd.Timestamp,
        num_steps: int = 288,
        real_sgv_series: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculates dynamic simulated trajectory for past day replay using continuous
        pharmacokinetic convolution of past boluses and meal absorption combined with
        an innovation filter to prevent open-loop drift while faithfully reproducing
        metabolic response dynamics.
        """
        curr_state = float(start_sgv)
        res = []

        for i in range(num_steps):
            dt = start_datetime + pd.Timedelta(minutes=5 * i)
            hour = dt.hour + dt.minute / 60.0
            block_idx = self.get_time_block(hour)

            isf = self.isf_by_block.get(block_idx, 35.0)
            cr = self.cr_by_block.get(block_idx, 9.0)
            basal_sched = self.basal_by_block.get(block_idx, 0.85)

            if i == 0:
                sim_val = round(curr_state, 1)
                res.append({
                    "datetime": dt.strftime('%Y-%m-%dT%H:%M:%S'),
                    "simulated_sgv": sim_val,
                    "p10": round(max(35.0, sim_val - 12.0), 1),
                    "p90": round(min(380.0, sim_val + 12.0), 1),
                    "simulated_iob": round(start_iob, 2),
                    "simulated_cob": round(start_cob, 1)
                })
                continue

            # 1. Cumulative incremental effect from past boluses
            total_bolus_drop_step = 0.0
            lookback_steps = int(min(i, self.dia * 12))  # DIA in 5-min intervals
            for k in range(lookback_steps):
                past_idx = i - 1 - k
                b_val = bolus_series[past_idx] if past_idx < len(bolus_series) else 0.0
                if b_val > 0:
                    t_min_curr = (k + 1) * 5.0
                    t_min_prev = k * 5.0
                    d_absorbed = max(0.0, insulin_iob_decay(t_min_prev, dia_hours=self.dia) - insulin_iob_decay(t_min_curr, dia_hours=self.dia))
                    total_bolus_drop_step += b_val * isf * d_absorbed

            # 2. Cumulative incremental effect from past carbs
            total_carbs_rise_step = 0.0
            lookback_carbs = int(min(i, 60))  # up to 5 hours
            for k in range(lookback_carbs):
                past_idx = i - 1 - k
                c_val = carbs_series[past_idx] if past_idx < len(carbs_series) else 0.0
                if c_val > 0:
                    t_min_curr = (k + 1) * 5.0
                    t_min_prev = k * 5.0
                    d_absorbed = max(0.0, carb_cob_decay_custom(t_min_prev, speed="normal") - carb_cob_decay_custom(t_min_curr, speed="normal"))
                    total_carbs_rise_step += c_val * (isf / cr) * d_absorbed

            # Continuous active simulated IOB and COB
            active_iob = sum(bolus_series[k] * insulin_iob_decay((i - k) * 5.0, dia_hours=self.dia) for k in range(i + 1) if k < len(bolus_series) and bolus_series[k] > 0) + start_iob * insulin_iob_decay(i * 5.0, dia_hours=self.dia)
            active_cob = sum(carbs_series[k] * carb_cob_decay_custom((i - k) * 5.0, speed="normal") for k in range(i + 1) if k < len(carbs_series) and carbs_series[k] > 0) + start_cob * carb_cob_decay_custom(i * 5.0, speed="normal")

            # 3. Temp basal delta effect vs scheduled profile (more insulin = drop in glucose)
            basal_val = basal_series[i - 1] if (i - 1) < len(basal_series) else basal_sched
            basal_drop = (basal_val - basal_sched) * (isf / 60.0) * 5.0

            # 4. Endogenous Glucose Production (EGP) homeostatic pull towards basal target (115 mg/dL)
            egp_homeostasis = (115.0 - curr_state) * 0.03
            
            # Physical metabolic forward step
            projected = curr_state + total_carbs_rise_step - total_bolus_drop_step - basal_drop + egp_homeostasis

            # 5. Continuous innovation update if real measurement is available
            if real_sgv_series and len(real_sgv_series) > (i - 1):
                real_prev = real_sgv_series[i - 1]
                # 70% physiological model mechanics, 30% sensor state feedback
                curr_state = float(np.clip(0.70 * projected + 0.30 * real_prev, 35.0, 380.0))
            else:
                curr_state = float(np.clip(projected, 35.0, 380.0))

            sim_val = round(curr_state, 1)
            uncertainty = 10.0 + min(15.0, abs(total_carbs_rise_step - total_bolus_drop_step) * 0.5)

            res.append({
                "datetime": dt.strftime('%Y-%m-%dT%H:%M:%S'),
                "simulated_sgv": sim_val,
                "p10": round(max(35.0, sim_val - uncertainty), 1),
                "p90": round(min(380.0, sim_val + uncertainty), 1),
                "simulated_iob": round(active_iob, 2),
                "simulated_cob": round(active_cob, 1)
            })

        return res
