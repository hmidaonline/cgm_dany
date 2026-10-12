from typing import Dict, Any, Optional
from app.data.dao import dao

def get_active_profile() -> Dict[str, Any]:
    """
    Parses active Nightscout profile and returns DIA, schedule ISF, CR, and Basal.
    """
    doc = dao.get_profile()
    if not doc or not isinstance(doc, dict):
        return {
            "name": "default",
            "dia": 5.0,
            "isf_schedule": {},
            "cr_schedule": {},
            "basal_schedule": {}
        }
    
    store = doc.get("store", {})
    def_name = doc.get("defaultProfile", "normalProfile")
    p_data = store.get(def_name, {})
    if not p_data and store:
        # Fallback to first profile in store
        first_key = list(store.keys())[0]
        p_data = store[first_key]
        def_name = first_key

    dia = float(p_data.get("dia", 5.0))

    # Helper to parse time string "HH:MM" to hour float
    def _parse_time(t_str: str) -> float:
        try:
            parts = t_str.split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        except Exception:
            return 0.0

    def _build_schedule_by_block(items: list, default_val: float) -> Dict[int, float]:
        """Maps Nightscout schedule items into 8 blocks of 3 hours (0-3h, 3-6h, ...)."""
        blocks = {i: default_val for i in range(8)}
        if not items:
            return blocks
        
        # Sort items by time
        sorted_items = sorted(items, key=lambda x: x.get("timeAsSeconds", _parse_time(x.get("time", "00:00")) * 3600))
        
        for block_idx in range(8):
            block_start_sec = block_idx * 3 * 3600
            val = default_val
            for it in sorted_items:
                sec = it.get("timeAsSeconds", int(_parse_time(it.get("time", "00:00")) * 3600))
                if sec <= block_start_sec:
                    val = float(it.get("value", default_val))
                else:
                    break
            blocks[block_idx] = val
        return blocks

    isf_blocks = _build_schedule_by_block(p_data.get("sens", []), default_val=35.0)
    cr_blocks = _build_schedule_by_block(p_data.get("carbratio", []), default_val=9.0)
    basal_blocks = _build_schedule_by_block(p_data.get("basal", []), default_val=0.85)

    return {
        "name": def_name,
        "dia": dia,
        "isf_schedule": isf_blocks,
        "cr_schedule": cr_blocks,
        "basal_schedule": basal_blocks,
        "timezone": p_data.get("timezone", "UTC"),
        "units": p_data.get("units", "mg/dl")
    }
