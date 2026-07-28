"""Platform abstraction layer.

Defines the vendor-neutral contract shared by all platform clients
(Quote/0, Zectrix, Demo) plus device-agnostic payloads so that views
never need to know about wire formats.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Shared response / status types
# --------------------------------------------------------------------------- #
class ApiResponse(BaseModel):
    message: str


class DeviceStatus(BaseModel):
    deviceId: str
    alias: Optional[str] = None
    location: Optional[str] = None
    status: dict = Field(default_factory=dict)
    renderInfo: dict = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Platform profile: resolution + capability descriptor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PlatformProfile:
    """Display and capability profile for a platform family."""

    name: str
    width: int
    height: int
    supports_text: bool
    supports_image: bool
    description: str


# --------------------------------------------------------------------------- #
# Neutral payloads (views build these; clients translate to wire format)
# --------------------------------------------------------------------------- #
DitherType = Literal["DIFFUSION", "ORDERED", "NONE"]
BorderColor = Literal[0, 1]


class ImagePayload(BaseModel):
    """Vendor-neutral description of an image to be pushed to a device.

    Carries raw PNG bytes plus common display options. Platform clients are
    responsible for converting this into their own wire format (e.g. base64
    JSON for Quote/0, multipart form for Zectrix).
    """

    image_bytes: bytes
    refresh_now: bool = True
    dither_type: Optional[DitherType] = None
    dither_kernel: Optional[str] = None
    border: Optional[BorderColor] = None
    link: Optional[str] = None
    task_key: Optional[str] = None
    task_alias: Optional[Union[str, int]] = None
    page_id: Optional[Union[str, int]] = None


class TextPayload(BaseModel):
    """Vendor-neutral description of a text message to be pushed to a device."""

    refresh_now: bool = True
    title: Optional[str] = None
    message: Optional[str] = None
    signature: Optional[str] = None
    icon: Optional[str] = None
    link: Optional[str] = None
    task_key: Optional[str] = None
    task_alias: Optional[Union[str, int]] = None
    # Opaque style descriptor (e.g. Quote/0 TextStyles); interpreted by the
    # platform client that supports styling.
    styles: Optional[dict] = None


# --------------------------------------------------------------------------- #
# Platform client contract
# --------------------------------------------------------------------------- #
class PlatformClient(ABC):
    """Abstract base for vendor clients.

    ``display_image`` is mandatory (all supported devices render images).
    ``display_text`` is optional: platforms without text support leave the
    default implementation which raises ``NotImplementedError``. Callers should
    consult the platform profile's ``supports_text`` flag before calling.
    """

    @abstractmethod
    def display_image(self, device_id: str, payload: ImagePayload) -> ApiResponse:
        ...

    def display_text(self, device_id: str, payload: TextPayload) -> ApiResponse:
        raise NotImplementedError(
            f"{type(self).__name__} does not support text display. "
            "Use image-based scenarios instead."
        )

    @abstractmethod
    def get_device_status(self, device_id: str) -> DeviceStatus:
        ...
