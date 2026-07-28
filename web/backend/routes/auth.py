import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/api/auth", tags=["auth"])

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Validate the Bearer token against ADMIN_TOKEN.

    If ADMIN_TOKEN is not set the API is open (dev mode).
    """
    if not ADMIN_TOKEN:
        return  # no token configured → open access

    if credentials is None or credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


@router.get("/status")
def auth_status(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, bool]:
    """Return whether authentication is required and the supplied token is valid."""
    if not ADMIN_TOKEN:
        return {"auth_required": False, "authenticated": True}
    authenticated = bool(
        credentials is not None and credentials.credentials == ADMIN_TOKEN
    )
    return {"auth_required": True, "authenticated": authenticated}
