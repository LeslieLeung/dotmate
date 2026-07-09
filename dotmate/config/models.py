from typing import Any, Dict, List, Optional
from pydantic import BaseModel, model_validator
import yaml
from pathlib import Path

from dotmate.platforms.base import PlatformProfile
from dotmate.platforms.registry import PlatformRegistry

PlatformName = str  # validated against PlatformRegistry at load time
DEFAULT_PLATFORM: PlatformName = "quote0"


class Schedule(BaseModel):
    cron: Optional[str] = None
    type: str
    params: Optional[Dict[str, Any]] = None


class Device(BaseModel):
    name: str
    device_id: str
    # Platform/vendor name (quote0, zectrix, ...). Registered in PlatformRegistry.
    platform: PlatformName = DEFAULT_PLATFORM
    # Optional per-device API key override (uses platform key from Config if unset)
    api_key: Optional[str] = None
    show_battery_icon: bool = False
    show_battery_percentage: bool = False
    show_refresh_time: bool = False
    schedules: Optional[List[Schedule]] = None


class PlatformConfig(BaseModel):
    # Credentials for a platform (e.g. api_key). Kept generic so each platform
    # can evolve its config section without model churn.
    api_key: Optional[str] = None


class Config(BaseModel):
    # Per-platform configuration, keyed by platform name.
    platforms: Dict[str, PlatformConfig] = {}
    request_interval: float = 1.0
    devices: List[Device]

    @model_validator(mode="after")
    def validate_platforms_and_capabilities(self) -> "Config":
        # Lazily import the view registry to avoid an import cycle at module
        # load time (config <- view.factory <- views <- platforms).
        from dotmate.view.factory import ViewFactory

        for device in self.devices:
            platform = device.platform

            # 1. Platform must be registered.
            if not PlatformRegistry.is_supported(platform):
                raise ValueError(
                    f"Device '{device.name}' uses unknown platform '{platform}'. "
                    f"Supported: {PlatformRegistry.available()}"
                )

            profile: PlatformProfile = PlatformRegistry.get_profile(platform)

            # 2. Credentials: device override OR platform-level key.
            has_key = bool(device.api_key) or bool(
                self.platforms.get(platform) and self.platforms[platform].api_key
            )
            if not has_key:
                raise ValueError(
                    f"Device '{device.name}' (platform={platform}) requires an API "
                    f"key. Set platforms.{platform}.api_key in config or api_key "
                    "on the device."
                )

            # 3. Capability check: each scheduled scenario must be supported by
            #    the platform (e.g. text scenarios are rejected on image-only
            #    platforms like Zectrix Note 4).
            if device.schedules:
                for schedule in device.schedules:
                    if not ViewFactory.is_registered(schedule.type):
                        continue  # unknown types are reported later by the scheduler
                    requires_text = ViewFactory.requires_text(schedule.type)
                    if requires_text and not profile.supports_text:
                        raise ValueError(
                            f"Device '{device.name}' (platform={platform}) schedules "
                            f"a '{schedule.type}' task, but platform '{platform}' "
                            f"does not support text display."
                        )
        return self


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Config(**data)
