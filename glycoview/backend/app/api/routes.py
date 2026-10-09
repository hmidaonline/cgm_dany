from fastapi import APIRouter
from app.data.dao import dao
from app.data.pipeline import load_and_clean_entries

router = APIRouter(prefix="/api/v1")

@router.get("/status")
def get_status():
    return {"status": "ok", "service": "glycoview-backend"}

@router.get("/entries/raw")
def get_raw_entries(limit: int = 100):
    entries = dao.get_entries(limit=limit)
    # Convert ObjectId to str
    for e in entries:
        e["_id"] = str(e["_id"])
    return entries

@router.get("/entries/processed")
def get_processed_entries():
    df = load_and_clean_entries()
    if df.empty:
        return []
    # Convert back to dicts for JSON
    df_reset = df.reset_index()
    df_reset["datetime"] = df_reset["datetime"].astype(str)
    import numpy as np
    df_reset = df_reset.replace({np.nan: None})
    return df_reset.to_dict(orient="records")

@router.get("/treatments")
def get_treatments(limit: int = 5000, date: str | None = None):
    treatments = dao.get_treatments(limit=limit)
    res = []
    for t in treatments:
        t["_id"] = str(t["_id"])
        # Format date and isSMB
        if t.get("type") == "SMB":
            t["isSMB"] = True
        if date:
            created_at = t.get("created_at", "")
            if created_at and created_at.startswith(date):
                res.append(t)
        else:
            res.append(t)
    return res

from app.core.database import get_db

def _extract_devicestatus(s: dict) -> dict:
    if not s:
        return {"iob": 0.0, "cob": 0.0, "basal": 0.0, "created_at": None}

    openaps = s.get("openaps", {})
    pump = s.get("pump", {})
    extended = pump.get("extended", {}) if isinstance(pump, dict) else {}

    # 1. IOB (Insulin on Board)
    iob = None
    if isinstance(openaps, dict):
        iob_obj = openaps.get("iob")
        if isinstance(iob_obj, dict):
            iob = iob_obj.get("iob")
        if iob is None:
            enacted = openaps.get("enacted")
            if isinstance(enacted, dict):
                iob = enacted.get("IOB", enacted.get("iob"))
        if iob is None:
            suggested = openaps.get("suggested")
            if isinstance(suggested, dict):
                iob = suggested.get("IOB", suggested.get("iob"))
    if iob is None and isinstance(s.get("loop"), dict):
        iob = s["loop"].get("iob", {}).get("iob")

    # 2. COB (Carbs on Board)
    cob = None
    if isinstance(openaps, dict):
        enacted = openaps.get("enacted")
        if isinstance(enacted, dict):
            cob = enacted.get("COB", enacted.get("cob"))
        if cob is None:
            suggested = openaps.get("suggested")
            if isinstance(suggested, dict):
                cob = suggested.get("COB", suggested.get("cob"))
        if cob is None:
            cob_obj = openaps.get("cob")
            if isinstance(cob_obj, dict):
                cob = cob_obj.get("cob")
    if cob is None and isinstance(s.get("loop"), dict):
        cob = s["loop"].get("cob", {}).get("cob")

    # 3. Basal (Débit basal actuel en U/h)
    basal = None
    if isinstance(extended, dict):
        basal = extended.get("TempBasalAbsoluteRate")
        if basal is None:
            basal = extended.get("BaseBasalRate")
    if basal is None and isinstance(openaps, dict):
        enacted = openaps.get("enacted")
        if isinstance(enacted, dict):
            basal = enacted.get("rate")
        if basal is None:
            suggested = openaps.get("suggested")
            if isinstance(suggested, dict):
                basal = suggested.get("rate")
    if basal is None and isinstance(pump, dict):
        basal = pump.get("basal", {}).get("rate")

    return {
        "iob": round(float(iob), 2) if iob is not None else 0.0,
        "cob": round(float(cob), 1) if cob is not None else 0.0,
        "basal": round(float(basal), 2) if basal is not None else 0.0,
        "created_at": s.get("created_at")
    }

@router.get("/devicestatus/latest")
def get_latest_devicestatus(date: str | None = None):
    db = get_db()
    if db is None:
        return {"iob": 0.0, "cob": 0.0, "basal": 0.0}

    query = {}
    if date:
        query["created_at"] = {"$lte": f"{date}T23:59:59.999Z"}

    status = db["devicestatus"].find_one(query, sort=[("created_at", -1)])
    if not status:
        return {"iob": 0.0, "cob": 0.0, "basal": 0.0}

    return _extract_devicestatus(status)

@router.get("/devicestatus")
def get_devicestatus_history(limit: int = 288, date: str | None = None):
    db = get_db()
    if db is None:
        return []
    
    query = {}
    if date:
        query["created_at"] = {
            "$gte": f"{date}T00:00:00.000Z",
            "$lte": f"{date}T23:59:59.999Z"
        }
        
    cursor = db["devicestatus"].find(query).sort("created_at", -1).limit(limit)
    history = [_extract_devicestatus(s) for s in cursor]
    history.reverse()
    return history
