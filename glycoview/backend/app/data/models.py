from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class SgvEntry(BaseModel):
    id: str = Field(alias="_id")
    type: str = "sgv"
    sgv: int
    date: int
    dateString: str | None = None
    direction: str | None = None
    device: str | None = None
    
    class Config:
        populate_by_name = True

class Treatment(BaseModel):
    id: str = Field(alias="_id")
    eventType: str
    created_at: str
    insulin: float | None = None
    carbs: float | None = None
    duration: float | None = None
    rate: float | None = None
    absolute: float | None = None
    profile: str | None = None
    targetTop: float | None = None
    targetBottom: float | None = None

    class Config:
        populate_by_name = True

class DeviceStatus(BaseModel):
    id: str = Field(alias="_id")
    device: str | None = None
    created_at: str
    openaps: dict[str, Any] | None = None
    pump: dict[str, Any] | None = None

    class Config:
        populate_by_name = True
