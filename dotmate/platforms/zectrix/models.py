"""Zectrix (Note 4) wire-format models.

The Zectrix open API consumes multipart form data for image push and JSON for
device listing. These models describe the wire shapes; the client translates
to/from vendor-neutral payloads.
"""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


@dataclass
class ZectrixImageRequest:
    """Fields for POST /devices/{deviceId}/display/image (multipart)."""

    image_bytes: bytes
    dither: bool = True
    page_id: Optional[str] = None


class ZectrixDeviceItem(BaseModel):
    """One entry from GET /devices."""

    device_id: str = Field(alias="deviceId")
    alias: Optional[str] = None
    board: Optional[str] = None

    model_config = {"populate_by_name": True}


__all__ = ["ZectrixImageRequest", "ZectrixDeviceItem"]
