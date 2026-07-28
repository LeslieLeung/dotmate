"""Zectrix (Note 4) wire-format models.

The Zectrix open API consumes multipart form data rather than JSON. These
models describe the fields that make up a Zectrix image push request; the
client assembles the actual multipart payload.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ZectrixImageRequest:
    """Fields for POST /devices/{deviceId}/display/image (multipart)."""

    image_bytes: bytes
    dither: bool = True
    page_id: Optional[str] = None


__all__ = ["ZectrixImageRequest"]
