"""Zectrix Note 4 platform profile (400x300, image only)."""

from dotmate.platforms.base import PlatformProfile

NOTE4_PROFILE = PlatformProfile(
    name="zectrix",
    width=400,
    height=300,
    supports_text=False,
    supports_image=True,
    description="Zectrix Note 4",
)
