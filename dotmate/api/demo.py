import base64
from datetime import datetime
from pathlib import Path
from dotmate.api.api import DisplayTextRequest, DisplayImageRequest, ApiResponse


class DemoClient:
    """Mock client that saves images to files instead of sending to API."""

    def __init__(self, output_dir: str = "demos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def display_text(self, payload: DisplayTextRequest) -> ApiResponse:
        """Mock text display - just return success."""
        print(f"[Demo] Text message would be sent:")
        print(f"  Title: {payload.title}")
        print(f"  Message: {payload.message}")
        return ApiResponse(message="Demo mode: text message not sent")

    def display_image(self, payload: DisplayImageRequest) -> ApiResponse:
        """Save image to file instead of sending to API."""
        # Decode base64 image
        image_data = base64.b64decode(payload.image)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"demo_{timestamp}.png"
        output_path = self.output_dir / filename

        # Save image
        with open(output_path, "wb") as f:
            f.write(image_data)

        print(f"[Demo] Image saved to: {output_path}")
        print(f"  Size: {len(image_data)} bytes")
        if payload.link:
            print(f"  Link: {payload.link}")
        if payload.border is not None:
            print(f"  Border: {payload.border}")
        if payload.ditherType:
            print(f"  Dither Type: {payload.ditherType}")
        if payload.ditherKernel:
            print(f"  Dither Kernel: {payload.ditherKernel}")

        return ApiResponse(message=f"Demo mode: image saved to {output_path}")
