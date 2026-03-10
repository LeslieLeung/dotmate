import base64
import io
import re
import time
from datetime import datetime
from typing import Optional, Type, Literal, Union
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from dotmate.api.api import DisplayImageRequest
from dotmate.view.base import BaseView
from dotmate.font import FontManager


class ImageParams(BaseModel):
    image_data: bytes
    link: Optional[str] = None
    border: Optional[int] = None
    dither_type: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = None
    dither_kernel: Optional[Literal[
        "THRESHOLD",
        "ATKINSON",
        "BURKES",
        "FLOYD_STEINBERG",
        "SIERRA2",
        "STUCKI",
        "JARVIS_JUDICE_NINKE",
        "DIFFUSION_ROW",
        "DIFFUSION_COLUMN",
        "DIFFUSION_2D"
    ]] = None


class ImageView(BaseView):
    """Base view handler for image display with optional font management."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.font_manager = FontManager()
        self.custom_font_name: Optional[str] = None
        self.font_weight: Optional[int] = None
        self.show_battery_icon: bool = False
        self.show_battery_percentage: bool = False
        self.show_refresh_time: bool = False

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return ImageParams

    def _get_font(self, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Get font with specified size, using custom settings if configured.

        Subclasses can override custom_font_name and font_weight in __init__.
        """
        return self.font_manager.get_font(size, self.custom_font_name, self.font_weight)

    def _encode_image_data(self, image_data: bytes) -> str:
        """Encode PNG binary data to base64."""
        return base64.b64encode(image_data).decode('utf-8')

    def _draw_overlay(self, image_data: bytes) -> bytes:
        """Draw battery and refresh time overlay in bottom-right corner."""
        try:
            img = Image.open(io.BytesIO(image_data))
            original_mode = img.mode
            img = img.convert("RGB")
            draw = ImageDraw.Draw(img)
            font = self.font_manager.get_font(10, "Hack-Bold", None)

            canvas_width, canvas_height = img.size
            overlay_h = 14
            y_pos = canvas_height - overlay_h

            # Gather battery info if needed
            battery_pct: Optional[int] = None
            charging = False
            if self.show_battery_icon or self.show_battery_percentage:
                try:
                    status = self.client.get_device_status(self.device_id)
                    battery_str = status.status.get("battery", "")
                    match = re.search(r"(\d+)", battery_str)
                    if match:
                        battery_pct = int(match.group(1))
                    charging = (
                        "充电中" == battery_str or "Power Connected" == battery_str
                    )
                except Exception:
                    battery_pct = None

            # --- First pass: measure total overlay width ---
            padding = 2
            total_width = padding
            icon_w, icon_h, cap_w = 12, 7, 2
            tw = 0
            ptw = 0
            pw = 0
            time_str = ""
            pct_str = ""

            if self.show_refresh_time:
                time_str = datetime.now().strftime("%H:%M")
                bbox = font.getbbox(time_str)
                tw = bbox[2] - bbox[0]
                total_width += tw

            has_battery = (
                self.show_battery_icon or self.show_battery_percentage
            ) and (battery_pct is not None or charging)

            if has_battery:
                if self.show_refresh_time:
                    total_width += 8  # gap between time and battery group
                if charging:
                    plus_bbox = font.getbbox("+")
                    pw = plus_bbox[2] - plus_bbox[0]
                    total_width += pw
                if self.show_battery_percentage and battery_pct is not None:
                    pct_str = f"{battery_pct}%"
                    pct_bbox = font.getbbox(pct_str)
                    ptw = pct_bbox[2] - pct_bbox[0]
                    total_width += ptw + 3
                if self.show_battery_icon:
                    total_width += icon_w + cap_w + 2

            total_width += padding

            # --- Clear white background behind overlay ---
            draw.rectangle(
                [
                    canvas_width - total_width,
                    y_pos,
                    canvas_width - 1,
                    canvas_height - 1,
                ],
                fill=(255, 255, 255),
            )

            # --- Second pass: draw elements right-to-left ---
            x = canvas_width - padding

            if self.show_refresh_time:
                draw.text((x - tw, y_pos), time_str, fill=(0, 0, 0), font=font)
                x -= tw + 8

            if has_battery:
                if charging:
                    draw.text((x - pw, y_pos), "+", fill=(0, 0, 0), font=font)
                    x -= pw

                if self.show_battery_percentage and pct_str:
                    draw.text((x - ptw, y_pos), pct_str, fill=(0, 0, 0), font=font)
                    x -= ptw + 3

                if self.show_battery_icon:
                    body_x = x - icon_w - cap_w
                    body_y = y_pos + (overlay_h - icon_h) // 2

                    # Body outline
                    draw.rectangle(
                        [body_x, body_y, body_x + icon_w - 1, body_y + icon_h - 1],
                        outline=(0, 0, 0),
                        fill=(255, 255, 255),
                    )
                    # Fill proportional to battery %
                    if battery_pct is not None:
                        fill_w = max(0, int((icon_w - 2) * battery_pct / 100))
                        if fill_w > 0:
                            draw.rectangle(
                                [
                                    body_x + 1,
                                    body_y + 1,
                                    body_x + fill_w,
                                    body_y + icon_h - 2,
                                ],
                                fill=(0, 0, 0),
                            )
                    # Terminal cap
                    cap_x = body_x + icon_w
                    cap_y = body_y + 2
                    draw.rectangle(
                        [cap_x, cap_y, cap_x + cap_w - 1, cap_y + icon_h - 5],
                        fill=(0, 0, 0),
                    )

            # Convert back without dithering to preserve small overlay elements
            if original_mode in ("1", "L"):
                img_out = img.convert("1", dither=Image.Dither.NONE)
            else:
                img_out = img
            buf = io.BytesIO()
            img_out.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            print(f"Warning: overlay rendering failed, using original image: {e}")
            return image_data

    def execute(self, params: BaseModel) -> None:
        """Send image to device."""
        image_params = ImageParams(**params.model_dump())

        if (
            self.show_battery_icon
            or self.show_battery_percentage
            or self.show_refresh_time
        ):
            image_params = ImageParams(
                **{
                    **params.model_dump(),
                    "image_data": self._draw_overlay(image_params.image_data),
                }
            )
            time.sleep(1)

        # Encode image data
        image_base64 = self._encode_image_data(image_params.image_data)

        # Create display request
        request = DisplayImageRequest(
            refreshNow=True,
            image=image_base64,
            link=image_params.link,
            border=image_params.border,
            ditherType=image_params.dither_type,
            ditherKernel=image_params.dither_kernel,
        )

        try:
            response = self.client.display_image(self.device_id, request)
            print(f"Image sent to {self.device_id}: {len(image_params.image_data)} bytes (Response: {response.message})")
        except Exception as e:
            print(f"Error sending image to {self.device_id}: {e}")