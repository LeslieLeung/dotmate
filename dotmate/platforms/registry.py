"""Platform registry: the single factory entry point for platforms.

Maps a platform name to its (client class, profile). ``create_client`` resolves
credentials from the loaded config (platform-level key, with an optional
per-device override) and instantiates the right client.
"""

from typing import Dict, Tuple, Type

from dotmate.platforms.base import PlatformClient, PlatformProfile
from dotmate.platforms.demo import DemoClient
from dotmate.platforms.quote0 import QUOTE0_PROFILE, DotClient
from dotmate.platforms.zectrix import NOTE4_PROFILE, ZectrixClient

# A device object only needs ``name`` and ``api_key`` attributes for credential
# resolution; the config ``Device`` model satisfies this duck-typing.


class PlatformRegistry:
    """Factory and registry for supported platforms."""

    _platforms: Dict[str, Tuple[Type[PlatformClient], PlatformProfile]] = {
        "quote0": (DotClient, QUOTE0_PROFILE),
        "zectrix": (ZectrixClient, NOTE4_PROFILE),
    }

    @classmethod
    def register(
        cls, name: str, client_class: Type[PlatformClient], profile: PlatformProfile
    ) -> None:
        cls._platforms[name] = (client_class, profile)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._platforms.keys())

    @classmethod
    def is_supported(cls, name: str) -> bool:
        return name in cls._platforms

    @classmethod
    def get_profile(cls, name: str) -> PlatformProfile:
        try:
            return cls._platforms[name][1]
        except KeyError:
            raise ValueError(
                f"Unknown platform '{name}'. Supported: {cls.available()}"
            )

    @classmethod
    def resolve_api_key(cls, name: str, config, device) -> str:
        """Resolve a device credential for client reuse.

        Credential resolution: ``device.api_key`` overrides the platform-level
        key configured under ``config.platforms[<name>]``.
        """
        if name not in cls._platforms:
            raise ValueError(
                f"Unknown platform '{name}'. Supported: {cls.available()}"
            )

        api_key = device.api_key
        if not api_key:
            platform_cfg = getattr(config, "platforms", {}).get(name)
            if platform_cfg is not None:
                api_key = getattr(platform_cfg, "api_key", None)
        if not api_key:
            raise ValueError(
                f"Device '{device.name}' uses platform '{name}' but no API key "
                f"is configured. Set platforms.{name}.api_key in config or "
                "api_key on the device."
            )
        return api_key

    @classmethod
    def create_client(cls, name: str, config, device) -> PlatformClient:
        """Build a client for ``name`` using credentials from config/device."""
        api_key = cls.resolve_api_key(name, config, device)
        client_class, _ = cls._platforms[name]

        request_interval = getattr(config, "request_interval", 1.0)
        return client_class(api_key, request_interval=request_interval)


def get_demo_client(output_dir: str = "demos") -> DemoClient:
    """Convenience helper returning a DemoClient for local preview."""
    return DemoClient(output_dir)
