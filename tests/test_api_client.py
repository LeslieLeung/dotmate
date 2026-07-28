import pytest
from pydantic import ValidationError

from dotmate.api import api as api_module
from dotmate.api.api import (
    DeviceIntervalSettings,
    DeviceSettingsUpdate,
    DeviceSleepSettings,
    DotClient,
)


class Response:
    def __init__(self, data, ok=True):
        self.data = data
        self.ok = ok
        self.status_code = 200 if ok else 500
        self.text = "response"
        self.encoding = None

    def json(self):
        return self.data

    def raise_for_status(self):
        raise RuntimeError("request failed")


def test_clients_with_same_api_key_share_rate_limit(monkeypatch):
    with DotClient._rate_limiters_lock:
        DotClient._rate_limiters.clear()

    clock = iter([100.0, 100.0, 100.0, 101.0])
    sleeps = []
    monkeypatch.setattr(api_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(api_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        api_module.requests,
        "request",
        lambda method, url, **kwargs: Response({"ok": True}),
    )

    DotClient("shared-key", request_interval=1)._rate_limited_request(
        "GET", "https://example.test/first"
    )
    DotClient("shared-key", request_interval=1)._rate_limited_request(
        "GET", "https://example.test/second"
    )

    assert sleeps == [1.0]


def test_list_devices_uses_open_devices_endpoint(monkeypatch):
    client = DotClient("secret", request_interval=0)
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response(
            [
                {
                    "id": "device-1",
                    "alias": "Desk",
                    "series": "quote",
                    "model": "quote_0",
                    "edition": 1,
                }
            ]
        )

    monkeypatch.setattr(client, "_rate_limited_request", request)
    devices = client.list_devices()
    assert devices[0].id == "device-1"
    assert calls[0][0:2] == (
        "GET",
        "https://dot.mindreset.tech/api/authV2/open/devices",
    )
    assert calls[0][2]["headers"]["Authorization"] == "Bearer secret"


def test_get_device_status_parses_nested_status_and_render_info(monkeypatch):
    client = DotClient("secret", request_interval=0)
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response(
            {
                "deviceId": "device-1",
                "alias": "Desk",
                "status": {
                    "version": "1.2.3",
                    "current": "Power Active",
                    "description": "Ready",
                    "battery": "Charging",
                    "wifi": "-62 dBm",
                },
                "renderInfo": {
                    "last": "12/18/2025 14:11",
                    "current": {
                        "rotated": False,
                        "border": 0,
                        "image": ["https://example.test/current.png"],
                    },
                    "next": {
                        "battery": "12/18/2025 17:11",
                        "power": "12/18/2025 14:16",
                    },
                },
            }
        )

    monkeypatch.setattr(client, "_rate_limited_request", request)
    status = client.get_device_status("device-1")

    assert status.status.battery == "Charging"
    assert status.renderInfo.current.image == [
        "https://example.test/current.png"
    ]
    assert calls[0][0:2] == (
        "GET",
        "https://dot.mindreset.tech/api/authV2/open/device/device-1/status",
    )
    assert calls[0][2]["headers"]["Authorization"] == "Bearer secret"


def test_device_settings_update_posts_partial_payload_then_reads_canonical_state(
    monkeypatch,
):
    client = DotClient("secret", request_interval=0)
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "POST":
            return Response({"message": "updated"})
        return Response(
            {
                "alias": "Desk",
                "timezone": "Asia/Shanghai",
                "interval": {"powerMs": 60000, "batteryMs": 120000},
                "sleep": {"enabled": True, "start": "22:00", "end": "07:00"},
            }
        )

    monkeypatch.setattr(client, "_rate_limited_request", request)
    result = client.update_device_settings(
        "device-1", DeviceSettingsUpdate(alias="Desk")
    )
    assert result.alias == "Desk"
    assert calls[0][0] == "POST"
    assert calls[0][2]["json"] == {"alias": "Desk"}
    assert calls[1][0] == "GET"


def test_device_settings_validation_matches_vendor_limits():
    with pytest.raises(ValidationError):
        DeviceIntervalSettings(powerMs=61000)
    with pytest.raises(ValidationError):
        DeviceSleepSettings(enabled=True, start="22:00", end="22:00")


def test_list_device_content_accepts_vendor_image_reference_objects(monkeypatch):
    client = DotClient("secret", request_interval=0)

    def request(method, url, **kwargs):
        return Response(
            [
                {
                    "type": "IMAGE_API",
                    "key": "image-task",
                    "image": {"key": "dot/user/example.png"},
                    "border": 0,
                    "ditherType": "DIFFUSION",
                    "ditherKernel": "FLOYD_STEINBERG",
                }
            ]
        )

    monkeypatch.setattr(client, "_rate_limited_request", request)
    tasks = client.list_device_content("device-1")
    assert tasks[0].image == {"key": "dot/user/example.png"}
