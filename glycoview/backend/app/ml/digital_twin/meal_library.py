import numpy as np
import pandas as pd
from typing import Dict, List, Any

def analyze_meal_responses(df_raw: pd.DataFrame) -> Dict[str, Any]:
    """
    Extracts postprandial meal responses (> 10g carbs) from historical dataset.
    Computes peak glucose rise, time-to-peak, +1h/+2h/+3h delta, and groups by meal category.
    """
    if df_raw.empty or 'sgv' not in df_raw.columns:
        return {"status": "success", "total_meals_analyzed": 0, "category_summary": {}, "meals": []}

    data = df_raw.copy()
    if 'datetime' in data.columns:
        data['datetime'] = pd.to_datetime(data['datetime'])
        data = data.sort_values('datetime').reset_index(drop=True)

    if 'carbs' not in data.columns:
        data['carbs'] = 0.0
    if 'bolus' not in data.columns:
        data['bolus'] = 0.0

    data['carbs'] = pd.to_numeric(data['carbs'], errors='coerce').fillna(0.0)
    data['bolus'] = pd.to_numeric(data['bolus'], errors='coerce').fillna(0.0)
    data['sgv'] = pd.to_numeric(data['sgv'], errors='coerce').interpolate().bfill().ffill()

    # Identify meal events (carbs > 10g with at least 2 hours spacing)
    meal_indices = data[data['carbs'] >= 10.0].index.tolist()
    
    meals_analyzed = []
    last_meal_idx = -100

    for idx in meal_indices:
        if idx - last_meal_idx < 12: # skip meals less than 1 hour apart to avoid overlap
            continue

        row = data.iloc[idx]
        meal_carbs = float(row['carbs'])
        meal_bolus = float(row.get('bolus', 0.0))
        meal_time = pd.to_datetime(row['datetime'])
        start_sgv = float(row['sgv'])

        # Look ahead 3 hours = 36 steps of 5-min
        window = data.iloc[idx: min(len(data), idx + 36)]
        if len(window) < 12:
            continue

        sgv_series = window['sgv'].values
        max_sgv = float(np.max(sgv_series))
        min_sgv = float(np.min(sgv_series))
        peak_delta = max_sgv - start_sgv
        peak_step = int(np.argmax(sgv_series))
        peak_time_min = peak_step * 5

        # 1h, 2h, 3h deltas
        sgv_1h = float(sgv_series[12]) if len(sgv_series) > 12 else max_sgv
        sgv_2h = float(sgv_series[24]) if len(sgv_series) > 24 else max_sgv
        sgv_3h = float(sgv_series[-1])

        # Categorize meal time
        hour = meal_time.hour
        if 5 <= hour < 11:
            category = "Petit-déjeuner"
        elif 11 <= hour < 15:
            category = "Déjeuner"
        elif 15 <= hour < 18:
            category = "Collation / Goûter"
        elif 18 <= hour < 22:
            category = "Dîner"
        else:
            category = "Collation Nocturne"

        # Categorize size
        if meal_carbs < 25:
            size_label = "Repas Léger (< 25g)"
        elif meal_carbs <= 60:
            size_label = "Repas Moyen (25-60g)"
        else:
            size_label = "Repas Riche (> 60g)"

        last_meal_idx = idx

        meals_analyzed.append({
            "meal_id": len(meals_analyzed) + 1,
            "datetime": meal_time.strftime('%Y-%m-%dT%H:%M:%S'),
            "category": category,
            "size_label": size_label,
            "carbs_g": round(meal_carbs, 1),
            "bolus_u": round(meal_bolus, 2),
            "start_sgv": round(start_sgv, 1),
            "max_sgv": round(max_sgv, 1),
            "peak_delta": round(peak_delta, 1),
            "peak_time_min": peak_time_min,
            "sgv_1h": round(sgv_1h, 1),
            "sgv_2h": round(sgv_2h, 1),
            "sgv_3h": round(sgv_3h, 1),
            "response_quality": "Excursion Modérée (Maîtrisée)" if peak_delta < 50 else ("Forte Élévation (Ajuster CR)" if peak_delta > 80 else "Réponse Normale")
        })

    # Summary by category
    category_summary = {}
    for cat in ["Petit-déjeuner", "Déjeuner", "Dîner", "Collation / Goûter"]:
        cat_meals = [m for m in meals_analyzed if m["category"] == cat]
        if cat_meals:
            avg_carbs = float(np.mean([m["carbs_g"] for m in cat_meals]))
            avg_delta = float(np.mean([m["peak_delta"] for m in cat_meals]))
            avg_peak_t = float(np.mean([m["peak_time_min"] for m in cat_meals]))
            category_summary[cat] = {
                "count": len(cat_meals),
                "avg_carbs_g": round(avg_carbs, 1),
                "avg_peak_delta": round(avg_delta, 1),
                "avg_peak_time_min": round(avg_peak_t, 0)
            }

    return {
        "status": "success",
        "total_meals_analyzed": len(meals_analyzed),
        "category_summary": category_summary,
        "meals": meals_analyzed[-50:] # return latest 50 meals
    }
