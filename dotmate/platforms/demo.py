"""Demo client: saves pushed content to local files instead of hitting an API.

Implements the same neutral contract as real platform clients, so views and
the scheduler can run end-to-end against it for local preview/testing.
"""

from datetime import datetime
from pathlib import Path

from dotmate.platforms.base import (
    ApiResponse,
    DeviceStatus,
    ImagePayload,
    PlatformClient,
    TextPayload,
)


class DemoClient(PlatformClient):
    """Mock client that saves images to files instead of sending to an API."""

    def __init__(self, output_dir: str = "demos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def display_text(self, device_id: str, payload: TextPayload) -> ApiResponse:
        print(f"[Demo] Text message would be sent to {device_id}:")
        print(f"  Title: {payload.title}")
        print(f"  Message: {payload.message}")
        print(f"  Signature: {payload.signature}")
        if payload.icon:
            print(f"  Icon: {payload.icon}")
        if payload.link:
            print(f"  Link: {payload.link}")
        if payload.task_key:
            print(f"  Task Key: {payload.task_key}")
        if payload.task_alias is not None:
            print(f"  Task Alias: {payload.task_alias}")
        if payload.styles:
            print(f"  Styles: {payload.styles}")
        return ApiResponse(message="Demo mode: text message not sent")

    def display_image(self, device_id: str, payload: ImagePayload) -> ApiResponse:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"demo_{timestamp}.png"
        output_path = self.output_dir / filename

        with open(output_path, "wb") as f:
            f.write(payload.image_bytes)

        print(f"[Demo] Image saved to: {output_path}")
        print(f"  Size: {len(payload.image_bytes)} bytes")
        if payload.link:
            print(f"  Link: {payload.link}")
        if payload.border is not None:
            print(f"  Border: {payload.border}")
        if payload.dither_type:
            print(f"  Dither Type: {payload.dither_type}")
        if payload.dither_kernel:
            print(f"  Dither Kernel: {payload.dither_kernel}")
        if payload.page_id is not None:
            print(f"  Page ID: {payload.page_id}")

        return ApiResponse(message=f"Demo mode: image saved to {output_path}")

    def get_device_status(self, device_id: str) -> DeviceStatus:
        return DeviceStatus(deviceId=device_id, status={"battery": "100%"}, renderInfo={})
