"""Device model catalogue endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from web.backend.device_models import list_device_models
from web.backend.routes.auth import verify_token
from web.backend.schemas import DeviceModelRead
from web.backend.vendors import get_vendor

router = APIRouter(prefix="/api/device-models", tags=["device-models"])


def _to_read(model) -> DeviceModelRead:
    return DeviceModelRead(
        id=model.id,
        vendor_id=model.vendor_id,
        label=model.label,
        description=model.description,
        width=model.width,
        height=model.height,
        supports_text=model.supports_text,
        supports_image=model.supports_image,
        supports_battery_overlay=model.supports_battery_overlay,
        supports_page_id=model.supports_page_id,
        device_id_label=model.device_id_label,
        device_id_example=model.device_id_example,
        display_capabilities=list(model.display_capabilities),
    )


@router.get("", response_model=list[DeviceModelRead])
def get_device_models(
    vendor: str | None = Query(default=None),
    _=Depends(verify_token),
):
    if vendor is not None:
        try:
            get_vendor(vendor)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    return [_to_read(model) for model in list_device_models(vendor)]
