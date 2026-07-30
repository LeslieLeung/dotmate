"""API credential management and remote device discovery."""

from __future__ import annotations

import logging
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from web.backend.db import get_session
from web.backend.device_models import default_model_for_vendor
from web.backend.models import ApiCredential, Device, DeviceStatusRecord, Settings
from web.backend.status_worker import utc_now
from web.backend.routes.auth import verify_token
from web.backend.schemas import (
    ApiCredentialBatchCreate,
    ApiCredentialBatchResponse,
    ApiCredentialBatchResult,
    ApiCredentialRead,
    ApiCredentialSyncAllResult,
    ApiCredentialSyncResult,
    ApiCredentialUpdate,
    DeviceSyncStats,
)
from web.backend.vendors import create_vendor_client, get_vendor

logger = logging.getLogger("dotmate.routes.api_keys")
router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])

ValidationStatus = Literal["validated", "unverified", "invalid"]


def _mask_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:4]}{'•' * 8}{api_key[-4:]}"


def _device_count(session: Session, credential_id: int) -> int:
    return int(
        session.exec(
            select(func.count(Device.id)).where(
                Device.api_credential_id == credential_id
            )
        ).one()
    )


def credential_to_read(
    session: Session,
    credential: ApiCredential,
    *,
    validation_status: ValidationStatus = "unverified",
) -> ApiCredentialRead:
    try:
        vendor_label = get_vendor(credential.vendor).label
    except ValueError:
        vendor_label = credential.vendor
    return ApiCredentialRead(
        id=credential.id,
        name=credential.name,
        vendor=credential.vendor,
        vendor_label=vendor_label,
        masked_key=_mask_key(credential.api_key),
        device_count=_device_count(session, credential.id),
        validation_status=validation_status,
    )


def _request_interval(session: Session) -> float:
    settings = session.get(Settings, 1)
    return settings.request_interval if settings else 1.0


def _upstream_message(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        if status == 401:
            return "API key is invalid or expired"
        if status == 403:
            return "This API key cannot access the requested devices"
        return f"Vendor request failed with status {status}"
    if isinstance(exc, requests.RequestException):
        return "Unable to connect to the vendor service"
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        return "Vendor returned an invalid response"
    logger.exception("Unexpected vendor error", exc_info=exc)
    return "Vendor request failed"


def _sync_devices(
    session: Session, credential: ApiCredential, remote_devices
) -> DeviceSyncStats:
    seen: set[str] = set()
    stats = DeviceSyncStats()
    default_model = default_model_for_vendor(credential.vendor)
    for remote in remote_devices:
        remote_id = remote.id.strip()
        if not remote_id or remote_id in seen:
            stats.duplicates += 1
            continue
        seen.add(remote_id)
        stats.fetched += 1

        existing = session.exec(
            select(Device)
            .join(ApiCredential)
            .where(
                ApiCredential.vendor == credential.vendor,
                Device.device_id == remote_id,
            )
            .order_by(Device.id)
        ).first()
        if existing:
            stats.duplicates += 1
            continue

        name = (remote.alias or "").strip() or remote_id
        device = Device(
            name=name,
            device_id=remote_id,
            api_credential_id=credential.id,
            device_model=default_model.id,
        )
        session.add(device)
        session.flush()
        if get_vendor(credential.vendor).supports_status:
            session.add(
                DeviceStatusRecord(device_id=device.id, next_refresh_at=utc_now())
            )
        stats.created += 1
    return stats


@router.get("", response_model=list[ApiCredentialRead])
def list_api_keys(
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    credentials = session.exec(
        select(ApiCredential).order_by(ApiCredential.vendor, ApiCredential.name)
    ).all()
    return [credential_to_read(session, item) for item in credentials]


@router.post("/batch", response_model=ApiCredentialBatchResponse)
def create_api_keys_batch(
    body: ApiCredentialBatchCreate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    results: list[ApiCredentialBatchResult] = []
    candidates = []
    names_seen: set[tuple[str, str]] = set()
    keys_seen: set[tuple[str, str]] = set()
    interval = _request_interval(session)

    for index, item in enumerate(body.items):
        identity = (item.vendor, item.name)
        secret_identity = (item.vendor, item.api_key)
        error = None
        vendor = None
        try:
            vendor = get_vendor(item.vendor)
        except ValueError:
            error = f"Unsupported vendor: {item.vendor}"
        if not error and identity in names_seen:
            error = "Credential name is duplicated in this batch"
        if not error and secret_identity in keys_seen:
            error = "API key is duplicated in this batch"
        if not error:
            duplicate = session.exec(
                select(ApiCredential).where(
                    ApiCredential.vendor == item.vendor,
                    (ApiCredential.name == item.name)
                    | (ApiCredential.api_key == item.api_key),
                )
            ).first()
            if duplicate:
                error = "A credential with this name or API key already exists"

        names_seen.add(identity)
        keys_seen.add(secret_identity)
        if error:
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=item.name,
                    vendor=item.vendor,
                    status="error",
                    validation_status="invalid",
                    error=error,
                )
            )
            continue

        remote_devices = None
        validation_status: ValidationStatus = "unverified"
        if vendor.supports_credential_validation or vendor.supports_device_discovery:
            try:
                client = create_vendor_client(item.vendor, item.api_key, interval)
                if vendor.supports_device_discovery:
                    remote_devices = client.list_devices()
                    validation_status = "validated"
                elif vendor.supports_credential_validation:
                    # Reserved for vendors with a safe read-only check that is
                    # not device discovery. MindReset validates via list_devices.
                    validation_status = "validated"
            except Exception as exc:
                results.append(
                    ApiCredentialBatchResult(
                        index=index,
                        name=item.name,
                        vendor=item.vendor,
                        status="error",
                        validation_status="invalid",
                        error=_upstream_message(exc),
                    )
                )
                continue
        candidates.append((index, item, remote_devices, validation_status))

    for index, item, remote_devices, validation_status in candidates:
        credential = ApiCredential(
            name=item.name,
            vendor=item.vendor,
            api_key=item.api_key,
        )
        session.add(credential)
        session.flush()
        stats = None
        if remote_devices is not None:
            stats = _sync_devices(session, credential, remote_devices)
        session.flush()
        results.append(
            ApiCredentialBatchResult(
                index=index,
                name=item.name,
                vendor=item.vendor,
                status="success",
                credential=credential_to_read(
                    session, credential, validation_status=validation_status
                ),
                sync=stats,
                validation_status=validation_status,
            )
        )

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            409, "Credential data conflicts with an existing record"
        ) from exc
    results.sort(key=lambda result: result.index)
    return ApiCredentialBatchResponse(results=results)


def _sync_one(session: Session, credential: ApiCredential) -> ApiCredentialSyncResult:
    vendor = get_vendor(credential.vendor)
    if not vendor.supports_device_discovery:
        raise HTTPException(
            422,
            f"Vendor '{credential.vendor}' does not support device discovery",
        )
    try:
        client = create_vendor_client(
            credential.vendor, credential.api_key, _request_interval(session)
        )
        remote_devices = client.list_devices()
        stats = _sync_devices(session, credential, remote_devices)
        session.commit()
        session.refresh(credential)
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(502, _upstream_message(exc)) from exc
    return ApiCredentialSyncResult(
        credential=credential_to_read(
            session, credential, validation_status="validated"
        ),
        sync=stats,
    )


@router.post("/sync-all", response_model=ApiCredentialSyncAllResult)
def sync_all_api_keys(
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    results = []
    credentials = session.exec(select(ApiCredential).order_by(ApiCredential.id)).all()
    for index, credential in enumerate(credentials):
        try:
            vendor = get_vendor(credential.vendor)
        except ValueError:
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=credential.name,
                    vendor=credential.vendor,
                    status="error",
                    error=f"Unsupported vendor: {credential.vendor}",
                )
            )
            continue
        if not vendor.supports_device_discovery:
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=credential.name,
                    vendor=credential.vendor,
                    status="success",
                    credential=credential_to_read(session, credential),
                    sync=DeviceSyncStats(),
                    validation_status="unverified",
                    error=None,
                )
            )
            # Annotate skipped discovery for clients via empty sync stats.
            continue
        try:
            synced = _sync_one(session, credential)
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=credential.name,
                    vendor=credential.vendor,
                    status="success",
                    credential=synced.credential,
                    sync=synced.sync,
                    validation_status="validated",
                )
            )
        except HTTPException as exc:
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=credential.name,
                    vendor=credential.vendor,
                    status="error",
                    error=str(exc.detail),
                )
            )
    return ApiCredentialSyncAllResult(results=results)


@router.post("/{credential_id}/sync", response_model=ApiCredentialSyncResult)
def sync_api_key(
    credential_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    credential = session.get(ApiCredential, credential_id)
    if not credential:
        raise HTTPException(404, "API credential not found")
    return _sync_one(session, credential)


@router.put("/{credential_id}", response_model=ApiCredentialRead)
def update_api_key(
    credential_id: int,
    body: ApiCredentialUpdate,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    credential = session.get(ApiCredential, credential_id)
    if not credential:
        raise HTTPException(404, "API credential not found")
    duplicate = session.exec(
        select(ApiCredential).where(
            ApiCredential.vendor == credential.vendor,
            ApiCredential.name == body.name,
            ApiCredential.id != credential_id,
        )
    ).first()
    if duplicate:
        raise HTTPException(409, "A credential with this name already exists")
    credential.name = body.name
    session.add(credential)
    session.commit()
    session.refresh(credential)
    return credential_to_read(session, credential)


@router.delete("/{credential_id}", status_code=204)
def delete_api_key(
    credential_id: int,
    session: Session = Depends(get_session),
    _=Depends(verify_token),
):
    credential = session.get(ApiCredential, credential_id)
    if not credential:
        raise HTTPException(404, "API credential not found")
    if _device_count(session, credential_id):
        raise HTTPException(409, "Reassign or delete this credential's devices first")
    session.delete(credential)
    session.commit()
