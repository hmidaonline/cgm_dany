import json
import os
from typing import Dict, Any, Optional

DEFAULT_PARAMS_PATH = os.path.join(os.path.dirname(__file__), "..", "calibration_params.json")

def save_calibration_params(params: Dict[str, Any], filepath: Optional[str] = None) -> str:
    path = filepath or DEFAULT_PARAMS_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)
    return os.path.abspath(path)

def load_calibration_params(filepath: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = filepath or DEFAULT_PARAMS_PATH
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Convert string keys back to int for schedules
    for schedule_key in ["isf_by_block", "cr_by_block", "basal_by_block"]:
        if schedule_key in data:
            data[schedule_key] = {int(k): float(v) for k, v in data[schedule_key].items()}
    if "isf_ci_95" in data:
        data["isf_ci_95"] = {int(k): v for k, v in data["isf_ci_95"].items()}
    if "cr_ci_95" in data:
        data["cr_ci_95"] = {int(k): v for k, v in data["cr_ci_95"].items()}
    return data
