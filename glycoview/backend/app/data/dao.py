import pandas as pd
from typing import Any
from app.core.database import get_db

class NightscoutDAO:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def get_entries(self, limit: int = 100000, since: Any = None) -> list[dict[str, Any]]:
        """Fetch SGV entries, optionally since a given datetime/timestamp, sorted by date ascending."""
        query: dict[str, Any] = {"type": "sgv"}
        if since is not None:
            if isinstance(since, (int, float)):
                query["date"] = {"$gte": since}
            else:
                ts = int(pd.to_datetime(since).timestamp() * 1000)
                query["date"] = {"$gte": ts}
        cursor = self.db.entries.find(query).sort("date", 1).limit(limit)
        return list(cursor)

    def get_treatments(self, limit: int = 100000, since: Any = None) -> list[dict[str, Any]]:
        """Fetch treatments, optionally since a given date/created_at, sorted by created_at ascending."""
        query: dict[str, Any] = {}
        if since is not None:
            since_iso = pd.to_datetime(since).isoformat()
            query["created_at"] = {"$gte": since_iso}
        cursor = self.db.treatments.find(query).sort("created_at", 1).limit(limit)
        return list(cursor)

    def get_devicestatus(self, limit: int = 100000, since: Any = None) -> list[dict[str, Any]]:
        """Fetch devicestatus, optionally since a given created_at, sorted by created_at ascending."""
        query: dict[str, Any] = {}
        if since is not None:
            since_iso = pd.to_datetime(since).isoformat()
            query["created_at"] = {"$gte": since_iso}
        cursor = self.db.devicestatus.find(query).sort("created_at", 1).limit(limit)
        return list(cursor)

    def get_profile(self) -> dict[str, Any] | None:
        """Fetch the most recent profile."""
        cursor = self.db.profile.find().sort("created_at", -1).limit(1)
        docs = list(cursor)
        return docs[0] if docs else None

dao = NightscoutDAO()
