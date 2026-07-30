"""Device model registry: hardware display capabilities separate from vendors."""

from __future__ import annotations

from dataclasses import dataclass

from dotmate.platforms.base import PlatformProfile


# Quote/0-oriented image protocol fields exposed by the MindReset image API.
QUOTE0_IMAGE_FIELDS: frozenset[str] = frozenset(
    {
        "link",
        "border",
        "dither_type",
        "dither_kernel",
        "task_key",
        "task_alias",
    }
)

# Note 4-oriented image protocol fields for the Zectrix multipart API.
NOTE4_IMAGE_FIELDS: frozenset[str] = frozenset(
    {
        "dither_type",
        "page_id",
    }
)


@dataclass(frozen=True)
class DeviceModelDefinition:
    """Concrete hardware product and its display/rendering capabilities."""

    id: str
    vendor_id: str
    label: str
    description: str
    width: int
    height: int
    supports_text: bool
    supports_image: bool
    supports_battery_overlay: bool
    supports_page_id: bool
    device_id_label: str
    device_id_example: str
    allowed_image_fields: frozenset[str]

    def to_profile(self) -> PlatformProfile:
        return PlatformProfile(
            name=self.id,
            width=self.width,
            height=self.height,
            supports_text=self.supports_text,
            supports_image=self.supports_image,
            description=self.label,
        )

    @property
    def display_capabilities(self) -> tuple[str, ...]:
        caps: list[str] = []
        if self.supports_text:
            caps.append("text")
        if self.supports_image:
            caps.append("image")
        if self.supports_battery_overlay:
            caps.append("battery_overlay")
        if self.supports_page_id:
            caps.append("page_id")
        caps.append("refresh_time_overlay")
        return tuple(caps)


_DEVICE_MODELS: dict[str, DeviceModelDefinition] = {
    "quote0": DeviceModelDefinition(
        id="quote0",
        vendor_id="mindreset",
        label="Quote/0",
        description="MindReset Quote/0 e-ink display (296×152, text + image).",
        width=296,
        height=152,
        supports_text=True,
        supports_image=True,
        supports_battery_overlay=True,
        supports_page_id=False,
        device_id_label="Device ID",
        device_id_example="device-xxxxxxxx",
        allowed_image_fields=QUOTE0_IMAGE_FIELDS,
    ),
    "note4": DeviceModelDefinition(
        id="note4",
        vendor_id="zectrix",
        label="Note 4",
        description="Zectrix Note 4 e-ink display (400×300, image only).",
        width=400,
        height=300,
        supports_text=False,
        supports_image=True,
        supports_battery_overlay=False,
        supports_page_id=True,
        device_id_label="MAC Address / Device ID",
        device_id_example="AA:BB:CC:DD:EE:FF",
        allowed_image_fields=NOTE4_IMAGE_FIELDS,
    ),
}

DEFAULT_DEVICE_MODEL = "quote0"


def list_device_models(vendor_id: str | None = None) -> list[DeviceModelDefinition]:
    models = list(_DEVICE_MODELS.values())
    if vendor_id is None:
        return models
    return [model for model in models if model.vendor_id == vendor_id]


def get_device_model(model_id: str) -> DeviceModelDefinition:
    try:
        return _DEVICE_MODELS[model_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported device model: {model_id}") from exc


def default_model_for_vendor(vendor_id: str) -> DeviceModelDefinition:
    models = list_device_models(vendor_id)
    if not models:
        raise ValueError(f"No device models registered for vendor: {vendor_id}")
    return models[0]


def assert_model_matches_vendor(model_id: str, vendor_id: str) -> DeviceModelDefinition:
    model = get_device_model(model_id)
    if model.vendor_id != vendor_id:
        raise ValueError(
            f"Device model '{model_id}' belongs to vendor '{model.vendor_id}', "
            f"not '{vendor_id}'"
        )
    return model
