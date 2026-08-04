from fastapi import APIRouter, Depends

from web.backend.routes.auth import verify_token
from web.backend.schemas import VendorRead
from web.backend.vendors import list_vendors

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get("", response_model=list[VendorRead])
def get_vendors(_=Depends(verify_token)):
    return [
        VendorRead(
            id=vendor.id,
            label=vendor.label,
            description=vendor.description,
            capabilities=list(vendor.capabilities),
            credential_hint=vendor.credential_hint,
            supports_credential_validation=vendor.supports_credential_validation,
            supports_device_discovery=vendor.supports_device_discovery,
        )
        for vendor in list_vendors()
    ]
