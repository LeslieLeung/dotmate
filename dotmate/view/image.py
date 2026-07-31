import io
import re
from datetime import datetime
from typing import Optional, Type, Literal, Union
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

from dotmate.platforms.base import ImagePayload, PlatformClient, PlatformProfile
from dotmate.view.base import BaseView
from dotmate.font import FontManager


# Reference resolution used to derive ``display_scale`` (Quote/0 baseline).
REFERENCE_WIDTH = 296
REFERENCE_HEIGHT = 152


class ImageParams(BaseModel):
    image_data: bytes
    link: Optional[str] = None
    border: Optional[Literal[0, 1]] = None
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
    task_key: Optional[str] = None
    task_alias: Optional[Union[str, int]] = None
    # Zectrix Note 4 page slot (1-5); also mapped via task_key when unset
    page_id: Optional[Union[str, int]] = None


class ImageView(BaseView):
    """Base view handler for image display with resolution-adaptive layout.

    Resolution is taken from a ``PlatformProfile`` (or defaults to Quote/0
    296x152). Layout helpers ``_sz`` (font/metric scaling) and ``_py``
    (proportional Y positions) make subclasses render correctly at any
    resolution without hardcoding pixel offsets.
    """

    SCALE_FACTOR = 2

    def __init__(
        self,
        client: PlatformClient,
        device_id: str,
        profile: Optional[PlatformProfile] = None,
    ):
        super().__init__(client, device_id)
        self.font_manager = FontManager()
        self.custom_font_name: Optional[str] = None
        self.font_weight: Optional[int] = None
        self.enable_supersampling: bool = True
        self.show_battery_icon: bool = False
        self.show_battery_percentage: bool = False
        self.show_refresh_time: bool = False

        self.profile = profile
        # Instance-level resolution (Quote/0 296x152 by default).
        self.DISPLAY_WIDTH = profile.width if profile else REFERENCE_WIDTH
        self.DISPLAY_HEIGHT = profile.height if profile else REFERENCE_HEIGHT

    def set_display_size(self, width: int, height: int) -> None:
        """Configure canvas resolution for the target device (legacy hook)."""
        self.DISPLAY_WIDTH = width
        self.DISPLAY_HEIGHT = height

    # ------------------------------------------------------------------ #
    # Resolution-adaptive helpers
    # ------------------------------------------------------------------ #
    @property
    def display_scale(self) -> float:
        """Geometric-mean scale factor vs the 296x152 reference resolution."""
        return (
            (self.DISPLAY_WIDTH / REFERENCE_WIDTH)
            * (self.DISPLAY_HEIGHT / REFERENCE_HEIGHT)
        ) ** 0.5

    def _s(self, value: int) -> int:
        """Scale a pixel value by the supersampling factor (no-op when off)."""
        return value * self.SCALE_FACTOR if self.enable_supersampling else value

    def _sz(self, base: int) -> int:
        """Font/metric size: base value scaled to the current resolution.

        ``base`` is expressed in reference-resolution (296x152) units; the
        result additionally reflects supersampling.
        """
        return self._s(int(base * self.display_scale))

    def _py(self, ratio: float) -> int:
        """Proportional Y position as a fraction of the canvas height."""
        canvas_h = self._s(self.DISPLAY_HEIGHT)
        return int(canvas_h * ratio)

    def _create_canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        """Create a canvas for rendering. Uses supersampled grayscale when enabled, 1-bit otherwise."""
        if self.enable_supersampling:
            image = Image.new('L', (self._s(self.DISPLAY_WIDTH), self._s(self.DISPLAY_HEIGHT)), 255)
        else:
            image = Image.new('1', (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), 1)
        draw = ImageDraw.Draw(image)
        return image, draw

    def _finalize_image(self, image: Image.Image) -> bytes:
        """Finalize image to PNG bytes. Downscales and thresholds when supersampling is enabled."""
        if self.enable_supersampling:
            image = image.resize((self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), Image.Resampling.LANCZOS)
            image = image.point(lambda x: 0 if x < 128 else 255, '1')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.read()

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return ImageParams

    def _get_font(self, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Get font with specified size, using custom settings if configured."""
        return self.font_manager.get_font(size, self.custom_font_name, self.font_weight)

    @staticmethod
    def _battery_string(runtime_status: object) -> str:
        """Extract battery text from dict or structured DeviceRuntimeStatus."""
        if isinstance(runtime_status, dict):
            return runtime_status.get("battery", "") or ""
        return getattr(runtime_status, "battery", None) or ""

    def _draw_overlay(self, image_data: bytes) -> bytes:
        """Draw battery and refresh time overlay in bottom-right corner."""
        try:
            img = Image.open(io.BytesIO(image_data))
            original_mode = img.mode
            img = img.convert("RGB")
            draw = ImageDraw.Draw(img)
            font = self.font_manager.get_font(int(10 * self.display_scale), "Hack-Bold", None)

            canvas_width, canvas_height = img.size
            overlay_h = int(14 * self.display_scale)
            y_pos = canvas_height - overlay_h

            # Gather battery info if needed
            battery_pct: Optional[int] = None
            charging = False
            if self.show_battery_icon or self.show_battery_percentage:
                try:
                    status = self.client.get_device_status(self.device_id)
                    battery_str = self._battery_string(status.status)
                    match = re.search(r"(\d+)", battery_str)
                    if match:
                        battery_pct = int(match.group(1))
                    charging = (
                        "充电中" == battery_str or "Power Connected" == battery_str
                    )
                except Exception:
                    battery_pct = None

            # --- First pass: measure total overlay width ---
            padding = max(2, int(2 * self.display_scale))
            total_width = padding
            icon_w, icon_h, cap_w = (
                int(12 * self.display_scale),
                int(7 * self.display_scale),
                int(2 * self.display_scale),
            )
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
                    total_width += int(8 * self.display_scale)
                if charging:
                    plus_bbox = font.getbbox("+")
                    pw = plus_bbox[2] - plus_bbox[0]
                    total_width += pw
                if self.show_battery_percentage and battery_pct is not None:
                    pct_str = f"{battery_pct}%"
                    pct_bbox = font.getbbox(pct_str)
                    ptw = pct_bbox[2] - pct_bbox[0]
                    total_width += ptw + int(3 * self.display_scale)
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
                x -= tw + int(8 * self.display_scale)

            if has_battery:
                if charging:
                    draw.text((x - pw, y_pos), "+", fill=(0, 0, 0), font=font)
                    x -= pw

                if self.show_battery_percentage and pct_str:
                    draw.text((x - ptw, y_pos), pct_str, fill=(0, 0, 0), font=font)
                    x -= ptw + int(3 * self.display_scale)

                if self.show_battery_icon:
                    body_x = x - icon_w - cap_w
                    body_y = y_pos + (overlay_h - icon_h) // 2

                    draw.rectangle(
                        [body_x, body_y, body_x + icon_w - 1, body_y + icon_h - 1],
                        outline=(0, 0, 0),
                        fill=(255, 255, 255),
                    )
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
                    cap_x = body_x + icon_w
                    cap_y = body_y + 2
                    draw.rectangle(
                        [cap_x, cap_y, cap_x + cap_w - 1, cap_y + icon_h - 5],
                        fill=(0, 0, 0),
                    )

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

    def _build_payload(self, image_params: ImageParams) -> ImagePayload:
        """Convert internal ImageParams into a vendor-neutral ImagePayload."""
        # Prefer page_id (Note 4); fall back to task_key for Quote/0 / shared configs
        task_key = image_params.task_key
        if image_params.page_id is not None and task_key is None:
            task_key = str(image_params.page_id)

        return ImagePayload(
            image_bytes=image_params.image_data,
            link=image_params.link,
            border=image_params.border,
            dither_type=image_params.dither_type,
            dither_kernel=image_params.dither_kernel,
            task_key=task_key,
            task_alias=image_params.task_alias,
            page_id=image_params.page_id,
        )

    def execute(self, params: BaseModel) -> None:
        """Send image to device via the platform-neutral payload."""
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

        payload = self._build_payload(image_params)

        try:
            response = self.client.display_image(self.device_id, payload)
            print(
                f"Image sent to {self.device_id} "
                f"({self.DISPLAY_WIDTH}x{self.DISPLAY_HEIGHT}): "
                f"{len(image_params.image_data)} bytes (Response: {response.message})"
            )
        except Exception as e:
            print(f"Error sending image to {self.device_id}: {e}")
