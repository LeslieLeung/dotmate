import json
import logging
import re
from datetime import datetime, timezone
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlmodel import Session, select

from dotmate.api.api import DeviceIntervalSettings, DeviceSettingsUpdate
from web.backend.device_models import (
    assert_model_matches_vendor,
    get_device_model,
)
from web.backend.db import get_session
from web.backend.models import (
    ApiCredential,
    Device,
    DeviceStatusRecord,
    Schedule,
    Settings,
)
from web.backend.schemas import (
    DeviceCreate,
    DeviceRead,
    DeviceStatusPolicyRead,
    DeviceStatusPolicyUpdate,
    DeviceStatusRefreshResponse,
    DeviceUpdate,
    RemoteActionResponse,
    RemoteContentRead,
    RemoteDeviceStatusRead,
    RemoteDeviceSettingsRead,
    RemoteDeviceSettingsUpdate,
    RemoteTimezoneRead,
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
)
from web.backend.routes.auth import verify_token
from web.backend.scheduler import ScheduleRunError, reload_scheduler, run_schedule_now
from web.backend.schedule_conflicts import (
    find_cron_conflicts,
    format_conflict_message,
)
from web.backend.schedule_types import (
    build_summary,
    get_schedule_type_schema,
    get_type_label,
    is_web_editable,
    validate_params_for_device,
    validation_errors,
)
from web.backend.vendors import create_vendor_client, get_vendor
from web.backend.status_worker import (
    ensure_status_record,
    request_status_refresh,
    utc_now,
)

logger = logging.getLogger("dotmate.routes.devices")
router = APIRouter(prefix="/api/devices", tags=["devices"])


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _schedule_to_read(
    s: Schedule, device_model: str | None = None
) -> ScheduleRead:
    try:
        params = json.loads(s.params) if s.params else None
    except json.JSONDecodeError:
        logger.exception("Invalid params JSON for schedule id=%s", s.id)
        params = None
    return ScheduleRead(
        id=s.id,
        name=s.name,
        cron=s.cron,
        type=s.type,
        type_label=get_type_label(s.type),
        params=params,
        summary=build_summary(s.type, params, device_model),
    )


def _validate_schedule_params(
    type_name: str, params: dict | None, device_model: str
) -> dict:
    if not is_web_editable(type_name):
        raise HTTPException(
            422,
            detail={
                "message": "This schedule type is not editable in the web admin",
                "fields": {"type": "Choose a supported schedule type"},
            },
        )
    try:
        return validate_params_for_device(type_name, params, device_model)
    except ValidationError as exc:
        raise HTTPException(
            422,
            detail={
                "message": "Check the highlighted schedule parameters",
                "fields": validation_errors(exc),
            },
        )
    except ValueError as exc:
        fields = getattr(exc, "fields", None)
        if fields:
            raise HTTPException(
                422,
                detail={
                    "message": "Check the highlighted schedule parameters",
                    "fields": fields,
                },
            ) from exc
        raise HTTPException(
            422,
            detail={
                "message": "Unknown schedule type",
                "fields": {"type": "Choose a supported schedule type"},
            },
        ) from exc
    except KeyError:
        raise HTTPException(
            422,
            detail={
                "message": "Unknown schedule type",
                "fields": {"type": "Choose a supported schedule type"},
            },
        )


def _normalize_overlays(
    model,
    *,
    show_battery_icon: bool,
    show_battery_percentage: bool,
    show_refresh_time: bool,
) -> tuple[bool, bool, bool]:
    if not model.supports_battery_overlay:
        return False, False, show_refresh_time
    return show_battery_icon, show_battery_percentage, show_refresh_time


def _device_to_read(
    session: Session, d: Device, schedules: list[Schedule]
) -> DeviceRead:
    credential = session.get(ApiCredential, d.api_credential_id)
    status_record = session.get(DeviceStatusRecord, d.id)
    remote_status, status_policy = _status_to_read(status_record)
    vendor = get_vendor(credential.vendor)
    try:
        model = get_device_model(d.device_model)
    except ValueError as exc:
        raise HTTPException(
            422, f"Device has an unsupported device model: {d.device_model}"
        ) from exc
    return DeviceRead(
        id=d.id,
        name=d.name,
        device_id=d.device_id,
        api_credential_id=d.api_credential_id,
        api_credential_name=credential.name,
        vendor=credential.vendor,
        vendor_label=vendor.label,
        vendor_capabilities=list(vendor.capabilities),
        device_model=model.id,
        device_model_label=model.label,
        display_width=model.width,
        display_height=model.height,
        display_capabilities=list(model.display_capabilities),
        show_battery_icon=d.show_battery_icon,
        show_battery_percentage=d.show_battery_percentage,
        show_refresh_time=d.show_refresh_time,
        remote_status=remote_status,
        status_policy=status_policy,
        schedules=[_schedule_to_read(s, model.id) for s in schedules],
    )


def _status_to_read(
    record: DeviceStatusRecord | None,
) -> tuple[RemoteDeviceStatusRead | None, DeviceStatusPolicyRead]:
    remote_status = None
    if record and record.payload_json:
        try:
            remote_status = RemoteDeviceStatusRead.model_validate_json(
                record.payload_json
            )
        except (ValidationError, ValueError):
            logger.exception(
                "Invalid cached status JSON for device id=%s", record.device_id
            )

    if record is None:
        return remote_status, DeviceStatusPolicyRead(state="pending")
    if record.refresh_started_at is not None:
        state = "refreshing"
    elif (
        record.refresh_requested_at is not None
        and (
            record.last_attempt_at is None
            or record.refresh_requested_at > record.last_attempt_at
        )
    ):
        state = "pending"
    elif record.last_error:
        state = "stale" if remote_status else "error"
    elif remote_status:
        state = "ready"
    else:
        state = "pending"
    return remote_status, DeviceStatusPolicyRead(
        refresh_interval_minutes=record.refresh_interval_minutes,
        effective_interval_minutes=record.effective_interval_minutes,
        interval_source=record.interval_source,
        state=state,
        last_attempt_at=_as_utc(record.last_attempt_at),
        last_success_at=_as_utc(record.last_success_at),
        next_refresh_at=_as_utc(record.next_refresh_at),
        last_error=record.last_error,
        refresh_requested_at=_as_utc(record.refresh_requested_at),
    )


# ── Device CRUD ───────────────────────────────────────────


@router.get("", response_model=list[DeviceRead])
def list_devices(
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    devices = session.exec(select(Device)).all()
    result = []
    for d in devices:
        schedules = session.exec(
            select(Schedule).where(Schedule.device_id == d.id)
        ).all()
        result.append(_device_to_read(session, d, schedules))
    return result


@router.post(
    "/remote/statuses/refresh",
    response_model=DeviceStatusRefreshResponse,
    status_code=202,
)
def refresh_all_device_statuses(
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device_ids = []
    for device in session.exec(select(Device)).all():
        credential = session.get(ApiCredential, device.api_credential_id)
        if not credential:
            continue
        try:
            if "status" in get_vendor(credential.vendor).capabilities:
                device_ids.append(device.id)
        except ValueError:
            continue
    requested_at, queued = request_status_refresh(device_ids)
    return DeviceStatusRefreshResponse(
        requested_at=_as_utc(requested_at),
        queued=queued,
    )


@router.post("", response_model=DeviceRead, status_code=201)
def create_device(
    body: DeviceCreate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    credential = session.get(ApiCredential, body.api_credential_id)
    if not credential:
        raise HTTPException(422, "Choose a valid API credential")
    try:
        model = assert_model_matches_vendor(body.device_model, credential.vendor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    duplicate = session.exec(
        select(Device)
        .join(ApiCredential)
        .where(
            ApiCredential.vendor == credential.vendor,
            Device.device_id == body.device_id,
        )
    ).first()
    if duplicate:
        raise HTTPException(409, "This device already exists for the selected vendor")
    battery_icon, battery_percent, refresh_time = _normalize_overlays(
        model,
        show_battery_icon=body.show_battery_icon,
        show_battery_percentage=body.show_battery_percentage,
        show_refresh_time=body.show_refresh_time,
    )
    device = Device(
        name=body.name,
        device_id=body.device_id,
        api_credential_id=body.api_credential_id,
        device_model=model.id,
        show_battery_icon=battery_icon,
        show_battery_percentage=battery_percent,
        show_refresh_time=refresh_time,
    )
    session.add(device)
    session.flush()
    if "status" in get_vendor(credential.vendor).capabilities:
        session.add(
            DeviceStatusRecord(device_id=device.id, next_refresh_at=utc_now())
        )
    session.commit()
    session.refresh(device)
    if "status" in get_vendor(credential.vendor).capabilities:
        request_status_refresh([device.id])
    return _device_to_read(session, device, [])


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    schedules = session.exec(
        select(Schedule).where(Schedule.device_id == device.id)
    ).all()
    return _device_to_read(session, device, schedules)


@router.put("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: int,
    body: DeviceUpdate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    current_credential = session.get(ApiCredential, device.api_credential_id)
    next_credential_id = (
        body.api_credential_id
        if body.api_credential_id is not None
        else device.api_credential_id
    )
    next_credential = session.get(ApiCredential, next_credential_id)
    if not next_credential:
        raise HTTPException(422, "Choose a valid API credential")
    if next_credential.vendor != current_credential.vendor:
        raise HTTPException(
            422, "A device can only be reassigned within the same vendor"
        )
    try:
        model = assert_model_matches_vendor(device.device_model, next_credential.vendor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    next_device_id = body.device_id or device.device_id
    duplicate = session.exec(
        select(Device)
        .join(ApiCredential)
        .where(
            ApiCredential.vendor == next_credential.vendor,
            Device.device_id == next_device_id,
            Device.id != device.id,
        )
    ).first()
    if duplicate:
        raise HTTPException(409, "This device already exists for the selected vendor")
    previous = {
        "name": device.name,
        "device_id": device.device_id,
        "api_credential_id": device.api_credential_id,
        "device_model": device.device_model,
        "show_battery_icon": device.show_battery_icon,
        "show_battery_percentage": device.show_battery_percentage,
        "show_refresh_time": device.show_refresh_time,
    }
    identity_changed = (
        next_device_id != device.device_id
        or next_credential_id != device.api_credential_id
    )
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(device, k, v)
    battery_icon, battery_percent, refresh_time = _normalize_overlays(
        model,
        show_battery_icon=device.show_battery_icon,
        show_battery_percentage=device.show_battery_percentage,
        show_refresh_time=device.show_refresh_time,
    )
    device.show_battery_icon = battery_icon
    device.show_battery_percentage = battery_percent
    device.show_refresh_time = refresh_time
    session.add(device)
    session.commit()
    session.refresh(device)
    try:
        reload_scheduler()
    except Exception:
        logger.exception(
            "Scheduler reload failed after updating device id=%s", device_id
        )
        for key, value in previous.items():
            setattr(device, key, value)
        session.add(device)
        session.commit()
        raise HTTPException(500, "Scheduler reload failed; device was not updated")
    schedules = session.exec(
        select(Schedule).where(Schedule.device_id == device.id)
    ).all()
    if identity_changed:
        record = ensure_status_record(session, device.id)
        record.payload_json = None
        record.effective_interval_minutes = None
        record.interval_source = None
        record.last_attempt_at = None
        record.last_success_at = None
        record.last_error = None
        record.refresh_started_at = None
        record.consecutive_failures = 0
        record.next_refresh_at = utc_now()
        session.add(record)
        session.commit()
        if "status" in get_vendor(next_credential.vendor).capabilities:
            request_status_refresh([device.id])
    return _device_to_read(session, device, schedules)


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    schedules = session.exec(
        select(Schedule).where(Schedule.device_id == device.id)
    ).all()
    device_snapshot = Device(
        id=device.id,
        name=device.name,
        device_id=device.device_id,
        api_credential_id=device.api_credential_id,
        device_model=device.device_model,
        show_battery_icon=device.show_battery_icon,
        show_battery_percentage=device.show_battery_percentage,
        show_refresh_time=device.show_refresh_time,
    )
    schedule_snapshots = [
        Schedule(
            id=s.id,
            device_id=s.device_id,
            name=s.name,
            cron=s.cron,
            type=s.type,
            params=s.params,
        )
        for s in schedules
    ]
    status_record = session.get(DeviceStatusRecord, device.id)
    status_snapshot = (
        DeviceStatusRecord(**status_record.model_dump())
        if status_record is not None
        else None
    )
    for s in schedules:
        session.delete(s)
    if status_record is not None:
        session.delete(status_record)
    session.delete(device)
    session.commit()
    try:
        reload_scheduler()
    except Exception:
        logger.exception(
            "Scheduler reload failed after deleting device id=%s", device_id
        )
        session.add(device_snapshot)
        if status_snapshot is not None:
            session.add(status_snapshot)
        for schedule_snapshot in schedule_snapshots:
            session.add(schedule_snapshot)
        session.commit()
        raise HTTPException(500, "Scheduler reload failed; device was not deleted")


# ── Remote device controls ───────────────────────────────


def _status_capable_device(session: Session, device_id: int) -> Device:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    credential = session.get(ApiCredential, device.api_credential_id)
    if not credential:
        raise HTTPException(409, "Device has no API credential")
    try:
        if "status" not in get_vendor(credential.vendor).capabilities:
            raise HTTPException(
                422, f"Vendor '{credential.vendor}' does not support status"
            )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return device


@router.post(
    "/{device_id}/remote/status/refresh",
    response_model=DeviceStatusRefreshResponse,
    status_code=202,
)
def refresh_device_status(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = _status_capable_device(session, device_id)
    requested_at, queued = request_status_refresh([device.id])
    return DeviceStatusRefreshResponse(
        requested_at=_as_utc(requested_at),
        queued=queued,
    )


@router.patch(
    "/{device_id}/remote/status/policy",
    response_model=DeviceStatusPolicyRead,
)
def update_device_status_policy(
    device_id: int,
    body: DeviceStatusPolicyUpdate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = _status_capable_device(session, device_id)
    record = ensure_status_record(session, device.id)
    record.refresh_interval_minutes = body.refresh_interval_minutes
    record.next_refresh_at = utc_now()
    session.add(record)
    session.commit()
    request_status_refresh([device.id])
    session.refresh(record)
    return _status_to_read(record)[1]


def _remote_client(session: Session, device_id: int, capability: str):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    credential = session.get(ApiCredential, device.api_credential_id)
    if not credential:
        raise HTTPException(409, "Device has no API credential")
    settings = session.get(Settings, 1)
    interval = settings.request_interval if settings else 1.0
    try:
        vendor = get_vendor(credential.vendor)
        if capability not in vendor.capabilities:
            raise HTTPException(
                422, f"Vendor '{credential.vendor}' does not support {capability}"
            )
        client = create_vendor_client(credential.vendor, credential.api_key, interval)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return device, client


def _raise_remote_error(exc: Exception):
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        if status == 400:
            raise HTTPException(422, "Vendor rejected the request") from exc
        if status == 403:
            raise HTTPException(
                403, "API credential cannot access this device"
            ) from exc
        if status == 404:
            raise HTTPException(404, "Device not found by vendor") from exc
        if status == 401:
            raise HTTPException(502, "API credential is invalid or expired") from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(502, "Vendor returned an invalid response") from exc
    raise HTTPException(502, "Unable to complete vendor request") from exc


def _settings_to_read(settings) -> RemoteDeviceSettingsRead:
    return RemoteDeviceSettingsRead(
        alias=settings.alias,
        location=settings.location,
        timezone=settings.timezone,
        power_interval_minutes=(
            settings.interval.powerMs // 60_000
            if settings.interval and settings.interval.powerMs is not None
            else None
        ),
        battery_interval_minutes=(
            settings.interval.batteryMs // 60_000
            if settings.interval and settings.interval.batteryMs is not None
            else None
        ),
        sleep=settings.sleep.model_dump() if settings.sleep else None,
    )


@router.get("/{device_id}/remote/settings", response_model=RemoteDeviceSettingsRead)
def get_remote_settings(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device, client = _remote_client(session, device_id, "settings")
    try:
        return _settings_to_read(client.get_device_settings(device.device_id))
    except Exception as exc:
        _raise_remote_error(exc)


@router.patch("/{device_id}/remote/settings", response_model=RemoteDeviceSettingsRead)
def update_remote_settings(
    device_id: int,
    body: RemoteDeviceSettingsUpdate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device, client = _remote_client(session, device_id, "settings")
    fields = body.model_fields_set
    interval = None
    if {"power_interval_minutes", "battery_interval_minutes"} & fields:
        interval_values = {}
        if body.power_interval_minutes is not None:
            interval_values["powerMs"] = body.power_interval_minutes * 60_000
        if body.battery_interval_minutes is not None:
            interval_values["batteryMs"] = body.battery_interval_minutes * 60_000
        if interval_values:
            interval = DeviceIntervalSettings(**interval_values)
    payload_data = {}
    for field in ("alias", "location", "timezone"):
        if field in fields:
            payload_data[field] = getattr(body, field)
    if interval is not None:
        payload_data["interval"] = interval
    if "sleep" in fields and body.sleep is not None:
        payload_data["sleep"] = body.sleep.model_dump()
    try:
        updated = client.update_device_settings(
            device.device_id, DeviceSettingsUpdate(**payload_data)
        )
        request_status_refresh([device.id])
        return _settings_to_read(updated)
    except Exception as exc:
        _raise_remote_error(exc)


@router.get("/{device_id}/remote/timezones", response_model=list[RemoteTimezoneRead])
def list_remote_timezones(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    _, client = _remote_client(session, device_id, "timezones")
    try:
        return [
            RemoteTimezoneRead(
                key=item.key,
                name=item.name,
                utc_offset_minutes=item.utcOffsetMinutes,
                utc_offset_label=item.utcOffsetLabel,
            )
            for item in client.list_timezones()
        ]
    except Exception as exc:
        _raise_remote_error(exc)


@router.post("/{device_id}/remote/next", response_model=RemoteActionResponse)
def switch_remote_content(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device, client = _remote_client(session, device_id, "next")
    try:
        return RemoteActionResponse(
            message=client.switch_next_content(device.device_id).message
        )
    except Exception as exc:
        _raise_remote_error(exc)


@router.get("/{device_id}/remote/content", response_model=list[RemoteContentRead])
def list_remote_content(
    device_id: int,
    task_type: str = "loop",
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_type):
        raise HTTPException(422, "Invalid task type")
    device, client = _remote_client(session, device_id, "content")
    try:
        tasks = client.list_device_content(device.device_id, task_type)
        return [
            RemoteContentRead(
                type=task.type,
                key=task.key,
                task_alias=task.taskAlias,
                refresh_now=task.refreshNow,
                title=task.title,
                message=task.message,
                signature=task.signature,
                link=task.link,
                border=task.border,
                dither_type=task.ditherType,
                dither_kernel=task.ditherKernel,
                has_icon=bool(task.icon),
                has_image=bool(task.image),
            )
            for task in tasks
        ]
    except Exception as exc:
        _raise_remote_error(exc)


# ── Schedule CRUD (nested under device) ───────────────────


def _raise_if_schedule_conflicts(
    session: Session,
    device_id: int,
    cron: str,
    *,
    exclude_id: int | None = None,
) -> None:
    existing = session.exec(
        select(Schedule).where(Schedule.device_id == device_id)
    ).all()
    conflicts = find_cron_conflicts(
        cron,
        [(s.id, s.name, s.cron or "") for s in existing if s.id is not None],
        exclude_id=exclude_id,
    )
    if not conflicts:
        return
    message = format_conflict_message(conflicts)
    raise HTTPException(
        409,
        detail={
            "message": message,
            "fields": {"cron": message},
            "conflicts": [c.to_dict() for c in conflicts],
        },
    )


@router.get("/{device_id}/schedule-types")
def get_device_schedule_types(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
) -> dict:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    return get_schedule_type_schema(device.device_model)


@router.get("/{device_id}/schedules", response_model=list[ScheduleRead])
def list_schedules(
    device_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    schedules = session.exec(
        select(Schedule).where(Schedule.device_id == device_id)
    ).all()
    return [_schedule_to_read(s, device.device_model) for s in schedules]


@router.post("/{device_id}/schedules", response_model=ScheduleRead, status_code=201)
def create_schedule(
    device_id: int,
    body: ScheduleCreate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    params = _validate_schedule_params(body.type, body.params, device.device_model)
    _raise_if_schedule_conflicts(session, device_id, body.cron)
    params_json = json.dumps(params) if params else None
    schedule = Schedule(
        device_id=device_id,
        name=body.name,
        cron=body.cron,
        type=body.type,
        params=params_json,
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    try:
        reload_scheduler()
    except Exception:
        logger.exception(
            "Scheduler reload failed after creating schedule id=%s; rolling back",
            schedule.id,
        )
        session.delete(schedule)
        session.commit()
        raise HTTPException(500, "Scheduler reload failed; schedule not saved")
    return _schedule_to_read(schedule, device.device_model)


@router.put("/schedules/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    device = session.get(Device, schedule.device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    previous = (schedule.name, schedule.cron, schedule.type, schedule.params)
    fields_set = body.model_fields_set
    effective_type = body.type if "type" in fields_set else schedule.type
    try:
        current_params = json.loads(schedule.params) if schedule.params else {}
    except json.JSONDecodeError:
        if (
            is_web_editable(effective_type)
            or "params" in fields_set
            or "type" in fields_set
        ):
            raise HTTPException(
                422,
                detail={
                    "message": "The existing schedule parameters are invalid",
                    "fields": {"params": "Replace the invalid stored parameters"},
                },
            )
        current_params = {}
    effective_params = body.params if "params" in fields_set else current_params

    if is_web_editable(effective_type):
        normalized_params = _validate_schedule_params(
            effective_type, effective_params, device.device_model
        )
    else:
        if "type" in fields_set or "params" in fields_set:
            _validate_schedule_params(
                effective_type, effective_params, device.device_model
            )
        normalized_params = current_params

    if "cron" in fields_set and body.cron and body.cron != schedule.cron:
        _raise_if_schedule_conflicts(
            session,
            schedule.device_id,
            body.cron,
            exclude_id=schedule.id,
        )

    if "name" in fields_set:
        schedule.name = body.name
    if "cron" in fields_set:
        schedule.cron = body.cron
    schedule.type = effective_type
    if is_web_editable(effective_type):
        schedule.params = json.dumps(normalized_params) if normalized_params else None
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    try:
        reload_scheduler()
    except Exception:
        logger.exception(
            "Scheduler reload failed after updating schedule id=%s; rolling back",
            schedule.id,
        )
        schedule.name, schedule.cron, schedule.type, schedule.params = previous
        session.add(schedule)
        session.commit()
        raise HTTPException(500, "Scheduler reload failed; schedule not updated")
    return _schedule_to_read(schedule, device.device_model)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    snapshot = Schedule(
        id=schedule.id,
        device_id=schedule.device_id,
        name=schedule.name,
        cron=schedule.cron,
        type=schedule.type,
        params=schedule.params,
    )
    session.delete(schedule)
    session.commit()
    try:
        reload_scheduler()
    except Exception:
        logger.exception(
            "Scheduler reload failed after deleting schedule id=%s", schedule_id
        )
        session.add(snapshot)
        session.commit()
        raise HTTPException(500, "Scheduler reload failed; schedule was not deleted")


@router.post(
    "/schedules/{schedule_id}/run",
    response_model=RemoteActionResponse,
)
def run_schedule(
    schedule_id: int,
    _=Depends(verify_token),
):
    """Push the schedule to the device immediately, outside the cron schedule."""
    try:
        return RemoteActionResponse(message=run_schedule_now(schedule_id))
    except ScheduleRunError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
