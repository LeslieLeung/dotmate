import io
from typing import Type, Optional, Literal
import requests
from pydantic import BaseModel
from dotmate.view.image import ImageView, ImageParams
from PIL import Image, ImageDraw


class CodePlanUsageParams(BaseModel):
    api_url: str
    provider: str = "anthropic"
    api_username: Optional[str] = None
    api_password: Optional[str] = None
    link: Optional[str] = None
    border: Optional[int] = None
    dither_type: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = "NONE"
    dither_kernel: Optional[
        Literal[
            "THRESHOLD",
            "ATKINSON",
            "BURKES",
            "FLOYD_STEINBERG",
            "SIERRA2",
            "STUCKI",
            "JARVIS_JUDICE_NINKE",
            "DIFFUSION_ROW",
            "DIFFUSION_COLUMN",
            "DIFFUSION_2D",
        ]
    ] = None


class CodePlanUsageView(ImageView):
    """View handler for displaying code plan usage quotas as progress bars."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "Hack-Bold"

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return CodePlanUsageParams

    def _fetch_usage_data(self, params: CodePlanUsageParams) -> dict:
        url = f"{params.api_url.rstrip('/')}/api/current"
        auth = None
        if params.api_username and params.api_password:
            auth = (params.api_username, params.api_password)
        response = requests.get(
            url, params={"provider": params.provider}, auth=auth, timeout=10
        )
        response.raise_for_status()
        return response.json()

    def _draw_progress_bar(
        self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int,
        utilization: float,
    ) -> None:
        """Draw a progress bar with outline and filled portion."""
        draw.rectangle([x, y, x + width, y + height], outline=0, fill=1)
        fill_width = int((min(utilization, 100) / 100) * (width - 2))
        if fill_width > 0:
            draw.rectangle([x + 1, y + 1, x + 1 + fill_width, y + height - 1], fill=0)

    def _generate_usage_image(self, data: dict, error: bool = False) -> bytes:
        width, height = 296, 152
        image = Image.new("1", (width, height), 1)
        draw = ImageDraw.Draw(image)

        quotas = data.get("quotas", [])
        quota_map = {q["name"]: q for q in quotas if "name" in q}
        display_quotas = [
            q for name in ("five_hour", "seven_day")
            if (q := quota_map.get(name)) is not None
        ]

        title_font = self._get_font(16)
        label_font = self._get_font(13)
        small_font = self._get_font(11)

        title_text = "Code Plan Usage"
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_w = bbox[2] - bbox[0]
        draw.text(((width - title_w) // 2, 5), title_text, fill=0, font=title_font)

        margin_x = 10
        bar_width = width - 2 * margin_x
        bar_height = 14
        section_starts = [30, 84]

        for i, quota in enumerate(display_quotas):
            y_base = section_starts[i]
            display_name = quota.get("displayName", "Unknown")
            utilization = quota.get("utilization", 0)
            time_until_reset = quota.get("timeUntilReset")

            util_text = "ERR" if error else f"{utilization:.0f}%"

            # Label left, percentage right
            draw.text((margin_x, y_base), display_name, fill=0, font=label_font)
            bbox = draw.textbbox((0, 0), util_text, font=label_font)
            util_w = bbox[2] - bbox[0]
            draw.text((width - margin_x - util_w, y_base), util_text, fill=0, font=label_font)

            # Progress bar
            bar_y = y_base + 18
            self._draw_progress_bar(draw, margin_x, bar_y, bar_width, bar_height, utilization)

            # Reset time below the bar
            if error:
                reset_text = "N/A"
            else:
                reset_text = f"resets in {time_until_reset}" if time_until_reset else "N/A"
            bbox = draw.textbbox((0, 0), reset_text, font=small_font)
            reset_w = bbox[2] - bbox[0]
            draw.text(
                (width - margin_x - reset_w, bar_y + bar_height + 3),
                reset_text, fill=0, font=small_font,
            )

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()

    def execute(self, params: BaseModel) -> None:
        usage_params = CodePlanUsageParams(**params.model_dump())

        try:
            data = self._fetch_usage_data(usage_params)
            image_data = self._generate_usage_image(data)

            image_params = ImageParams(
                image_data=image_data,
                link=usage_params.link,
                border=usage_params.border,
                dither_type=usage_params.dither_type,
                dither_kernel=usage_params.dither_kernel,
            )
            super().execute(image_params)

        except requests.RequestException as e:
            print(f"API Error fetching code plan usage: {e}")
            error_data = {"quotas": [
                {"displayName": "5-Hour Limit", "utilization": 0, "timeUntilReset": "N/A"},
                {"displayName": "Weekly All-Model", "utilization": 0, "timeUntilReset": "N/A"},
            ]}
            try:
                image_data = self._generate_usage_image(error_data, error=True)
                image_params = ImageParams(
                    image_data=image_data,
                    link=usage_params.link,
                    border=usage_params.border,
                    dither_type=usage_params.dither_type,
                    dither_kernel=usage_params.dither_kernel,
                )
                super().execute(image_params)
            except Exception as img_error:
                print(f"Failed to generate error image: {img_error}")

        except Exception as e:
            print(f"Error in CodePlanUsageView: {e}")
