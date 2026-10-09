from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    mongodb_uri: str
    mongodb_database: str
    timezone: str = "Africa/Casablanca"
    glucose_units: str = "mg/dL"
    target_low: int = 70
    target_high: int = 180
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cache_dir: str = "./cache"
    auth_secret_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"], 
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
