import os
import pandas as pd
from pathlib import Path
from app.core.config import settings

class DataCache:
    def __init__(self):
        self.cache_dir = Path(settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> pd.DataFrame | None:
        path = self.cache_dir / f"{key}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return None

    def set(self, key: str, df: pd.DataFrame):
        path = self.cache_dir / f"{key}.parquet"
        df.to_parquet(path, engine="pyarrow")

cache = DataCache()
