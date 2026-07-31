"""Stable, language-neutral error descriptors for the web client."""

from __future__ import annotations

import re
from typing import Any


_MESSAGE_CODES = {
    "Invalid or missing admin token": "unauthorized",
    "Device not found": "device.notFound",
    "Device has no API credential": "device.credentialMissing",
    "Choose a valid API credential": "device.credentialInvalid",
    "This device already exists for the selected vendor": "device.duplicate",
    "A device can only be reassigned within the same vendor": "device.vendorMismatch",
    "API credential not found": "credential.notFound",
    "A credential with this name already exists": "credential.duplicate",
    "A credential with this name or API key already exists": "credential.duplicate",
    "Credential data conflicts with an existing record": "credential.duplicate",
    "Credential name is duplicated in this batch": "credential.duplicate",
    "API key is duplicated in this batch": "credential.duplicate",
    "Reassign or delete this credential's devices first": "credential.devicesFirst",
    "Schedule not found": "schedule.notFound",
    "Unknown schedule type": "schedule.unsupported",
    "Choose a supported schedule type": "schedule.unsupported",
    "Check the highlighted schedule parameters": "schedule.invalid",
    "The existing schedule parameters are invalid": "schedule.invalid",
    "Replace the invalid stored parameters": "schedule.invalid",
    "API key is invalid or expired": "vendor.apiCredentialInvalid",
    "API credential is invalid or expired": "vendor.apiCredentialInvalid",
    "This API key cannot access the requested devices": "vendor.accessDenied",
    "API credential cannot access this device": "vendor.accessDenied",
    "Device not found by vendor": "vendor.deviceNotFound",
    "Device was not found by the vendor": "vendor.deviceNotFound",
    "Unable to connect to the vendor service": "vendor.unavailable",
    "Vendor returned an invalid response": "vendor.invalidResponse",
    "Vendor request failed": "vendor.requestFailed",
    "Unable to complete vendor request": "vendor.requestFailed",
    "Unable to refresh device status": "remote.statusRefreshFailed",
    "Scheduler reload failed; settings were not updated": "scheduler.reload",
    "Scheduler reload failed; device was not updated": "scheduler.reload",
    "Scheduler reload failed; device was not deleted": "scheduler.reload",
    "Scheduler reload failed; schedule not saved": "scheduler.reload",
    "Scheduler reload failed; schedule not updated": "scheduler.reload",
    "Scheduler reload failed; schedule was not deleted": "scheduler.reload",
    "This field is required": "required",
    "Field required": "required",
}


def describe_message(
    message: str | None,
    *,
    status_code: int | None = None,
) -> dict[str, Any]:
    if message in _MESSAGE_CODES:
        return {"code": _MESSAGE_CODES[message], "params": {}}

    if message:
        status_match = re.fullmatch(r"Vendor request failed with status (\d+)", message)
        if status_match:
            return {
                "code": "vendor.status",
                "params": {"status": int(status_match.group(1))},
            }
        unsupported_vendor = re.fullmatch(r"Unsupported vendor: (.+)", message)
        if unsupported_vendor:
            return {
                "code": "vendor.requestFailed",
                "params": {"vendor": unsupported_vendor.group(1)},
            }

    if status_code == 404:
        code = "notFound"
    elif status_code == 409:
        code = "conflict"
    elif status_code == 422:
        code = "validation"
    elif status_code is not None and status_code >= 500:
        code = "server"
    else:
        code = "generic"
    return {"code": code, "params": {}}


def structured_http_detail(detail: Any, status_code: int) -> dict[str, Any]:
    if isinstance(detail, dict):
        result = dict(detail)
        if result.get("conflicts"):
            conflict = result["conflicts"][0]
            result.setdefault("code", "schedule.conflict")
            result.setdefault(
                "params",
                {
                    "name": conflict["name"],
                    "cron": conflict["cron"],
                    "sample": conflict["sample_at"],
                },
            )
        else:
            descriptor = describe_message(result.get("message"), status_code=status_code)
            result.setdefault("code", descriptor["code"])
            result.setdefault("params", descriptor["params"])

        fields = result.get("fields") or {}
        result.setdefault(
            "field_errors",
            {
                field: describe_message(message, status_code=status_code)
                for field, message in fields.items()
            },
        )
        return result

    message = str(detail)
    descriptor = describe_message(message, status_code=status_code)
    return {"message": message, **descriptor, "fields": {}, "field_errors": {}}
