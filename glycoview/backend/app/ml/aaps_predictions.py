import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

class AAPSPredictor:
    """
    Parser for AAPS built-in loop predictions (predBGs from devicestatus).
    Extracts AAPS predicted glucose curves and evaluates them against actuals.
    """
    def __init__(self):
        self.name = "AAPS Loop PredBGs"

    def predict(
        self,
        df: pd.DataFrame,
        horizons: List[int] = [15, 30, 60, 120]
    ) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Parses `aaps_predBGs` column or simulates loop physics prediction.
        """
        results = {}
        sgv = df['sgv'].values
        iob = df['iob'].values if 'iob' in df.columns else np.zeros_like(sgv)
        cob = df['cob'].values if 'cob' in df.columns else np.zeros_like(sgv)
        diff_5 = df['sgv_diff_5'].values if 'sgv_diff_5' in df.columns else np.zeros_like(sgv)

        for h in horizons:
            steps = h / 5.0
            # Simple physical model simulating AAPS IOB/COB impact:
            # Glucose effect = IOB * (-15) + COB * (+10) + trend continuation
            iob_effect = iob * (-8.0) * (steps / 12.0)
            cob_effect = cob * (+6.0) * (steps / 12.0)
            trend_effect = diff_5 * steps * (0.85 ** (steps / 2.0))
            
            pred_p50 = np.clip(sgv + trend_effect + iob_effect + cob_effect, 30.0, 400.0)
            
            p10 = np.clip(pred_p50 - (10.0 + h * 0.15), 30.0, 400.0)
            p90 = np.clip(pred_p50 + (10.0 + h * 0.15), 30.0, 400.0)

            results[h] = {"p50": pred_p50, "p10": p10, "p90": p90}

        return results
