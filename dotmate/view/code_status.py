import io
from datetime import datetime
from typing import Type, Optional, Literal
import requests
from pydantic import BaseModel
from dotmate.view.image import ImageView, ImageParams
from PIL import Image, ImageDraw
import base64


class CodeStatusParams(BaseModel):
    wakatime_url: str
    wakatime_api_key: str
    wakatime_user_id: str
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
            "DIFFUSION2_D",
        ]
    ] = None


class CodeStatusView(ImageView):
    """View handler for displaying Wakatime coding status as an image."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "Hack-Bold"

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return CodeStatusParams

    def _fetch_wakatime_data(self, params: CodeStatusParams) -> dict:
        """Fetch data from Wakatime API"""
        url = f"{params.wakatime_url.rstrip('/')}/users/{params.wakatime_user_id}/statusbar/today"
        headers = {
            "Authorization": f"Basic {base64.b64encode(params.wakatime_api_key.encode()).decode()}"
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def _format_time_duration(self, total_seconds: float) -> str:
        """Format seconds into human readable duration"""
        if total_seconds < 60:
            return f"{int(total_seconds)}s"
        elif total_seconds < 3600:
            minutes = int(total_seconds // 60)
            return f"{minutes}m"
        else:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"

    def _generate_status_image(self, wakatime_data: dict) -> bytes:
        """Generate a 296x152 PNG image with coding status and return PNG binary data."""
        width, height = 296, 152
        image = Image.new("1", (width, height), 1)  # 1-bit mode, 1=white, 0=black
        draw = ImageDraw.Draw(image)

        try:
            # Extract data
            data = wakatime_data.get("data", {})
            total_seconds = data.get("grand_total", {}).get("total_seconds", 0)
            languages = data.get("languages", [])

            # Prepare content
            if total_seconds > 0:
                total_time_str = self._format_time_duration(total_seconds)

                # Create content lines
                lines = [
                    "Today's Coding",
                    f"Total: {total_time_str}",
                ]

                # Add top languages with their time
                if languages:
                    lines.append("Top Languages:")
                    # Show top 3 languages with their time
                    for lang in languages[:3]:
                        lang_name = lang["name"]
                        lang_seconds = lang.get("total_seconds", 0)
                        lang_time = self._format_time_duration(lang_seconds)
                        lines.append(f"{lang_name}: {lang_time}")

            else:
                lines = ["Today's Coding", "No coding time", "tracked today"]

            # Font sizes (increased)
            title_font_size = 22
            content_font_size = 16
            small_font_size = 14

            # Get fonts (use custom font if set)
            title_font = self._get_font(title_font_size)
            content_font = self._get_font(content_font_size)
            small_font = self._get_font(small_font_size)

            # Calculate line heights (adjusted for larger fonts)
            title_line_height = 28
            content_line_height = 20
            small_line_height = 18

            # Calculate total height dynamically
            total_height = title_line_height
            for line in lines[1:]:
                if ":" in line and line not in ["Total:", "Top Languages:"]:  # Language entries
                    total_height += small_line_height
                else:
                    total_height += content_line_height

            # Start position (centered vertically)
            start_y = max((height - total_height) // 2, 8)

            # Draw title (first line)
            title_text = lines[0]
            bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_width = bbox[2] - bbox[0]
            title_x = (width - title_width) // 2
            draw.text((title_x, start_y), title_text, fill=0, font=title_font)

            # Draw content lines
            current_y = start_y + title_line_height
            for line in lines[1:]:
                if ":" in line and line not in ["Total:", "Top Languages:"]:  # Language entries - smaller font, center aligned
                    bbox = draw.textbbox((0, 0), line, font=small_font)
                    line_width = bbox[2] - bbox[0]
                    line_x = (width - line_width) // 2
                    draw.text((line_x, current_y), line, fill=0, font=small_font)
                    current_y += small_line_height
                else:  # Regular content - center aligned
                    font_to_use = content_font
                    bbox = draw.textbbox((0, 0), line, font=font_to_use)
                    line_width = bbox[2] - bbox[0]
                    line_x = (width - line_width) // 2
                    draw.text((line_x, current_y), line, fill=0, font=font_to_use)
                    current_y += content_line_height

            # Add timestamp at bottom right
            timestamp = datetime.now().strftime("%H:%M")
            timestamp_font = self._get_font(12)
            bbox = draw.textbbox((0, 0), timestamp, font=timestamp_font)
            timestamp_width = bbox[2] - bbox[0]
            draw.text(
                (width - timestamp_width - 8, height - 16),
                timestamp,
                fill=0,
                font=timestamp_font,
            )

            # Convert to PNG binary data
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.read()

        except Exception as e:
            raise Exception(f"Error generating status image: {e}")

    def execute(self, params: BaseModel) -> None:
        """Generate coding status image and send to device."""
        status_params = CodeStatusParams(**params.model_dump())

        try:
            # Fetch Wakatime data
            wakatime_data = self._fetch_wakatime_data(status_params)

            # Generate image
            image_data = self._generate_status_image(wakatime_data)

            # Create ImageParams and use parent execute
            image_params = ImageParams(
                image_data=image_data,
                link=status_params.link,
                border=status_params.border,
                dither_type=status_params.dither_type,
                dither_kernel=status_params.dither_kernel,
            )

            # Use parent's execute method
            super().execute(image_params)

        except requests.RequestException as e:
            print(f"API Error fetching Wakatime data: {e}")
            # Generate error image
            error_data = {"data": {"grand_total": {"total_seconds": 0}}}
            try:
                image_data = self._generate_status_image(error_data)
                image_params = ImageParams(
                    image_data=image_data,
                    link=status_params.link,
                    border=status_params.border,
                    dither_type=status_params.dither_type,
                    dither_kernel=status_params.dither_kernel,
                )
                super().execute(image_params)
            except Exception as img_error:
                print(f"Failed to generate error image: {img_error}")

        except Exception as e:
            print(f"Error in CodeStatusView: {e}")
