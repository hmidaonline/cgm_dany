import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any

FEATURE_COLUMNS = [
    'sgv', 'sgv_lag_5', 'sgv_lag_10', 'sgv_lag_15', 'sgv_lag_20', 'sgv_lag_30', 'sgv_lag_45', 'sgv_lag_60',
    'sgv_diff_5', 'sgv_diff_15', 'sgv_diff2_5',
    'sgv_roll_mean_30', 'sgv_roll_std_30', 'sgv_roll_mean_60',
    'iob', 'iob_diff_5', 'iob_lag_15', 'iob_lag_30',
    'cob', 'cob_diff_5', 'cob_lag_15', 'cob_lag_30',
    'bolus_sum_1h', 'carbs_sum_2h',
    'sin_hour', 'cos_hour', 'day_of_week'
]

TARGET_HORIZONS = [15, 30, 60, 120]  # in minutes

def prepare_ml_dataset(
    df: pd.DataFrame,
    horizons: List[int] = TARGET_HORIZONS
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Transforms raw/merged CGM dataset (resampled at 5-minute intervals)
    into a feature-rich DataFrame suitable for supervised ML/DL forecasting.
    
    Returns:
        (df_features, feature_column_names, target_column_names)
    """
    if df.empty or 'sgv' not in df.columns:
        return pd.DataFrame(), [], []

    data = df.copy()

    # Ensure datetime sorting
    if 'datetime' in data.columns:
        data['datetime'] = pd.to_datetime(data['datetime'])
        data = data.sort_values('datetime').reset_index(drop=True)

    # Ensure numeric columns
    for col in ['sgv', 'iob', 'cob', 'bolus', 'carbs']:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0.0)
        else:
            data[col] = 0.0

    # Interpolate missing SGV values up to 30 mins (6 periods of 5 min)
    data['sgv'] = data['sgv'].replace(0, np.nan).interpolate(method='linear', limit=6).bfill().ffill()

    # Lags for SGV (1 period = 5 mins)
    data['sgv_lag_5'] = data['sgv'].shift(1)
    data['sgv_lag_10'] = data['sgv'].shift(2)
    data['sgv_lag_15'] = data['sgv'].shift(3)
    data['sgv_lag_20'] = data['sgv'].shift(4)
    data['sgv_lag_30'] = data['sgv'].shift(6)
    data['sgv_lag_45'] = data['sgv'].shift(9)
    data['sgv_lag_60'] = data['sgv'].shift(12)

    # Derivatives / Speed of change (rate of change in mg/dL per 5 min)
    data['sgv_diff_5'] = data['sgv'] - data['sgv_lag_5']
    data['sgv_diff_15'] = data['sgv'] - data['sgv_lag_15']
    data['sgv_diff2_5'] = data['sgv_diff_5'] - (data['sgv_lag_5'] - data['sgv_lag_10'])

    # Rolling statistics over 30 min (6 steps) and 60 min (12 steps)
    data['sgv_roll_mean_30'] = data['sgv'].rolling(window=6, min_periods=1).mean()
    data['sgv_roll_std_30'] = data['sgv'].rolling(window=6, min_periods=1).std().fillna(0.0)
    data['sgv_roll_mean_60'] = data['sgv'].rolling(window=12, min_periods=1).mean()

    # IOB & COB features
    data['iob_lag_5'] = data['iob'].shift(1)
    data['iob_diff_5'] = data['iob'] - data['iob_lag_5']
    data['iob_lag_15'] = data['iob'].shift(3)
    data['iob_lag_30'] = data['iob'].shift(6)

    data['cob_lag_5'] = data['cob'].shift(1)
    data['cob_diff_5'] = data['cob'] - data['cob_lag_5']
    data['cob_lag_15'] = data['cob'].shift(3)
    data['cob_lag_30'] = data['cob'].shift(6)

    # Rolling insulin / carbs sums
    data['bolus_sum_1h'] = data['bolus'].rolling(window=12, min_periods=1).sum()
    data['carbs_sum_2h'] = data['carbs'].rolling(window=24, min_periods=1).sum()

    # Temporal cyclical features
    if 'datetime' in data.columns and not data['datetime'].isna().all():
        hours = data['datetime'].dt.hour + data['datetime'].dt.minute / 60.0
        data['sin_hour'] = np.sin(2 * np.pi * hours / 24.0)
        data['cos_hour'] = np.cos(2 * np.pi * hours / 24.0)
        data['day_of_week'] = data['datetime'].dt.dayofweek / 6.0
    else:
        data['sin_hour'] = 0.0
        data['cos_hour'] = 0.0
        data['day_of_week'] = 0.0

    # Targets (Future SGV at +15m, +30m, +60m, +120m)
    target_cols = []
    for h in horizons:
        steps = h // 5
        col_name = f'target_{h}m'
        data[col_name] = data['sgv'].shift(-steps)
        target_cols.append(col_name)

    # Drop rows without required past history
    data = data.dropna(subset=['sgv_lag_60']).reset_index(drop=True)

    return data, FEATURE_COLUMNS, target_cols
