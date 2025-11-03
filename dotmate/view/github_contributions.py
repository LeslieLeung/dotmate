import io
from datetime import datetime, timedelta
from typing import Type, Optional, Literal
import requests
from pydantic import BaseModel
from dotmate.view.image import ImageView, ImageParams
from PIL import Image, ImageDraw


class GitHubContributionsParams(BaseModel):
    github_username: str
    github_token: str
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


class GitHubContributionsView(ImageView):
    """View handler for displaying GitHub user contributions as an image."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "Hack-Bold"

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return GitHubContributionsParams

    def _fetch_github_data(self, params: GitHubContributionsParams) -> dict:
        """Fetch user data from GitHub GraphQL API"""
        url = "https://api.github.com/graphql"
        headers = {
            "Authorization": f"Bearer {params.github_token}",
            "Content-Type": "application/json",
        }

        query = """
        query($username: String!) {
          user(login: $username) {
            login
            followers { totalCount }
            repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
              nodes { stargazerCount }
            }
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    date
                    contributionCount
                    color
                  }
                }
              }
            }
          }
        }
        """

        payload = {"query": query, "variables": {"username": params.github_username}}

        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Check for GraphQL errors
        if "errors" in data:
            raise Exception(f"GraphQL Error: {data['errors']}")

        return data["data"]["user"]

    def _calculate_contribution_level(self, count: int) -> int:
        """Calculate contribution level (0-3) based on count."""
        if count == 0:
            return 0
        elif count <= 3:
            return 1
        elif count <= 9:
            return 2
        else:
            return 3

    def _get_grayscale_for_level(self, level: int) -> int:
        """Get grayscale value (0=black, 1=white) for contribution level."""
        # For 1-bit images: 0 = black, 1 = white
        grayscale_map = {
            0: 1,  # 0 contributions = white
            1: 1,  # 1-3 contributions = light (will use pattern)
            2: 0,  # 4-9 contributions = medium (will use pattern)
            3: 0,  # 10+ contributions = black
        }
        return grayscale_map.get(level, 1)

    def _draw_contribution_cell(self, draw, x, y, size, level):
        """Draw a single contribution cell with pattern based on level."""
        if level == 0:
            # Empty - white
            draw.rectangle([x, y, x + size, y + size], fill=1, outline=0)
        elif level == 1:
            # Light - white with sparse dots
            draw.rectangle([x, y, x + size, y + size], fill=1, outline=0)
            # Add sparse pattern
            for dx in range(0, size, 3):
                for dy in range(0, size, 3):
                    if (dx + dy) % 4 == 0:
                        draw.point((x + dx, y + dy), fill=0)
        elif level == 2:
            # Medium - checkerboard pattern
            draw.rectangle([x, y, x + size, y + size], fill=1, outline=0)
            for dx in range(size):
                for dy in range(size):
                    if (dx + dy) % 2 == 0:
                        draw.point((x + dx, y + dy), fill=0)
        else:
            # Dark - solid black
            draw.rectangle([x, y, x + size, y + size], fill=0, outline=0)

    def _format_number(self, value: int) -> str:
        """Format number with K/M suffix for large numbers."""
        if value >= 1000000:
            return f"{value / 1000000:.1f}M"
        elif value >= 1000:
            return f"{value / 1000:.1f}K"
        else:
            return str(value)

    def _generate_github_image(self, github_data: dict) -> bytes:
        """Generate a 296x152 PNG image with GitHub contributions and return PNG binary data."""
        width, height = 296, 152
        image = Image.new("1", (width, height), 1)  # 1-bit mode, 1=white, 0=black
        draw = ImageDraw.Draw(image)

        try:
            # Extract user data
            username = github_data.get("login", "Unknown")
            followers = github_data.get("followers", {}).get("totalCount", 0)

            # Calculate total stars
            repositories = github_data.get("repositories", {}).get("nodes", [])
            total_stars = sum(repo.get("stargazerCount", 0) for repo in repositories)

            # Get contribution data
            contribution_calendar = github_data.get("contributionsCollection", {}).get(
                "contributionCalendar", {}
            )
            weeks = contribution_calendar.get("weeks", [])

            # --- Top Section: User Info ---
            top_section_height = 60

            # Font sizes
            username_font_size = 16
            stats_font_size = 12

            username_font = self._get_font(username_font_size)
            stats_font = self._get_font(stats_font_size)

            # Draw username at top left
            draw.text((10, 8), username, fill=0, font=username_font)

            # Draw stats below username
            followers_text = f"Followers: {self._format_number(followers)}"
            stars_text = f"Stars: {self._format_number(total_stars)}"

            draw.text((10, 28), followers_text, fill=0, font=stats_font)
            draw.text((10, 44), stars_text, fill=0, font=stats_font)

            # Draw separator line
            draw.line([(0, top_section_height), (width, top_section_height)], fill=0)

            # --- Bottom Section: Contribution Grid ---
            grid_top = top_section_height + 8
            grid_bottom = height - 5
            grid_left = 5
            grid_right = width - 5

            # Available space
            available_width = grid_right - grid_left
            available_height = grid_bottom - grid_top

            # Gap between cells
            gap = 2

            # Calculate how many weeks we can display
            # Each week needs 7 rows (days), calculate cell size based on height
            cell_size_from_height = (available_height - (7 - 1) * gap) // 7

            # Calculate how many weeks can fit in the width with this cell size
            max_weeks = (available_width + gap) // (cell_size_from_height + gap)

            # Limit to available data
            num_weeks = min(max_weeks, len(weeks))

            # Use the cell size calculated from height
            cell_size = max(cell_size_from_height, 4)  # Minimum 4 pixels

            # Get the most recent weeks
            last_weeks = weeks[-num_weeks:] if len(weeks) >= num_weeks else weeks

            # Center the grid horizontally
            total_grid_width = num_weeks * (cell_size + gap) - gap
            grid_left = (width - total_grid_width) // 2

            # Draw contribution grid
            for week_index, week in enumerate(last_weeks):
                contribution_days = week.get("contributionDays", [])
                for day_index, day in enumerate(contribution_days):
                    x = grid_left + week_index * (cell_size + gap)
                    y = grid_top + day_index * (cell_size + gap)

                    count = day.get("contributionCount", 0)
                    level = self._calculate_contribution_level(count)

                    self._draw_contribution_cell(draw, x, y, cell_size, level)

            # Convert to PNG binary data
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.read()

        except Exception as e:
            raise Exception(f"Error generating GitHub contributions image: {e}")

    def _generate_error_image(self) -> bytes:
        """Generate an error image when GitHub API fails."""
        width, height = 296, 152
        image = Image.new("1", (width, height), 1)
        draw = ImageDraw.Draw(image)

        error_font = self._get_font(16)
        small_font = self._get_font(12)

        # Draw error message
        error_text = "GitHub API Error"
        bbox = draw.textbbox((0, 0), error_text, font=error_font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2

        draw.text((text_x, 50), error_text, fill=0, font=error_font)

        sub_text = "Check credentials"
        bbox = draw.textbbox((0, 0), sub_text, font=small_font)
        sub_width = bbox[2] - bbox[0]
        sub_x = (width - sub_width) // 2

        draw.text((sub_x, 80), sub_text, fill=0, font=small_font)

        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M")
        timestamp_font = self._get_font(10)
        draw.text((width - 40, height - 15), timestamp, fill=0, font=timestamp_font)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()

    def execute(self, params: BaseModel) -> None:
        """Generate GitHub contributions image and send to device."""
        github_params = GitHubContributionsParams(**params.model_dump())

        try:
            # Fetch GitHub data
            github_data = self._fetch_github_data(github_params)

            # Generate image
            image_data = self._generate_github_image(github_data)

            # Create ImageParams and use parent execute
            image_params = ImageParams(
                image_data=image_data,
                link=github_params.link,
                border=github_params.border,
                dither_type=github_params.dither_type,
                dither_kernel=github_params.dither_kernel,
            )

            # Use parent's execute method
            super().execute(image_params)

        except requests.RequestException as e:
            print(f"API Error fetching GitHub data: {e}")
            # Generate error image
            try:
                image_data = self._generate_error_image()
                image_params = ImageParams(
                    image_data=image_data,
                    link=github_params.link,
                    border=github_params.border,
                    dither_type=github_params.dither_type,
                    dither_kernel=github_params.dither_kernel,
                )
                super().execute(image_params)
            except Exception as img_error:
                print(f"Failed to generate error image: {img_error}")

        except Exception as e:
            print(f"Error in GitHubContributionsView: {e}")
