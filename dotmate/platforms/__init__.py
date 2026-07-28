"""Platform abstraction package.

Provides vendor-neutral payloads and a registry/factory for platform clients.
Views depend only on the neutral contract here; platform-specific clients live
under their own subpackages.
"""

from dotmate.platforms.base import (
    ApiResponse,
    DeviceStatus,
    ImagePayload,
    PlatformClient,
    PlatformProfile,
    TextPayload,
)
from dotmate.platforms.demo import DemoClient
from dotmate.platforms.quote0 import DotClient, QUOTE0_PROFILE
from dotmate.platforms.registry import PlatformRegistry, get_demo_client
from dotmate.platforms.zectrix import NOTE4_PROFILE, ZectrixClient

__all__ = [
    "ApiResponse",
    "DeviceStatus",
    "ImagePayload",
    "TextPayload",
    "PlatformClient",
    "PlatformProfile",
    "DemoClient",
    "DotClient",
    "ZectrixClient",
    "QUOTE0_PROFILE",
    "NOTE4_PROFILE",
    "PlatformRegistry",
    "get_demo_client",
]
