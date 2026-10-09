import pandas as pd
from typing import Any
from app.data.dao import dao

def load_and_clean_entries() -> pd.DataFrame:
    raw_entries = dao.get_entries(limit=100000)
    if not raw_entries:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_entries)
    # Filter valid sgv
    df = df[(df["type"] == "sgv") & (df["sgv"] > 20) & (df["sgv"] < 500)]
    
    # Convert epoch to datetime
    df["datetime"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    
    # Deduplicate keeping the first
    df = df.drop_duplicates(subset=["datetime", "sgv"], keep="first")
    
    # Set index
    df = df.set_index("datetime").sort_index()
    
    df_resampled = df.resample("5min").mean(numeric_only=True)
    df_resampled["sgv"] = df_resampled["sgv"].interpolate(method="linear", limit=6)
    
    return df_resampled

def build_features() -> pd.DataFrame:
    """Build the unified dataframe by joining entries, treatments, etc."""
    df = load_and_clean_entries()
    # In a full implementation, this will join treatments and devicestatus
    return df

def get_processed_dataframe(days: int = 7) -> pd.DataFrame:
    """Returns cleaned and resampled dataframe with datetime column."""
    df = build_features()
    if df.empty:
        return pd.DataFrame()
    df_reset = df.reset_index()
    if 'datetime' in df_reset.columns:
        df_reset['datetime'] = pd.to_datetime(df_reset['datetime'])
    return df_reset

