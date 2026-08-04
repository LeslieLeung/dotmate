"""Expose schedule type metadata for dynamic web forms."""

from fastapi import APIRouter, Depends

from web.backend.routes.auth import verify_token
from web.backend.schedule_types import get_schedule_type_schema

router = APIRouter(prefix="/api/schema", tags=["schema"])


@router.get("/schedule-types")
def get_schedule_types(_=Depends(verify_token)) -> dict:
    return get_schedule_type_schema()
