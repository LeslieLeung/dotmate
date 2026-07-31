"""Battery overlay must read structured DeviceStatus and plain dict status."""

from io import BytesIO
from unittest.mock import MagicMock

from PIL import Image

from dotmate.api.api import DeviceRuntimeStatus, DeviceStatus
from dotmate.view.image import ImageView


def _blank_png(width: int = 296, height: int = 152) -> bytes:
    buf = BytesIO()
    Image.new("1", (width, height), 1).save(buf, format="PNG")
    return buf.getvalue()


def test_battery_string_supports_dict_and_structured_status():
    assert ImageView._battery_string({"battery": "82%"}) == "82%"
    assert ImageView._battery_string(DeviceRuntimeStatus(battery="Charging")) == (
        "Charging"
    )
    assert ImageView._battery_string({}) == ""
    assert ImageView._battery_string(DeviceRuntimeStatus()) == ""


def test_draw_overlay_reads_battery_from_structured_device_status():
    client = MagicMock()
    client.get_device_status.return_value = DeviceStatus(
        deviceId="device-1",
        status=DeviceRuntimeStatus(battery="75%"),
    )
    view = ImageView(client, "device-1")
    view.show_battery_percentage = True

    result = view._draw_overlay(_blank_png())

    client.get_device_status.assert_called_once_with("device-1")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_draw_overlay_reads_battery_from_dict_status():
    client = MagicMock()
    client.get_device_status.return_value = MagicMock(
        status={"battery": "42%"},
    )
    view = ImageView(client, "device-1")
    view.show_battery_percentage = True

    result = view._draw_overlay(_blank_png())

    client.get_device_status.assert_called_once_with("device-1")
    assert isinstance(result, bytes)
    assert len(result) > 0
