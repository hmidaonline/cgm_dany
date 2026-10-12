import numpy as np
import pandas as pd
from typing import Any, Optional
from app.data.dao import dao

def load_and_clean_entries(since: Optional[Any] = "2026-10-01") -> pd.DataFrame:
    raw_entries = dao.get_entries(limit=500000, since=since)
    if not raw_entries:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_entries)
    # Filter valid sgv
    df = df[(df["type"] == "sgv") & (df["sgv"] > 20) & (df["sgv"] < 500)]
    if df.empty:
        return pd.DataFrame()
    
    # Convert epoch to datetime
    df["datetime"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    
    # Deduplicate keeping the first
    df = df.drop_duplicates(subset=["datetime", "sgv"], keep="first")
    
    # Set index
    df = df.set_index("datetime").sort_index()
    
    df_resampled = df[["sgv"]].resample("5min").mean()
    df_resampled["sgv"] = df_resampled["sgv"].interpolate(method="linear", limit=6)
    
    return df_resampled

def build_features(since: Optional[Any] = "2026-10-01") -> pd.DataFrame:
    """
    Builds the unified dataframe by joining entries (SGV), treatments (Bolus & Carbs),
    and devicestatus (IOB, COB, Basal rate) sampled at 5-minute intervals.
    Includes all historical data from the specified start date (default 2026-10-01).
    """
    df = load_and_clean_entries(since=since)
    if df.empty:
        return pd.DataFrame()

    # 1. Join Treatments (Insulin Bolus & Carbs)
    try:
        raw_tr = dao.get_treatments(limit=500000, since=since)
        if raw_tr:
            df_tr = pd.DataFrame(raw_tr)
            if not df_tr.empty and "created_at" in df_tr.columns:
                df_tr["datetime"] = pd.to_datetime(df_tr["created_at"], utc=True)
                df_tr["insulin"] = pd.to_numeric(df_tr.get("insulin"), errors="coerce").fillna(0.0)
                df_tr["carbs"] = pd.to_numeric(df_tr.get("carbs"), errors="coerce").fillna(0.0)
                
                tr_res = df_tr.set_index("datetime")[["insulin", "carbs"]].resample("5min").sum()
                df = df.join(tr_res, how="left")
                df["bolus"] = df["insulin"].fillna(0.0)
                df["carbs"] = df["carbs"].fillna(0.0)
                df = df.drop(columns=["insulin"], errors="ignore")
            else:
                df["bolus"] = 0.0
                df["carbs"] = 0.0
        else:
            df["bolus"] = 0.0
            df["carbs"] = 0.0
    except Exception:
        df["bolus"] = 0.0
        df["carbs"] = 0.0

    # 2. Join DeviceStatus (IOB, COB, Basal rate)
    try:
        raw_ds = dao.get_devicestatus(limit=500000, since=since)
        if raw_ds:
            ds_rows = []
            for d in raw_ds:
                openaps = d.get("openaps", {})
                iob_val = openaps.get("iob", {}).get("iob")
                if iob_val is None:
                    iob_val = openaps.get("suggested", {}).get("IOB")
                cob_val = openaps.get("suggested", {}).get("COB")
                rate_val = openaps.get("suggested", {}).get("rate") or openaps.get("enacted", {}).get("rate")
                
                created = d.get("created_at")
                if created:
                    ds_rows.append({
                        "datetime": pd.to_datetime(created, utc=True),
                        "iob": float(iob_val) if iob_val is not None else np.nan,
                        "cob": float(cob_val) if cob_val is not None else np.nan,
                        "basal": float(rate_val) if rate_val is not None else np.nan
                    })
            if ds_rows:
                df_ds = pd.DataFrame(ds_rows).dropna(subset=["datetime"]).drop_duplicates(subset=["datetime"], keep="last").set_index("datetime").sort_index()
                ds_res = df_ds.resample("5min").last()
                df = df.join(ds_res, how="left")
                df["iob"] = df["iob"].ffill().bfill().fillna(0.0)
                df["cob"] = df["cob"].ffill().bfill().fillna(0.0)
                df["basal"] = df["basal"].ffill().bfill().fillna(0.8)
            else:
                df["iob"] = 0.0
                df["cob"] = 0.0
                df["basal"] = 0.8
        else:
            df["iob"] = 0.0
            df["cob"] = 0.0
            df["basal"] = 0.8
    except Exception:
        df["iob"] = 0.0
        df["cob"] = 0.0
        df["basal"] = 0.8

    return df

def get_processed_dataframe(days: Optional[int] = None, since: Optional[Any] = "2026-10-01") -> pd.DataFrame:
    """
    Returns cleaned, resampled, and feature-merged dataframe from the start date (2026-10-01 by default).
    If days is explicitly passed, filters to the last N days.
    """
    df = build_features(since=since)
    if df.empty:
        return pd.DataFrame()
        
    df_reset = df.reset_index()
    if 'datetime' in df_reset.columns:
        df_reset['datetime'] = pd.to_datetime(df_reset['datetime'])
        if days is not None and days > 0:
            cutoff = df_reset['datetime'].max() - pd.Timedelta(days=days)
            df_reset = df_reset[df_reset['datetime'] >= cutoff].reset_index(drop=True)
            
    return df_reset

