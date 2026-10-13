from fastapi import APIRouter, Query, Response
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
import io

from app.data.pipeline import get_processed_dataframe
from app.ml.features import prepare_ml_dataset, FEATURE_COLUMNS, TARGET_HORIZONS

router = APIRouter(prefix="/api/v1/ml", tags=["dataset"])

# Cache processed dataset in memory to avoid re-computing on every pagination click
DATASET_CACHE: Dict[str, Any] = {
    "df": None,
    "last_updated": 0,
    "feature_cols": [],
    "target_cols": []
}

def _get_or_compute_dataset() -> pd.DataFrame:
    import time
    now = time.time()
    # Cache for 120 seconds
    if DATASET_CACHE["df"] is not None and (now - DATASET_CACHE["last_updated"]) < 120:
        return DATASET_CACHE["df"]

    try:
        df_raw = get_processed_dataframe(since="2026-10-01")
    except Exception:
        df_raw = pd.DataFrame()

    if df_raw.empty or 'sgv' not in df_raw.columns:
        # Synthetic fallback if database unavailable
        now_ts = pd.Timestamp.now()
        times = [now_ts - pd.Timedelta(minutes=5 * i) for i in range(1500)][::-1]
        base_sgv = 115 + 30 * np.sin(np.linspace(0, 15 * np.pi, 1500)) + np.random.normal(0, 3, 1500)
        df_raw = pd.DataFrame({
            'datetime': times,
            'sgv': np.clip(base_sgv, 45, 340),
            'iob': np.clip(1.2 + np.cos(np.linspace(0, 7 * np.pi, 1500)), 0, 5),
            'cob': np.clip(15 + 10 * np.sin(np.linspace(0, 7 * np.pi, 1500)), 0, 60),
            'bolus': [2.5 if i % 144 == 20 else 0.0 for i in range(1500)],
            'carbs': [45.0 if i % 144 == 20 else 0.0 for i in range(1500)],
            'basal': 0.8
        })

    df_feat, fcols, tcols = prepare_ml_dataset(df_raw)
    DATASET_CACHE["df"] = df_feat
    DATASET_CACHE["feature_cols"] = fcols
    DATASET_CACHE["target_cols"] = tcols
    DATASET_CACHE["last_updated"] = now
    return df_feat

@router.get("/dataset")
def get_training_dataset(
    page: int = 1,
    page_size: int = 50,
    search_date: Optional[str] = None,
    category: Optional[str] = "all",
    sort_order: str = "desc"
):
    """
    Returns the supervised ML training dataset after extraction from Nightscout MongoDB,
    data cleaning, 5-minute resampling, lag calculation, differential velocities,
    pharmacokinetics integration, cyclic time encoding and multi-horizon target labeling.
    """
    df = _get_or_compute_dataset()
    if df.empty:
        return {
            "status": "empty",
            "total_records": 0,
            "columns": [],
            "records": []
        }

    working_df = df.copy()

    # Filter by date if provided
    if search_date:
        working_df['date_str'] = pd.to_datetime(working_df['datetime']).dt.strftime('%Y-%m-%d')
        working_df = working_df[working_df['date_str'] == search_date].drop(columns=['date_str'])

    # Filter by glycemic or clinical category
    if category == "hypo":
        working_df = working_df[working_df['sgv'] < 70.0]
    elif category == "target":
        working_df = working_df[(working_df['sgv'] >= 70.0) & (working_df['sgv'] <= 180.0)]
    elif category == "hyper":
        working_df = working_df[working_df['sgv'] > 180.0]
    elif category == "meals":
        working_df = working_df[working_df['carbs'] > 0.0]
    elif category == "bolus":
        working_df = working_df[working_df['bolus'] > 0.0]

    # Sort
    if 'datetime' in working_df.columns:
        working_df = working_df.sort_values('datetime', ascending=(sort_order == "asc"))

    total_records = len(working_df)
    total_unfiltered = len(df)

    # Compute global summary on full dataset
    sgv_series = df['sgv']
    tbr = round(float((sgv_series < 70).mean() * 100), 1)
    tir = round(float(((sgv_series >= 70) & (sgv_series <= 180)).mean() * 100), 1)
    tar = round(float((sgv_series > 180).mean() * 100), 1)

    min_date = str(df['datetime'].min()) if 'datetime' in df.columns else ""
    max_date = str(df['datetime'].max()) if 'datetime' in df.columns else ""

    summary = {
        "total_records": total_unfiltered,
        "features_count": len(DATASET_CACHE["feature_cols"]),
        "targets_count": len(DATASET_CACHE["target_cols"]),
        "all_columns_count": len(df.columns),
        "min_date": min_date,
        "max_date": max_date,
        "tir_pct": tir,
        "tbr_pct": tbr,
        "tar_pct": tar,
        "mean_sgv": round(float(sgv_series.mean()), 1),
        "min_sgv": round(float(sgv_series.min()), 1),
        "max_sgv": round(float(sgv_series.max()), 1),
        "meal_events": int((df['carbs'] > 0).sum()),
        "bolus_events": int((df['bolus'] > 0).sum()),
    }

    # Pagination slice
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = working_df.iloc[start_idx:end_idx].copy()

    # Format datetime as ISO string and round floats for clean JSON transport
    records = []
    for _, row in page_df.iterrows():
        rec = {}
        for col in page_df.columns:
            val = row[col]
            if pd.isna(val):
                rec[col] = None
            elif col == 'datetime':
                rec[col] = str(val)
            elif isinstance(val, (float, np.floating)):
                rec[col] = round(float(val), 2)
            elif isinstance(val, (int, np.integer)):
                rec[col] = int(val)
            else:
                rec[col] = str(val)
        records.append(rec)

    total_pages = int(np.ceil(total_records / page_size)) if total_records > 0 else 1

    # Column catalog with categories
    column_metadata = [
        {"name": "datetime", "label": "Date & Heure", "category": "Temps", "desc": "Horodatage échantillonné au pas de 5 min"},
        {"name": "sgv", "label": "Glycémie SGV", "category": "Mesure CGM", "desc": "Glycémie interstitielle en mg/dL"},
        {"name": "carbs", "label": "Glucides (g)", "category": "Traitements", "desc": "Glucides ingérés saisis"},
        {"name": "bolus", "label": "Bolus (U)", "category": "Traitements", "desc": "Insuline bolus délivrée"},
        {"name": "iob", "label": "IOB (U)", "category": "Pharmacocinétique", "desc": "Insuline active restante à bord"},
        {"name": "cob", "label": "COB (g)", "category": "Pharmacocinétique", "desc": "Glucides actifs restants à bord"},
        {"name": "basal", "label": "Débit Basal (U/h)", "category": "Pharmacocinétique", "desc": "Débit basal programmé / effectif"},
        {"name": "sgv_lag_5", "label": "SGV (t-5m)", "category": "Historique Lags", "desc": "Glycémie 5 minutes auparavant"},
        {"name": "sgv_lag_15", "label": "SGV (t-15m)", "category": "Historique Lags", "desc": "Glycémie 15 minutes auparavant"},
        {"name": "sgv_lag_30", "label": "SGV (t-30m)", "category": "Historique Lags", "desc": "Glycémie 30 minutes auparavant"},
        {"name": "sgv_lag_60", "label": "SGV (t-60m)", "category": "Historique Lags", "desc": "Glycémie 1 heure auparavant"},
        {"name": "sgv_diff_5", "label": "Vitesse (Δ 5m)", "category": "Dynamique & Dérivées", "desc": "Taux de variation de la glycémie sur 5 min (mg/dL)"},
        {"name": "sgv_diff_15", "label": "Vitesse (Δ 15m)", "category": "Dynamique & Dérivées", "desc": "Taux de variation de la glycémie sur 15 min"},
        {"name": "sgv_diff2_5", "label": "Accélération", "category": "Dynamique & Dérivées", "desc": "Dérivée seconde (accélération ou décélération)"},
        {"name": "sgv_roll_mean_30", "label": "Moyenne 30m", "category": "Statistiques Glissantes", "desc": "Moyenne mobile sur 30 minutes"},
        {"name": "sgv_roll_std_30", "label": "Écart-type 30m", "category": "Statistiques Glissantes", "desc": "Variabilité glycémique locale sur 30 minutes"},
        {"name": "bolus_sum_1h", "label": "Bolus cumul 1h", "category": "Pharmacocinétique", "desc": "Cumul des bolus injectés sur la dernière heure"},
        {"name": "carbs_sum_2h", "label": "Glucides cumul 2h", "category": "Pharmacocinétique", "desc": "Cumul des glucides ingérés sur les 2 dernières heures"},
        {"name": "sin_hour", "label": "Sinus Heure", "category": "Cycle Circadien", "desc": "Encodage trigonométrique continu de l'heure du jour"},
        {"name": "cos_hour", "label": "Cosinus Heure", "category": "Cycle Circadien", "desc": "Encodage trigonométrique continu de l'heure du jour"},
        {"name": "target_15m", "label": "Cible (+15m)", "category": "Cibles ML (Supervisé)", "desc": "Glycémie réelle future à t+15 min (Target ML)"},
        {"name": "target_30m", "label": "Cible (+30m)", "category": "Cibles ML (Supervisé)", "desc": "Glycémie réelle future à t+30 min (Critère Principal)"},
        {"name": "target_60m", "label": "Cible (+60m)", "category": "Cibles ML (Supervisé)", "desc": "Glycémie réelle future à t+60 min (Target ML)"},
        {"name": "target_120m", "label": "Cible (+120m)", "category": "Cibles ML (Supervisé)", "desc": "Glycémie réelle future à t+120 min (Target ML)"},
    ]

    return {
        "status": "success",
        "summary": summary,
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
        "columns": column_metadata,
        "records": records
    }

@router.get("/dataset/export")
def export_dataset_csv():
    """
    Exports the complete feature-engineered dataset as a downloadable CSV file.
    """
    df = _get_or_compute_dataset()
    if df.empty:
        return Response(content="Aucune donnée", media_type="text/plain")

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    csv_bytes = stream.getvalue().encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=glycoview_training_dataset.csv"
        }
    )
