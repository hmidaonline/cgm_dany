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

    def get_entries(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Fetch latest SGV entries, sorted by date."""
        cursor = self.db.entries.find({"type": "sgv"}).sort("date", -1).limit(limit)
        return list(cursor)

    def get_treatments(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Fetch latest treatments, sorted by created_at."""
        cursor = self.db.treatments.find().sort("created_at", -1).limit(limit)
        return list(cursor)

    def get_devicestatus(self, limit: int = 2000) -> list[dict[str, Any]]:
        """Fetch latest devicestatus, sorted by created_at."""
        cursor = self.db.devicestatus.find().sort("created_at", -1).limit(limit)
        return list(cursor)

    def get_profile(self) -> dict[str, Any] | None:
        """Fetch the most recent profile."""
        cursor = self.db.profile.find().sort("created_at", -1).limit(1)
        docs = list(cursor)
        return docs[0] if docs else None

dao = NightscoutDAO()
