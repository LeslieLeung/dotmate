"""Background APScheduler that reads validated jobs from SQLite."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import ValidationError
from sqlmodel import Session, select

from dotmate.view.factory import ViewFactory
from web.backend.db import engine
from web.backend.models import ApiCredential, Device, Schedule, Settings
from web.backend.vendors import create_vendor_client

logger = logging.getLogger("dotmate.scheduler")

scheduler = BackgroundScheduler()


@dataclass(frozen=True)
class JobSpec:
    id: str
    name: str
    trigger: CronTrigger
    args: list[Any]


_active_job_specs: list[JobSpec] = []


def _build_job_specs() -> list[JobSpec]:
    """Build and validate the complete next scheduler state without mutating jobs."""
    specs: list[JobSpec] = []
    with Session(engine) as session:
        settings = session.get(Settings, 1)
        request_interval = settings.request_interval if settings else 1.0
        clients = {}

        devices = session.exec(select(Device)).all()
        for device in devices:
            credential = session.get(ApiCredential, device.api_credential_id)
            if not credential:
                logger.warning(
                    "Device '%s' has no API credential, skipping", device.name
                )
                continue
            if credential.id not in clients:
                try:
                    clients[credential.id] = create_vendor_client(
                        credential.vendor,
                        credential.api_key,
                        request_interval,
                    )
                except ValueError as exc:
                    logger.warning(
                        "Unsupported vendor '%s' for device '%s': %s",
                        credential.vendor,
                        device.name,
                        exc,
                    )
                    continue
            client = clients[credential.id]
            schedules = session.exec(
                select(Schedule).where(Schedule.device_id == device.id)
            ).all()
            for schedule in schedules:
                if not schedule.cron:
                    continue
                if schedule.type not in ViewFactory.get_available_types():
                    logger.warning(
                        "Unknown schedule type '%s' for device '%s', skipping",
                        schedule.type,
                        device.name,
                    )
                    continue

                try:
                    trigger = CronTrigger.from_crontab(schedule.cron)
                    raw_params = json.loads(schedule.params) if schedule.params else {}
                    params_class = ViewFactory.get_params_class(schedule.type)
                    params = params_class.model_validate(raw_params).model_dump(
                        mode="json", exclude_none=True
                    )
                except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                    logger.error(
                        "Invalid configuration for schedule id=%s on device '%s', skipping: %s",
                        schedule.id,
                        device.name,
                        exc,
                    )
                    continue

                overlay = {
                    "show_battery_icon": device.show_battery_icon,
                    "show_battery_percentage": device.show_battery_percentage,
                    "show_refresh_time": device.show_refresh_time,
                }
                specs.append(
                    JobSpec(
                        id=f"db_{schedule.id}",
                        name=f"{schedule.name} for {device.name}",
                        trigger=trigger,
                        args=[schedule.type, client, device.device_id, params, overlay],
                    )
                )
    return specs


def _install_job_specs(specs: list[JobSpec]) -> None:
    for spec in specs:
        scheduler.add_job(
            func=ViewFactory.execute_view,
            trigger=spec.trigger,
            args=spec.args,
            id=spec.id,
            name=spec.name,
            replace_existing=True,
        )


def _replace_jobs(specs: list[JobSpec]) -> None:
    """Atomically replace jobs, restoring the last known-good snapshot on failure."""
    global _active_job_specs

    previous_specs = _active_job_specs
    was_running = scheduler.running
    if was_running:
        scheduler.pause()
    try:
        scheduler.remove_all_jobs()
        _install_job_specs(specs)
    except Exception:
        logger.exception(
            "Failed to install scheduler snapshot; restoring previous jobs"
        )
        scheduler.remove_all_jobs()
        _install_job_specs(previous_specs)
        raise
    finally:
        if was_running:
            scheduler.resume()

    _active_job_specs = specs
    logger.info("Scheduler loaded %d job(s)", len(specs))


def start_scheduler() -> None:
    """Start the background scheduler with the current validated database state."""
    _replace_jobs(_build_job_specs())
    scheduler.start()
    logger.info("Background scheduler started")


def reload_scheduler() -> None:
    """Hot-reload jobs from a fully validated database snapshot."""
    _replace_jobs(_build_job_specs())
    logger.info("Scheduler reloaded")


def stop_scheduler() -> None:
    """Stop the web scheduler during a graceful process shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")
