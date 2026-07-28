"""API credential management and remote device discovery."""

from __future__ import annotations

import logging

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from web.backend.db import get_session
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
    session: Session, credential: ApiCredential
) -> ApiCredentialRead:
    return ApiCredentialRead(
        id=credential.id,
        name=credential.name,
        vendor=credential.vendor,
        masked_key=_mask_key(credential.api_key),
        device_count=_device_count(session, credential.id),
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
        )
        session.add(device)
        session.flush()
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
        try:
            get_vendor(item.vendor)
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
                    error=error,
                )
            )
            continue

        try:
            client = create_vendor_client(item.vendor, item.api_key, interval)
            remote_devices = client.list_devices()
        except Exception as exc:
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=item.name,
                    vendor=item.vendor,
                    status="error",
                    error=_upstream_message(exc),
                )
            )
            continue
        candidates.append((index, item, remote_devices))

    for index, item, remote_devices in candidates:
        credential = ApiCredential(
            name=item.name,
            vendor=item.vendor,
            api_key=item.api_key,
        )
        session.add(credential)
        session.flush()
        stats = _sync_devices(session, credential, remote_devices)
        session.flush()
        results.append(
            ApiCredentialBatchResult(
                index=index,
                name=item.name,
                vendor=item.vendor,
                status="success",
                credential=credential_to_read(session, credential),
                sync=stats,
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
    try:
        client = create_vendor_client(
            credential.vendor, credential.api_key, _request_interval(session)
        )
        remote_devices = client.list_devices()
        stats = _sync_devices(session, credential, remote_devices)
        session.commit()
        session.refresh(credential)
    except Exception as exc:
        session.rollback()
        raise HTTPException(502, _upstream_message(exc)) from exc
    return ApiCredentialSyncResult(
        credential=credential_to_read(session, credential), sync=stats
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
            synced = _sync_one(session, credential)
            results.append(
                ApiCredentialBatchResult(
                    index=index,
                    name=credential.name,
                    vendor=credential.vendor,
                    status="success",
                    credential=synced.credential,
                    sync=synced.sync,
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
