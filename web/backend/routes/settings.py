import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from web.backend.db import get_session
from web.backend.models import Settings
from web.backend.schemas import SettingsRead, SettingsUpdate
from web.backend.routes.auth import verify_token
from web.backend.scheduler import reload_scheduler

logger = logging.getLogger("dotmate.routes.settings")

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_create(session: Session) -> Settings:
    settings = session.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.get("", response_model=SettingsRead)
def get_settings(
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    settings = _get_or_create(session)
    return SettingsRead(request_interval=settings.request_interval)


@router.put("", response_model=SettingsRead)
def update_settings(
    body: SettingsUpdate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    settings = _get_or_create(session)
    previous = settings.request_interval
    if body.request_interval is not None:
        settings.request_interval = body.request_interval
    session.add(settings)
    session.commit()
    session.refresh(settings)
    try:
        reload_scheduler()
    except Exception:
        logger.exception("Scheduler reload failed after updating settings")
        settings.request_interval = previous
        session.add(settings)
        session.commit()
        raise HTTPException(500, "Scheduler reload failed; settings were not updated")
    return SettingsRead(request_interval=settings.request_interval)
