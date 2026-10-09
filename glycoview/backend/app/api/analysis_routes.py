from fastapi import APIRouter
from app.data.pipeline import load_and_clean_entries
from app.data.metrics import calculate_glycemic_metrics

router = APIRouter(prefix="/api/v1/analysis")

@router.get("/metrics")
def get_metrics(date: str | None = None):
    df = load_and_clean_entries()
    if df.empty:
        return {}
    if date:
        df_filtered = df[df.index.strftime('%Y-%m-%d') == date]
        return calculate_glycemic_metrics(df_filtered)
    return calculate_glycemic_metrics(df)

@router.get("/days")
def get_available_days():
    df = load_and_clean_entries()
    if df.empty:
        return []
    metrics = calculate_glycemic_metrics(df)
    return metrics.get("daily", [])

