import numpy as np
import pandas as pd
from typing import Dict, List

class PersistenceBaseline:
    """Baseline model: future glucose equals current glucose."""
    def __init__(self):
        self.name = "Baseline Persistance"

    def predict(self, df: pd.DataFrame, horizons: List[int] = [15, 30, 60, 120]) -> Dict[int, np.ndarray]:
        current_sgv = df['sgv'].values
        return {h: current_sgv.copy() for h in horizons}

class LinearExtrapolationBaseline:
    """Baseline model: future glucose = current glucose + (horizon_minutes / 5) * delta_5m."""
    def __init__(self, damping: float = 0.8):
        self.name = "Baseline Extrapolation Lineaire"
        self.damping = damping  # Damping factor to prevent extreme linear growth over long horizons

    def predict(self, df: pd.DataFrame, horizons: List[int] = [15, 30, 60, 120]) -> Dict[int, np.ndarray]:
        current_sgv = df['sgv'].values
        diff_5m = df['sgv_diff_5'].values if 'sgv_diff_5' in df.columns else np.zeros_like(current_sgv)
        
        preds = {}
        for h in horizons:
            steps = h / 5.0
            # Apply progressive damping over time (e.g. at 120 min, pure linear momentum dies off)
            decay = self.damping ** (steps / 3.0)
            preds[h] = np.clip(current_sgv + steps * diff_5m * decay, 30.0, 400.0)
        return preds
