"""Vendor registry for external device services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from dotmate.api.api import (
    ApiResponse,
    DeviceSettings,
    DeviceSettingsUpdate,
    DeviceStatus,
    DeviceTask,
    DotClient,
    RemoteDevice,
    TimezoneInfo,
)


class VendorClient(Protocol):
    def list_devices(self) -> list[RemoteDevice]: ...

    def get_device_status(self, device_id: str) -> DeviceStatus: ...

    def get_device_settings(self, device_id: str) -> DeviceSettings: ...

    def update_device_settings(
        self, device_id: str, payload: DeviceSettingsUpdate
    ) -> DeviceSettings: ...

    def list_timezones(self) -> list[TimezoneInfo]: ...

    def switch_next_content(self, device_id: str) -> ApiResponse: ...

    def list_device_content(
        self, device_id: str, task_type: str = "loop"
    ) -> list[DeviceTask]: ...


@dataclass(frozen=True)
class VendorDefinition:
    id: str
    label: str
    capabilities: tuple[str, ...]
    client_factory: Callable[[str, float], VendorClient]

    def create_client(self, api_key: str, request_interval: float) -> VendorClient:
        return self.client_factory(api_key, request_interval)


_VENDORS = {
    "mindreset": VendorDefinition(
        id="mindreset",
        label="MindReset",
        capabilities=(
            "devices",
            "status",
            "settings",
            "timezones",
            "next",
            "content",
        ),
        client_factory=lambda api_key, request_interval: DotClient(
            api_key, request_interval=request_interval
        ),
    )
}


def list_vendors() -> list[VendorDefinition]:
    return list(_VENDORS.values())


def get_vendor(vendor: str) -> VendorDefinition:
    try:
        return _VENDORS[vendor]
    except KeyError as exc:
        raise ValueError(f"Unsupported vendor: {vendor}") from exc


def create_vendor_client(
    vendor: str, api_key: str, request_interval: float
) -> VendorClient:
    return get_vendor(vendor).create_client(api_key, request_interval)
