import io
from datetime import datetime, timedelta
from typing import Type, Optional, Literal
import requests
from pydantic import BaseModel
from dotmate.view.image import ImageView, ImageParams
from PIL import Image, ImageDraw


class UmamiStatsParams(BaseModel):
    umami_host: str
    umami_website_id: str
    umami_api_key: str
    umami_time_range: str = "24h"  # e.g., "7d", "24h", "30d"
    title: Optional[str] = None  # Custom title, defaults to "Umami Stats ({time_range})"
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


class UmamiStatsView(ImageView):
    """View handler for displaying Umami website statistics as an image."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "Hack-Bold"

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return UmamiStatsParams

    def _parse_time_range(self, time_range: str) -> tuple[int, int]:
        """Parse time range string (e.g., '7d', '24h') and return start/end timestamps in milliseconds."""
        now = datetime.now()

        # Extract number and unit
        try:
            if time_range.endswith('h'):
                hours = int(time_range[:-1])
                start_time = now - timedelta(hours=hours)
            elif time_range.endswith('d'):
                days = int(time_range[:-1])
                start_time = now - timedelta(days=days)
            elif time_range.endswith('w'):
                weeks = int(time_range[:-1])
                start_time = now - timedelta(weeks=weeks)
            else:
                # Default to 24 hours if format is unknown
                start_time = now - timedelta(hours=24)
        except (ValueError, IndexError):
            # Default to 24 hours if parsing fails
            start_time = now - timedelta(hours=24)

        # Convert to milliseconds timestamps
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(now.timestamp() * 1000)

        return start_timestamp, end_timestamp

    def _fetch_umami_stats(self, params: UmamiStatsParams) -> dict:
        """Fetch statistics from Umami API"""
        start_at, end_at = self._parse_time_range(params.umami_time_range)

        url = f"{params.umami_host.rstrip('/')}/api/websites/{params.umami_website_id}/stats"
        headers = {
            "Authorization": f"Bearer {params.umami_api_key}"
        }
        query_params = {
            "startAt": start_at,
            "endAt": end_at
        }

        response = requests.get(url, headers=headers, params=query_params, timeout=10)
        response.raise_for_status()
        return response.json()

    def _format_number(self, value: int) -> str:
        """Format number with K/M suffix for large numbers."""
        if value >= 1000000:
            return f"{value / 1000000:.1f}M"
        elif value >= 1000:
            return f"{value / 1000:.1f}K"
        else:
            return str(value)

    def _format_time(self, seconds: int) -> str:
        """Format seconds into human readable duration."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"

    def _calculate_change_percentage(self, current: int, previous: int) -> tuple[str, str]:
        """Calculate percentage change and return (percentage_string, triangle_symbol)."""
        if previous == 0:
            if current > 0:
                return "100%", "▲"
            else:
                return "0%", ""

        change = ((current - previous) / previous) * 100
        if change > 0:
            return f"{change:.0f}%", "▲"
        elif change < 0:
            return f"{abs(change):.0f}%", "▼"
        else:
            return "0%", ""

    def _generate_stats_image(self, stats_data: dict, time_range: str, title: Optional[str] = None) -> bytes:
        """Generate a 296x152 PNG image with website statistics and return PNG binary data."""
        width, height = 296, 152
        image = Image.new("1", (width, height), 1)  # 1-bit mode, 1=white, 0=black
        draw = ImageDraw.Draw(image)

        try:
            # Extract data (current and previous values)
            pageviews = stats_data.get("pageviews", {}).get("value", 0)
            pageviews_prev = stats_data.get("pageviews", {}).get("prev", 0)
            visitors = stats_data.get("visitors", {}).get("value", 0)
            visitors_prev = stats_data.get("visitors", {}).get("prev", 0)
            visits = stats_data.get("visits", {}).get("value", 0)
            visits_prev = stats_data.get("visits", {}).get("prev", 0)
            bounces = stats_data.get("bounces", {}).get("value", 0)
            bounces_prev = stats_data.get("bounces", {}).get("prev", 0)
            totaltime = stats_data.get("totaltime", {}).get("value", 0)
            totaltime_prev = stats_data.get("totaltime", {}).get("prev", 0)

            # Format values
            pv_str = self._format_number(pageviews)
            uv_str = self._format_number(visitors)
            visits_str = self._format_number(visits)
            bounces_str = self._format_number(bounces)
            totaltime_str = self._format_time(totaltime)

            # Calculate changes
            pv_change, pv_symbol = self._calculate_change_percentage(pageviews, pageviews_prev)
            uv_change, uv_symbol = self._calculate_change_percentage(visitors, visitors_prev)
            visits_change, visits_symbol = self._calculate_change_percentage(visits, visits_prev)
            bounces_change, bounces_symbol = self._calculate_change_percentage(bounces, bounces_prev)
            totaltime_change, totaltime_symbol = self._calculate_change_percentage(totaltime, totaltime_prev)

            # Font sizes
            title_font_size = 18
            label_font_size = 14
            value_font_size = 20
            change_font_size = 12  # Larger font for triangles and percentage

            # Get fonts
            title_font = self._get_font(title_font_size)
            label_font = self._get_font(label_font_size)
            value_font = self._get_font(value_font_size)
            change_font = self._get_font(change_font_size)

            # Draw title
            if title:
                title_text = f"{title} ({time_range})"
            else:
                title_text = f"Umami Stats ({time_range})"
            bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_width = bbox[2] - bbox[0]
            title_x = (width - title_width) // 2
            draw.text((title_x, 8), title_text, fill=0, font=title_font)

            # Layout: First row (PV, UV), Second row (visits, bounces, totaltime)
            # First row starts at y=32
            row1_y = 32
            row2_y = 90

            # First row: 2 columns (PV, UV)
            col_width_2 = width // 2

            # Draw PV (left column)
            pv_label = "PV"
            bbox = draw.textbbox((0, 0), pv_label, font=label_font)
            label_width = bbox[2] - bbox[0]
            draw.text(((col_width_2 - label_width) // 2, row1_y), pv_label, fill=0, font=label_font)

            bbox = draw.textbbox((0, 0), pv_str, font=value_font)
            value_width = bbox[2] - bbox[0]
            value_x = (col_width_2 - value_width) // 2
            draw.text((value_x, row1_y + 18), pv_str, fill=0, font=value_font)

            # Draw PV change with large triangle before percentage
            pv_combined = f"{pv_symbol}{pv_change}" if pv_symbol else pv_change
            bbox = draw.textbbox((0, 0), pv_combined, font=change_font)
            combined_width = bbox[2] - bbox[0]
            draw.text(((col_width_2 - combined_width) // 2, row1_y + 42), pv_combined, fill=0, font=change_font)

            # Draw UV (right column)
            uv_label = "UV"
            bbox = draw.textbbox((0, 0), uv_label, font=label_font)
            label_width = bbox[2] - bbox[0]
            draw.text((col_width_2 + (col_width_2 - label_width) // 2, row1_y), uv_label, fill=0, font=label_font)

            bbox = draw.textbbox((0, 0), uv_str, font=value_font)
            value_width = bbox[2] - bbox[0]
            value_x = col_width_2 + (col_width_2 - value_width) // 2
            draw.text((value_x, row1_y + 18), uv_str, fill=0, font=value_font)

            # Draw UV change with large triangle before percentage
            uv_combined = f"{uv_symbol}{uv_change}" if uv_symbol else uv_change
            bbox = draw.textbbox((0, 0), uv_combined, font=change_font)
            combined_width = bbox[2] - bbox[0]
            draw.text((col_width_2 + (col_width_2 - combined_width) // 2, row1_y + 42), uv_combined, fill=0, font=change_font)

            # Second row: 3 columns (visits, bounces, totaltime)
            col_width_3 = width // 3

            # Draw visits (left column)
            visits_label = "Visits"
            bbox = draw.textbbox((0, 0), visits_label, font=label_font)
            label_width = bbox[2] - bbox[0]
            draw.text(((col_width_3 - label_width) // 2, row2_y), visits_label, fill=0, font=label_font)

            bbox = draw.textbbox((0, 0), visits_str, font=value_font)
            value_width = bbox[2] - bbox[0]
            value_x = (col_width_3 - value_width) // 2
            draw.text((value_x, row2_y + 16), visits_str, fill=0, font=value_font)

            # Draw visits change with large triangle before percentage
            visits_combined = f"{visits_symbol}{visits_change}" if visits_symbol else visits_change
            bbox = draw.textbbox((0, 0), visits_combined, font=change_font)
            combined_width = bbox[2] - bbox[0]
            draw.text(((col_width_3 - combined_width) // 2, row2_y + 38), visits_combined, fill=0, font=change_font)

            # Draw bounces (middle column)
            bounces_label = "Bounces"
            bbox = draw.textbbox((0, 0), bounces_label, font=label_font)
            label_width = bbox[2] - bbox[0]
            draw.text((col_width_3 + (col_width_3 - label_width) // 2, row2_y), bounces_label, fill=0, font=label_font)

            bbox = draw.textbbox((0, 0), bounces_str, font=value_font)
            value_width = bbox[2] - bbox[0]
            value_x = col_width_3 + (col_width_3 - value_width) // 2
            draw.text((value_x, row2_y + 16), bounces_str, fill=0, font=value_font)

            # Draw bounces change with large triangle before percentage
            bounces_combined = f"{bounces_symbol}{bounces_change}" if bounces_symbol else bounces_change
            bbox = draw.textbbox((0, 0), bounces_combined, font=change_font)
            combined_width = bbox[2] - bbox[0]
            draw.text((col_width_3 + (col_width_3 - combined_width) // 2, row2_y + 38), bounces_combined, fill=0, font=change_font)

            # Draw totaltime (right column)
            time_label = "Time"
            bbox = draw.textbbox((0, 0), time_label, font=label_font)
            label_width = bbox[2] - bbox[0]
            draw.text((2 * col_width_3 + (col_width_3 - label_width) // 2, row2_y), time_label, fill=0, font=label_font)

            bbox = draw.textbbox((0, 0), totaltime_str, font=value_font)
            value_width = bbox[2] - bbox[0]
            value_x = 2 * col_width_3 + (col_width_3 - value_width) // 2
            draw.text((value_x, row2_y + 16), totaltime_str, fill=0, font=value_font)

            # Draw totaltime change with large triangle before percentage
            totaltime_combined = f"{totaltime_symbol}{totaltime_change}" if totaltime_symbol else totaltime_change
            bbox = draw.textbbox((0, 0), totaltime_combined, font=change_font)
            combined_width = bbox[2] - bbox[0]
            draw.text((2 * col_width_3 + (col_width_3 - combined_width) // 2, row2_y + 38), totaltime_combined, fill=0, font=change_font)

            # Convert to PNG binary data
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.read()

        except Exception as e:
            raise Exception(f"Error generating stats image: {e}")

    def execute(self, params: BaseModel) -> None:
        """Generate Umami stats image and send to device."""
        stats_params = UmamiStatsParams(**params.model_dump())

        try:
            # Fetch Umami stats
            stats_data = self._fetch_umami_stats(stats_params)

            # Generate image
            image_data = self._generate_stats_image(stats_data, stats_params.umami_time_range, stats_params.title)

            # Create ImageParams and use parent execute
            image_params = ImageParams(
                image_data=image_data,
                link=stats_params.link,
                border=stats_params.border,
                dither_type=stats_params.dither_type,
                dither_kernel=stats_params.dither_kernel,
            )

            # Use parent's execute method
            super().execute(image_params)

        except requests.RequestException as e:
            print(f"API Error fetching Umami stats: {e}")
            # Generate error image with zeros
            error_data = {
                "pageviews": {"value": 0},
                "visitors": {"value": 0},
                "visits": {"value": 0},
                "bounces": {"value": 0},
                "totaltime": {"value": 0}
            }
            try:
                image_data = self._generate_stats_image(error_data, stats_params.umami_time_range, stats_params.title)
                image_params = ImageParams(
                    image_data=image_data,
                    link=stats_params.link,
                    border=stats_params.border,
                    dither_type=stats_params.dither_type,
                    dither_kernel=stats_params.dither_kernel,
                )
                super().execute(image_params)
            except Exception as img_error:
                print(f"Failed to generate error image: {img_error}")

        except Exception as e:
            print(f"Error in UmamiStatsView: {e}")
