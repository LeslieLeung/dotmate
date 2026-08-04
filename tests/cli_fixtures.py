"""Shared helpers for CLI regression tests (no real network)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

from PIL import Image

from dotmate.platforms.base import ApiResponse, DeviceStatus, ImagePayload, TextPayload


CLI_CONFIG_YAML = """\
platforms:
  quote0:
    api_key: "test-quote0-key"
  zectrix:
    api_key: "zt_test-zectrix-key"
request_interval: 0.0
devices:
  - name: "office"
    device_id: "office-device-001"
    platform: quote0
    show_battery_icon: true
    show_battery_percentage: true
    show_refresh_time: false
    schedules:
      - cron: "*/5 * * * *"
        type: "work"
        params:
          clock_in: "09:00"
          clock_out: "18:00"
      - cron: "0 12 * * *"
        type: "title_image"
        params:
          main_title: "Lunch"
          sub_title: "From schedule"
      - cron: null
        type: "title_image"
        params:
          main_title: "Skipped"
      - cron: "0 8 * * *"
        type: "not_a_real_type"
        params: {}
  - name: "note4"
    device_id: "AA:BB:CC:DD:EE:FF"
    platform: zectrix
    schedules:
      - cron: "*/15 * * * *"
        type: "title_image"
        params:
          main_title: "Note4"
          page_id: "1"
"""


def write_cli_config(tmp_path: Path, content: str = CLI_CONFIG_YAML) -> Path:
    """Write a temporary config.yaml and return its path."""
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def write_minimal_png(path: Path, width: int = 32, height: int = 16) -> Path:
    """Write a tiny 1-bit PNG for image-scenario tests."""
    buf = BytesIO()
    Image.new("1", (width, height), 1).save(buf, format="PNG")
    path.write_bytes(buf.getvalue())
    return path


class RecordingClient:
    """Stub PlatformClient that records display_* calls without network I/O."""

    def __init__(self) -> None:
        self.images: list[tuple[str, ImagePayload]] = []
        self.texts: list[tuple[str, TextPayload]] = []

    def display_image(self, device_id: str, payload: ImagePayload) -> ApiResponse:
        self.images.append((device_id, payload))
        return ApiResponse(message="recorded image")

    def display_text(self, device_id: str, payload: TextPayload) -> ApiResponse:
        self.texts.append((device_id, payload))
        return ApiResponse(message="recorded text")

    def get_device_status(self, device_id: str) -> DeviceStatus:
        return DeviceStatus(
            deviceId=device_id,
            status={"battery": "100%"},
            renderInfo={},
        )


def make_stub_create_client(client: Optional[Any] = None) -> MagicMock:
    """Return a MagicMock suitable for PlatformRegistry.create_client."""
    stub = client if client is not None else RecordingClient()
    return MagicMock(return_value=stub)


# Minimal fake payloads for external-API views (shape matches renderers).
FAKE_WAKATIME = {
    "data": {
        "grand_total": {"total_seconds": 3661},
        "languages": [
            {"name": "Python", "total_seconds": 1800},
            {"name": "TypeScript", "total_seconds": 900},
        ],
    }
}

FAKE_UMAMI = {
    "pageviews": {"value": 1200, "prev": 1000},
    "visitors": {"value": 300, "prev": 250},
    "visits": {"value": 400, "prev": 350},
    "bounces": {"value": 50, "prev": 40},
    "totaltime": {"value": 3600, "prev": 3000},
}

FAKE_GITHUB = {
    "login": "tester",
    "followers": {"totalCount": 42},
    "repositories": {"nodes": [{"stargazerCount": 10}, {"stargazerCount": 5}]},
    "contributionsCollection": {
        "contributionCalendar": {
            "totalContributions": 100,
            "weeks": [
                {
                    "contributionDays": [
                        {
                            "date": f"2024-01-{day:02d}",
                            "contributionCount": day % 4,
                            "color": "#ebedf0",
                        }
                        for day in range(1, 8)
                    ]
                }
                for _ in range(52)
            ],
        }
    },
}

FAKE_CODE_PLAN = {
    "quotas": [
        {"name": "five_hour", "utilization": 42.5, "resets_at": "2024-01-01T12:00:00Z"},
        {"name": "seven_day", "utilization": 18.0, "resets_at": "2024-01-07T00:00:00Z"},
    ]
}

SCENARIO_MIN_PARAMS: dict[str, dict[str, Any]] = {
    "work": {"clock_in": "09:00", "clock_out": "18:00"},
    "text": {"message": "hello", "title": "Test"},
    "title_image": {"main_title": "Hello", "sub_title": "World", "dither_type": "NONE"},
    "code_status": {
        "wakatime_url": "https://wakatime.example",
        "wakatime_api_key": "key",
        "wakatime_user_id": "user",
        "dither_type": "NONE",
    },
    "umami_stats": {
        "umami_host": "https://umami.example",
        "umami_website_id": "site-1",
        "umami_api_key": "key",
        "umami_time_range": "7d",
        "dither_type": "NONE",
    },
    "github_contributions": {
        "github_username": "tester",
        "github_token": "ghp_test",
        "dither_type": "NONE",
    },
    "code_plan_usage": {
        "api_url": "http://onwatch.example",
        "provider": "anthropic",
        "api_username": "user",
        "api_password": "pass",
        "dither_type": "NONE",
    },
}
