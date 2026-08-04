from datetime import datetime
from typing import Optional
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Relationship


class Settings(SQLModel, table=True):
    """Global settings stored as a singleton row (id=1)."""

    id: int = Field(default=1, primary_key=True)
    request_interval: float = 1.0


class ApiCredential(SQLModel, table=True):
    __tablename__ = "api_credential"
    __table_args__ = (
        UniqueConstraint("vendor", "name", name="uq_api_credential_vendor_name"),
        UniqueConstraint("vendor", "api_key", name="uq_api_credential_vendor_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    vendor: str = Field(default="mindreset", index=True)
    api_key: str

    devices: list["Device"] = Relationship(back_populates="api_credential")


class Device(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    device_id: str
    api_credential_id: int = Field(foreign_key="api_credential.id", index=True)
    device_model: str = Field(default="quote0", index=True)
    show_battery_icon: bool = False
    show_battery_percentage: bool = False
    show_refresh_time: bool = False

    schedules: list["Schedule"] = Relationship(back_populates="device")
    api_credential: ApiCredential = Relationship(back_populates="devices")


class DeviceStatusRecord(SQLModel, table=True):
    """Latest cached vendor status and local refresh policy for one device."""

    __tablename__ = "device_status"

    device_id: int = Field(foreign_key="device.id", primary_key=True)
    payload_json: Optional[str] = None
    refresh_interval_minutes: Optional[int] = None
    effective_interval_minutes: Optional[int] = None
    interval_source: Optional[str] = None
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    next_refresh_at: Optional[datetime] = None
    last_error: Optional[str] = None
    refresh_requested_at: Optional[datetime] = None
    refresh_started_at: Optional[datetime] = None
    consecutive_failures: int = 0


class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id")
    name: str
    cron: Optional[str] = None
    type: str
    params: Optional[str] = None  # JSON-encoded dict

    device: Device = Relationship(back_populates="schedules")
