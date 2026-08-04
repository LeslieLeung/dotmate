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
from web.backend.device_models import assert_model_matches_vendor
from web.backend.models import ApiCredential, Device, Schedule, Settings
from web.backend.schedule_types import sanitize_params_for_model
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

            try:
                model = assert_model_matches_vendor(
                    device.device_model, credential.vendor
                )
            except ValueError as exc:
                logger.error(
                    "Configuration error for device '%s' (vendor=%s model=%s): %s",
                    device.name,
                    credential.vendor,
                    device.device_model,
                    exc,
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
            profile = model.to_profile()
            schedules = session.exec(
                select(Schedule).where(Schedule.device_id == device.id)
            ).all()
            for schedule in schedules:
                if not schedule.cron:
                    continue
                if schedule.type not in ViewFactory.get_available_types():
                    logger.warning(
                        "Unknown schedule type '%s' for device '%s' "
                        "(vendor=%s model=%s), skipping",
                        schedule.type,
                        device.name,
                        credential.vendor,
                        model.id,
                    )
                    continue

                if ViewFactory.requires_text(schedule.type) and not model.supports_text:
                    logger.error(
                        "Schedule id=%s type='%s' requires text but device '%s' "
                        "model '%s' does not support text; skipping",
                        schedule.id,
                        schedule.type,
                        device.name,
                        model.id,
                    )
                    continue

                try:
                    trigger = CronTrigger.from_crontab(schedule.cron)
                    raw_params = json.loads(schedule.params) if schedule.params else {}
                    params_class = ViewFactory.get_params_class(schedule.type)
                    params = params_class.model_validate(raw_params).model_dump(
                        mode="json", exclude_none=True
                    )
                    params = sanitize_params_for_model(schedule.type, params, model)
                except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                    logger.error(
                        "Invalid configuration for schedule id=%s on device '%s' "
                        "(vendor=%s model=%s), skipping: %s",
                        schedule.id,
                        device.name,
                        credential.vendor,
                        model.id,
                        exc,
                    )
                    continue

                overlay = {
                    "show_battery_icon": (
                        device.show_battery_icon and model.supports_battery_overlay
                    ),
                    "show_battery_percentage": (
                        device.show_battery_percentage
                        and model.supports_battery_overlay
                    ),
                    "show_refresh_time": device.show_refresh_time,
                }
                specs.append(
                    JobSpec(
                        id=f"db_{schedule.id}",
                        name=f"{schedule.name} for {device.name}",
                        trigger=trigger,
                        args=[
                            schedule.type,
                            client,
                            device.device_id,
                            params,
                            overlay,
                            profile,
                        ],
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


class ScheduleRunError(Exception):
    """Raised when a schedule cannot be executed immediately."""

    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def run_schedule_now(schedule_id: int) -> str:
    """Execute one schedule immediately using the same path as cron jobs."""
    with Session(engine) as session:
        schedule = session.get(Schedule, schedule_id)
        if not schedule:
            raise ScheduleRunError("Schedule not found", status_code=404)

        device = session.get(Device, schedule.device_id)
        if not device:
            raise ScheduleRunError("Device not found", status_code=404)

        credential = session.get(ApiCredential, device.api_credential_id)
        if not credential:
            raise ScheduleRunError(
                "Device has no API credential", status_code=409
            )

        try:
            model = assert_model_matches_vendor(
                device.device_model, credential.vendor
            )
        except ValueError as exc:
            raise ScheduleRunError(str(exc), status_code=422) from exc

        if schedule.type not in ViewFactory.get_available_types():
            raise ScheduleRunError(
                f"Unknown schedule type '{schedule.type}'", status_code=422
            )

        if ViewFactory.requires_text(schedule.type) and not model.supports_text:
            raise ScheduleRunError(
                f"Schedule type '{schedule.type}' requires text support",
                status_code=422,
            )

        settings = session.get(Settings, 1)
        request_interval = settings.request_interval if settings else 1.0
        try:
            client = create_vendor_client(
                credential.vendor, credential.api_key, request_interval
            )
        except ValueError as exc:
            raise ScheduleRunError(str(exc), status_code=422) from exc

        try:
            raw_params = json.loads(schedule.params) if schedule.params else {}
            params_class = ViewFactory.get_params_class(schedule.type)
            params = params_class.model_validate(raw_params).model_dump(
                mode="json", exclude_none=True
            )
            params = sanitize_params_for_model(schedule.type, params, model)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise ScheduleRunError(
                f"Invalid schedule configuration: {exc}", status_code=422
            ) from exc

        overlay = {
            "show_battery_icon": (
                device.show_battery_icon and model.supports_battery_overlay
            ),
            "show_battery_percentage": (
                device.show_battery_percentage and model.supports_battery_overlay
            ),
            "show_refresh_time": device.show_refresh_time,
        }
        profile = model.to_profile()
        device_name = device.name
        device_remote_id = device.device_id
        schedule_name = schedule.name
        schedule_type = schedule.type

    try:
        ViewFactory.execute_view(
            schedule_type,
            client,
            device_remote_id,
            params,
            overlay,
            profile,
        )
    except Exception as exc:
        logger.exception(
            "Failed to run schedule id=%s (%s) for device '%s'",
            schedule_id,
            schedule_name,
            device_name,
        )
        raise ScheduleRunError(
            f"Unable to push schedule: {exc}", status_code=502
        ) from exc

    logger.info(
        "Ran schedule id=%s (%s) for device '%s' immediately",
        schedule_id,
        schedule_name,
        device_name,
    )
    return f"Pushed '{schedule_name}' to {device_name}"
