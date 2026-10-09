from pymongo import MongoClient, ReadPreference
from app.core.config import settings

class Database:
    def __init__(self):
        self.client: MongoClient | None = None
        self.db = None

    def connect(self):
        """Connect to MongoDB in read-only mode (secondary preferred)."""
        self.client = MongoClient(
            settings.mongodb_uri,
            read_preference=ReadPreference.SECONDARY_PREFERRED,
            serverSelectionTimeoutMS=10000,
            tz_aware=True
        )
        self.db = self.client[settings.mongodb_database]
        # Verify connection
        self.db.command("ping")

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

db_manager = Database()

def get_db():
    if db_manager.db is None:
        db_manager.connect()
    return db_manager.db
