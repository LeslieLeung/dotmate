from datetime import datetime
from typing import Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from apscheduler.triggers.cron import CronTrigger


def validate_cron(value: Optional[str]) -> Optional[str]:
    """Validate a crontab expression (5 fields). Allows None for ad-hoc schedules."""
    if value is None or value == "":
        return value
    try:
        CronTrigger.from_crontab(value)
    except ValueError as exc:
        raise ValueError(
            "Invalid cron expression. Expected 5 fields (minute hour day month day_of_week), "
            "e.g. '*/5 * * * *'"
        ) from exc
    return value


# ── Settings ──────────────────────────────────────────────


class SettingsRead(BaseModel):
    request_interval: float


class SettingsUpdate(BaseModel):
    request_interval: Optional[float] = Field(default=None, gt=0, le=60)


# ── Vendors and API credentials ──────────────────────────


class VendorRead(BaseModel):
    id: str
    label: str
    capabilities: list[str]


class ApiCredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    vendor: str = Field(default="mindreset", min_length=1, max_length=50)
    api_key: str = Field(min_length=1)

    @field_validator("name", "api_key")
    @classmethod
    def strip_credential_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value

    @field_validator("vendor")
    @classmethod
    def normalize_vendor(cls, value: str) -> str:
        return value.strip().lower()


class ApiCredentialBatchCreate(BaseModel):
    items: list[ApiCredentialCreate] = Field(min_length=1)


class ApiCredentialUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value


class ApiCredentialRead(BaseModel):
    id: int
    name: str
    vendor: str
    masked_key: str
    device_count: int


class DeviceSyncStats(BaseModel):
    fetched: int = 0
    created: int = 0
    linked: int = 0
    duplicates: int = 0


class ApiCredentialBatchResult(BaseModel):
    index: int
    name: str
    vendor: str
    status: Literal["success", "error"]
    credential: Optional[ApiCredentialRead] = None
    sync: Optional[DeviceSyncStats] = None
    error: Optional[str] = None


class ApiCredentialBatchResponse(BaseModel):
    results: list[ApiCredentialBatchResult]


class ApiCredentialSyncResult(BaseModel):
    credential: ApiCredentialRead
    sync: DeviceSyncStats


class ApiCredentialSyncAllResult(BaseModel):
    results: list[ApiCredentialBatchResult]


# ── Device ────────────────────────────────────────────────


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_id: str = Field(min_length=1, max_length=255)
    api_credential_id: int = Field(gt=0)
    show_battery_icon: bool = False
    show_battery_percentage: bool = False
    show_refresh_time: bool = False

    @field_validator("name", "device_id")
    @classmethod
    def strip_device_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    api_credential_id: Optional[int] = Field(default=None, gt=0)
    show_battery_icon: Optional[bool] = None
    show_battery_percentage: Optional[bool] = None
    show_refresh_time: Optional[bool] = None

    @field_validator("name", "device_id")
    @classmethod
    def strip_optional_device_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value


class ScheduleSummaryItem(BaseModel):
    label: str
    value: str


class ScheduleRead(BaseModel):
    id: int
    name: str
    cron: Optional[str]
    type: str
    type_label: str
    params: Optional[dict[str, Any]] = None
    summary: list[ScheduleSummaryItem] = Field(default_factory=list)


class RemoteDeviceStatusRead(BaseModel):
    remote_device_id: str
    alias: Optional[str] = None
    location: Optional[str] = None
    version: str
    current: str
    description: str
    battery: str
    wifi: str
    last_render: str
    rotated: bool
    border: int
    image_count: int
    next_battery_render: str
    next_power_render: str


class DeviceStatusPolicyRead(BaseModel):
    refresh_interval_minutes: Optional[int] = None
    effective_interval_minutes: Optional[int] = None
    interval_source: Optional[str] = None
    state: Literal["pending", "refreshing", "ready", "stale", "error"]
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    next_refresh_at: Optional[datetime] = None
    last_error: Optional[str] = None
    refresh_requested_at: Optional[datetime] = None


class DeviceStatusPolicyUpdate(BaseModel):
    refresh_interval_minutes: Optional[int] = Field(ge=1, le=720)


class DeviceStatusRefreshResponse(BaseModel):
    requested_at: datetime
    queued: int


class DeviceRead(BaseModel):
    id: int
    name: str
    device_id: str
    api_credential_id: int
    api_credential_name: str
    vendor: str
    vendor_capabilities: list[str]
    show_battery_icon: bool
    show_battery_percentage: bool
    show_refresh_time: bool
    remote_status: Optional[RemoteDeviceStatusRead] = None
    status_policy: DeviceStatusPolicyRead
    schedules: list[ScheduleRead] = []


# ── Remote device controls ───────────────────────────────


class RemoteSleepSettings(BaseModel):
    enabled: bool
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            hours, minutes = value.split(":")
            valid = (
                len(hours) == 2
                and len(minutes) == 2
                and 0 <= int(hours) <= 23
                and 0 <= int(minutes) <= 59
            )
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Time must use HH:mm format")
        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.start == self.end:
            raise ValueError("Sleep start and end must be different")
        return self


class RemoteDeviceSettingsRead(BaseModel):
    alias: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    power_interval_minutes: Optional[int] = None
    battery_interval_minutes: Optional[int] = None
    sleep: Optional[RemoteSleepSettings] = None


class RemoteDeviceSettingsUpdate(BaseModel):
    alias: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = None
    power_interval_minutes: Optional[int] = Field(default=None, ge=1, le=720)
    battery_interval_minutes: Optional[int] = Field(default=None, ge=1, le=720)
    sleep: Optional[RemoteSleepSettings] = None


class RemoteTimezoneRead(BaseModel):
    key: str
    name: str
    utc_offset_minutes: int
    utc_offset_label: str


class RemoteContentRead(BaseModel):
    type: str
    key: Optional[str] = None
    task_alias: Optional[str | int] = None
    refresh_now: Optional[bool] = None
    title: Optional[str] = None
    message: Optional[str] = None
    signature: Optional[str] = None
    link: Optional[str] = None
    border: Optional[int] = None
    dither_type: Optional[str] = None
    dither_kernel: Optional[str] = None
    has_icon: bool = False
    has_image: bool = False


class RemoteActionResponse(BaseModel):
    message: str


# ── Schedule ──────────────────────────────────────────────


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    cron: str = Field(min_length=1)
    type: str
    params: Optional[dict[str, Any]] = None

    @field_validator("name", "cron")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value

    _validate_cron = field_validator("cron")(validate_cron)


class ScheduleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    cron: Optional[str] = None
    type: Optional[str] = None
    params: Optional[dict[str, Any]] = None

    @field_validator("name", "cron")
    @classmethod
    def strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value

    _validate_cron = field_validator("cron")(validate_cron)
