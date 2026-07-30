"""Persisted device-status refresh worker for the web admin."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import ValidationError
from sqlmodel import Session, select

from dotmate.api.api import DeviceSettings, DeviceStatus
from web.backend import db
from web.backend.models import ApiCredential, Device, DeviceStatusRecord, Settings
from web.backend.vendors import create_vendor_client, get_vendor

logger = logging.getLogger("dotmate.status_worker")

FALLBACK_INTERVAL_MINUTES = 60
STALE_CLAIM_MINUTES = 2
RETRY_MINUTES = (1, 2, 4, 8, 15)

status_scheduler = BackgroundScheduler(
    executors={"default": ThreadPoolExecutor(1)},
    job_defaults={"coalesce": True, "max_instances": 1},
)
_client_cache: dict[tuple[int, str, str, float], object] = {}


def utc_now() -> datetime:
    """Return a timezone-independent value that round-trips through SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_status_record(
    session: Session, device_id: int, *, due_at: datetime | None = None
) -> DeviceStatusRecord:
    record = session.get(DeviceStatusRecord, device_id)
    if record is None:
        record = DeviceStatusRecord(
            device_id=device_id,
            next_refresh_at=due_at or utc_now(),
        )
        session.add(record)
        session.flush()
    return record


def ensure_all_status_records(session: Session) -> int:
    created = 0
    now = utc_now()
    for device in session.exec(select(Device)).all():
        credential = session.get(ApiCredential, device.api_credential_id)
        if credential is None:
            continue
        try:
            if not get_vendor(credential.vendor).supports_status:
                continue
        except ValueError:
            continue
        if session.get(DeviceStatusRecord, device.id) is None:
            session.add(
                DeviceStatusRecord(device_id=device.id, next_refresh_at=now)
            )
            created += 1
    if created:
        session.commit()
    return created


def normalized_status(status: DeviceStatus) -> dict:
    """Keep display-safe status data while omitting current image URLs."""
    images = status.renderInfo.current.image or []
    return {
        "remote_device_id": status.deviceId,
        "alias": status.alias,
        "location": status.location,
        "version": status.status.version,
        "current": status.status.current,
        "description": status.status.description,
        "battery": status.status.battery,
        "wifi": status.status.wifi,
        "last_render": status.renderInfo.last,
        "rotated": status.renderInfo.current.rotated,
        "border": status.renderInfo.current.border,
        "image_count": len(images),
        "next_battery_render": status.renderInfo.next.battery,
        "next_power_render": status.renderInfo.next.power,
    }


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        if status == 401:
            return "API credential is invalid or expired"
        if status == 403:
            return "API credential cannot access this device"
        if status == 404:
            return "Device was not found by the vendor"
        return f"Vendor request failed with status {status}"
    if isinstance(exc, requests.RequestException):
        return "Unable to connect to the vendor service"
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        return "Vendor returned an invalid response"
    logger.exception("Unexpected status refresh error", exc_info=exc)
    return "Unable to refresh device status"


def _uses_power(status: DeviceStatus) -> bool:
    battery = status.status.battery.casefold()
    current = status.status.current.casefold()
    return (
        "charging" in battery
        or current.startswith("power")
        or "connected to power" in current
    )


def _device_interval(
    status: DeviceStatus,
    settings: DeviceSettings,
) -> tuple[int | None, str]:
    interval = settings.interval
    if interval is None:
        return None, "fallback"
    if _uses_power(status):
        if interval.powerMs is not None:
            return interval.powerMs // 60_000, "power"
        if interval.batteryMs is not None:
            return interval.batteryMs // 60_000, "battery"
    else:
        if interval.batteryMs is not None:
            return interval.batteryMs // 60_000, "battery"
        if interval.powerMs is not None:
            return interval.powerMs // 60_000, "power"
    return None, "fallback"


def _client_for(
    credential: ApiCredential, request_interval: float
):
    key = (
        credential.id,
        credential.vendor,
        credential.api_key,
        request_interval,
    )
    client = _client_cache.get(key)
    if client is None:
        client = create_vendor_client(
            credential.vendor,
            credential.api_key,
            request_interval,
        )
        _client_cache[key] = client
    return client


def _claim_refresh(device_id: int, now: datetime) -> bool:
    with Session(db.engine) as session:
        record = ensure_status_record(session, device_id, due_at=now)
        if (
            record.refresh_started_at is not None
            and record.refresh_started_at > now - timedelta(minutes=STALE_CLAIM_MINUTES)
        ):
            return False
        record.refresh_started_at = now
        session.add(record)
        session.commit()
    return True


def refresh_device_status(device_id: int, *, now: datetime | None = None) -> bool:
    """Refresh one device and persist either a new snapshot or safe error state."""
    started_at = now or utc_now()
    if not _claim_refresh(device_id, started_at):
        return False

    with Session(db.engine) as session:
        device = session.get(Device, device_id)
        if device is None:
            record = session.get(DeviceStatusRecord, device_id)
            if record is not None:
                session.delete(record)
                session.commit()
            return False
        credential = session.get(ApiCredential, device.api_credential_id)
        global_settings = session.get(Settings, 1)
        request_interval = (
            global_settings.request_interval if global_settings else 1.0
        )
        record = ensure_status_record(session, device_id, due_at=started_at)
        custom_interval = record.refresh_interval_minutes
        previous_effective = record.effective_interval_minutes
        remote_device_id = device.device_id
        credential_id = device.api_credential_id

    finished_at = utc_now() if now is None else now
    try:
        if credential is None:
            raise ValueError("Device has no API credential")
        vendor = get_vendor(credential.vendor)
        if "status" not in vendor.capabilities:
            raise ValueError(f"Vendor '{credential.vendor}' does not support status")
        client = _client_for(credential, request_interval)
        status = client.get_device_status(remote_device_id)

        if custom_interval is not None:
            effective_interval = custom_interval
            interval_source = "custom"
        else:
            try:
                remote_settings = client.get_device_settings(remote_device_id)
                detected_interval, interval_source = _device_interval(
                    status, remote_settings
                )
            except Exception:
                logger.warning(
                    "Unable to read refresh settings for device id=%s; using cached interval",
                    device_id,
                    exc_info=True,
                )
                detected_interval, interval_source = None, "fallback"
            effective_interval = (
                detected_interval
                or previous_effective
                or FALLBACK_INTERVAL_MINUTES
            )

        with Session(db.engine) as session:
            current_device = session.get(Device, device_id)
            if current_device is None:
                record = session.get(DeviceStatusRecord, device_id)
                if record is not None:
                    session.delete(record)
                    session.commit()
                return False
            if (
                current_device.device_id != remote_device_id
                or current_device.api_credential_id != credential_id
            ):
                record = ensure_status_record(session, device_id, due_at=finished_at)
                record.refresh_started_at = None
                record.next_refresh_at = finished_at
                session.add(record)
                session.commit()
                return False
            record = ensure_status_record(session, device_id, due_at=finished_at)
            record.payload_json = json.dumps(
                normalized_status(status), ensure_ascii=False
            )
            record.effective_interval_minutes = effective_interval
            record.interval_source = interval_source
            record.last_attempt_at = finished_at
            record.last_success_at = finished_at
            record.next_refresh_at = finished_at + timedelta(
                minutes=effective_interval
            )
            record.last_error = None
            record.refresh_started_at = None
            record.consecutive_failures = 0
            session.add(record)
            session.commit()
        return True
    except Exception as exc:
        with Session(db.engine) as session:
            current_device = session.get(Device, device_id)
            if current_device is None:
                record = session.get(DeviceStatusRecord, device_id)
                if record is not None:
                    session.delete(record)
                    session.commit()
                return False
            if (
                current_device.device_id != remote_device_id
                or current_device.api_credential_id != credential_id
            ):
                record = ensure_status_record(session, device_id, due_at=finished_at)
                record.refresh_started_at = None
                record.next_refresh_at = finished_at
                session.add(record)
                session.commit()
                return False
            record = ensure_status_record(session, device_id, due_at=finished_at)
            record.consecutive_failures += 1
            normal_interval = (
                record.refresh_interval_minutes
                or record.effective_interval_minutes
                or FALLBACK_INTERVAL_MINUTES
            )
            retry_index = min(record.consecutive_failures - 1, len(RETRY_MINUTES) - 1)
            retry_minutes = min(normal_interval, RETRY_MINUTES[retry_index])
            record.last_attempt_at = finished_at
            record.next_refresh_at = finished_at + timedelta(minutes=retry_minutes)
            record.last_error = _safe_error(exc)
            record.refresh_started_at = None
            session.add(record)
            session.commit()
        return False


def _due_device_ids(now: datetime) -> list[int]:
    with Session(db.engine) as session:
        ensure_all_status_records(session)
        records = session.exec(select(DeviceStatusRecord)).all()
        due = []
        for record in records:
            device = session.get(Device, record.device_id)
            if device is None:
                continue
            credential = session.get(ApiCredential, device.api_credential_id)
            if credential is None:
                continue
            try:
                if not get_vendor(credential.vendor).supports_status:
                    continue
            except ValueError:
                continue
            requested = (
                record.refresh_requested_at is not None
                and (
                    record.last_attempt_at is None
                    or record.refresh_requested_at > record.last_attempt_at
                )
            )
            scheduled = (
                record.next_refresh_at is None or record.next_refresh_at <= now
            )
            if requested or scheduled:
                due.append(record.device_id)
        return sorted(due)


def refresh_due_devices() -> int:
    now = utc_now()
    refreshed = 0
    for device_id in _due_device_ids(now):
        if refresh_device_status(device_id):
            refreshed += 1
    return refreshed


def request_status_refresh(device_ids: Iterable[int]) -> tuple[datetime, int]:
    """Mark devices due and wake the single worker queue without doing I/O inline."""
    requested_at = utc_now()
    count = 0
    with Session(db.engine) as session:
        for device_id in dict.fromkeys(device_ids):
            if session.get(Device, device_id) is None:
                continue
            record = ensure_status_record(session, device_id, due_at=requested_at)
            record.refresh_requested_at = requested_at
            record.next_refresh_at = requested_at
            session.add(record)
            count += 1
        session.commit()

    if count and status_scheduler.running:
        status_scheduler.add_job(
            refresh_due_devices,
            trigger="date",
            run_date=datetime.now(),
            id="device_status_requested",
            replace_existing=True,
        )
    return requested_at, count


def start_status_worker() -> None:
    if status_scheduler.running:
        return
    with Session(db.engine) as session:
        ensure_all_status_records(session)
        for record in session.exec(select(DeviceStatusRecord)).all():
            record.refresh_started_at = None
            session.add(record)
        session.commit()
    status_scheduler.add_job(
        refresh_due_devices,
        trigger="interval",
        seconds=30,
        next_run_time=datetime.now(),
        id="device_status_sweep",
        replace_existing=True,
    )
    status_scheduler.start()
    logger.info("Device status worker started")


def stop_status_worker() -> None:
    if status_scheduler.running:
        status_scheduler.shutdown(wait=True)
        logger.info("Device status worker stopped")
