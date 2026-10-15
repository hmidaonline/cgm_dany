import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from app.ml.simulation import insulin_iob_decay

class Oref0UAMPerturbationEngine:
    """
    Estimates unannounced carbohydrate absorption / metabolic deviations
    using OpenAPS / AndroidAPS oref0 deviation mechanics:
    Deviation(t) = Delta_G(t) - BGI(t) - Delta_Basal_Effect(t)
    
    When Deviation > 0, it represents ongoing exogenous glucose flux (unannounced meal,
    delayed gastric emptying, or hepatic surge) that prompted AAPS insulin delivery.
    """
    def __init__(self, dia_hours: float = 7.5, tau_minutes: float = 50.0):
        self.dia = dia_hours
        self.tau = tau_minutes

    def calculate_recent_deviation(
        self,
        df: pd.DataFrame,
        t_idx: int,
        window_steps: int = 3, # past 15 min
        isf: float = 32.0,
        sched_basal: float = 0.85
    ) -> float:
        """
        Calculates mean observed deviation over the past window_steps (15 min).
        Returns deviation rate in mg/dL per 5-min step.
        """
        if t_idx < window_steps + 1:
            return 0.0

        deviations = []
        for j in range(t_idx - window_steps + 1, t_idx + 1):
            g_curr = float(df.iloc[j]['sgv'])
            g_prev = float(df.iloc[j - 1]['sgv'])
            delta_g = g_curr - g_prev

            # Insulin effect at step j from treatments
            # Approximate BGI from active IOB change or delivered bolus/basal
            b_prev = float(df.iloc[j - 1].get('bolus', 0.0))
            basal_prev = float(df.iloc[j - 1].get('basal', sched_basal))
            
            # Basal delta effect (more basal = negative delta_g)
            basal_effect = (basal_prev - sched_basal) * (5.0 / 60.0) * isf

            # Bolus activity approx
            bolus_effect = b_prev * isf * (1.0 - insulin_iob_decay(5.0, dia_hours=self.dia))

            bgi = -(bolus_effect + basal_effect)
            dev = delta_g - bgi
            deviations.append(dev)

        mean_dev = float(np.mean(deviations))
        # Physically bound to plausible rates [-6 mg/dL to +20 mg/dL per 5 min]
        return float(np.clip(mean_dev, -6.0, 20.0))

    def project_uam_flux(
        self,
        initial_deviation_rate: float,
        horizon_steps: int
    ) -> List[float]:
        """
        Projects exogenous glucose appearance flux over horizon_steps
        with exponential decay: flux(k) = D0 * exp(-k * dt / tau)
        """
        flux_series = []
        for k in range(1, horizon_steps + 1):
            t_min = k * 5.0
            decay = np.exp(-t_min / self.tau)
            flux_series.append(float(initial_deviation_rate * decay))
        return flux_series
