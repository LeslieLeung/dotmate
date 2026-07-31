"""Vendor registry for external device cloud APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

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
from dotmate.platforms.zectrix import ZectrixClient


class VendorClient(Protocol):
    """Remote-management surface used by device cloud vendors.

    Callers must gate on ``VendorDefinition.capabilities`` before invoking
    methods. Zectrix currently exposes device discovery via ``list_devices``
    but not status/settings.
    """

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
    description: str
    capabilities: tuple[str, ...]
    client_factory: Callable[[str, float], Any]
    credential_hint: str = ""
    supports_credential_validation: bool = False

    def create_client(self, api_key: str, request_interval: float) -> Any:
        return self.client_factory(api_key, request_interval)

    @property
    def supports_device_discovery(self) -> bool:
        return "devices" in self.capabilities

    @property
    def supports_status(self) -> bool:
        return "status" in self.capabilities


_VENDORS = {
    "mindreset": VendorDefinition(
        id="mindreset",
        label="MindReset",
        description="MindReset Open API for Quote/0 devices.",
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
        credential_hint="Paste your MindReset Open API key. Devices can be synced after saving.",
        supports_credential_validation=True,
    ),
    "zectrix": VendorDefinition(
        id="zectrix",
        label="Zectrix",
        description="Zectrix Open API for Note 4 devices.",
        capabilities=("devices",),
        client_factory=lambda api_key, request_interval: ZectrixClient(
            api_key, request_interval=request_interval
        ),
        credential_hint=(
            "Paste your Zectrix API key (typically starts with zt_). "
            "Devices can be synced after saving."
        ),
        supports_credential_validation=True,
    ),
}


def list_vendors() -> list[VendorDefinition]:
    return list(_VENDORS.values())


def get_vendor(vendor: str) -> VendorDefinition:
    try:
        return _VENDORS[vendor]
    except KeyError as exc:
        raise ValueError(f"Unsupported vendor: {vendor}") from exc


def create_vendor_client(vendor: str, api_key: str, request_interval: float) -> Any:
    return get_vendor(vendor).create_client(api_key, request_interval)
