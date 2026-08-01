import pytest
import json
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import inspect
from sqlmodel import SQLModel, Session, create_engine

from dotmate.api.api import (
    ApiResponse,
    DeviceIntervalSettings,
    DeviceSettings,
    DeviceSleepSettings,
    DeviceTask,
    RemoteDevice,
    TimezoneInfo,
)
from web.backend import db, scheduler as scheduler_module
from web.backend.models import DeviceStatusRecord
from web.backend.routes import api_keys as api_key_routes
from web.backend.routes import auth as auth_routes
from web.backend.routes import devices as device_routes
from web.backend.routes import settings as settings_routes
from web.backend.schedule_types import get_schedule_type_schema


def create_api_key(client, name="Personal", api_key="valid-key") -> int:
    response = client.post(
        "/api/api-keys/batch",
        json={"items": [{"name": name, "vendor": "mindreset", "api_key": api_key}]},
    )
    assert response.status_code == 200
    return response.json()["results"][0]["credential"]["id"]


def create_device(client) -> int:
    credential_id = create_api_key(client)
    response = client.post(
        "/api/devices",
        json={
            "name": "Desk",
            "device_id": "device-1",
            "api_credential_id": credential_id,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_schedule_schema_is_human_readable_and_type_safe():
    schema = get_schedule_type_schema()

    assert schema["work"]["label"] == "Work Countdown"
    assert schema["work"]["description"]
    assert "image" not in schema
    assert schema["text"]["fields"]["styles"]["hidden"] is True
    border = schema["code_status"]["fields"]["border"]
    assert border["type"] == "integer"
    assert [option["value"] for option in border["options"]] == [0, 1]


def test_init_db_creates_final_schema_without_migrations(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()
    inspector = inspect(engine)
    assert "api_credential" in inspector.get_table_names()
    device_columns = {column["name"] for column in inspector.get_columns("device")}
    assert "api_credential_id" in device_columns
    assert "device_model" in device_columns
    assert "name" in {column["name"] for column in inspector.get_columns("schedule")}
    assert "device_status" in inspector.get_table_names()
    assert "api_key" not in {
        column["name"] for column in inspector.get_columns("settings")
    }


def test_schedule_create_validates_params_and_normalizes_defaults(api_client):
    device_id = create_device(api_client)

    invalid = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={"name": "Work", "cron": "0 9 * * *", "type": "work", "params": {}},
    )
    assert invalid.status_code == 422
    assert set(invalid.json()["detail"]["fields"]) == {"clock_in", "clock_out"}

    created = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "  Morning title  ",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Good morning"},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Morning title"
    assert body["params"]["dither_type"] == "NONE"
    assert body["summary"] == [
        {
            "field": "main_title",
            "label": "Main Title",
            "value": "Good morning",
            "raw_value": "Good morning",
        }
    ]


def test_structured_errors_are_opt_in_and_language_neutral(api_client):
    legacy = api_client.post("/api/devices/schedules/999/run")
    assert legacy.status_code == 404
    assert legacy.json()["detail"] == "Schedule not found"

    structured = api_client.post(
        "/api/devices/schedules/999/run",
        headers={"X-Dotmate-Structured-Errors": "1"},
    )
    assert structured.status_code == 404
    assert structured.json()["detail"]["code"] == "schedule.notFound"
    assert structured.json()["detail"]["message"] == "Schedule not found"

    validation = api_client.put(
        "/api/settings",
        json={"request_interval": 0},
        headers={"X-Dotmate-Structured-Errors": "1"},
    )
    assert validation.status_code == 422
    assert validation.json()["detail"]["code"] == "validation"
    assert "request_interval" in validation.json()["detail"]["field_errors"]


def test_batch_errors_include_stable_error_codes(api_client):
    response = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "Same", "vendor": "mindreset", "api_key": "one"},
                {"name": "Same", "vendor": "mindreset", "api_key": "two"},
            ]
        },
    )
    assert response.status_code == 200
    error = next(item for item in response.json()["results"] if item["status"] == "error")
    assert error["error_code"] == "credential.duplicate"


def test_schedule_summary_never_contains_sensitive_fields(api_client):
    device_id = create_device(api_client)
    secret = "secret-api-key"
    response = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Coding status",
            "cron": "*/5 * * * *",
            "type": "code_status",
            "params": {
                "wakatime_url": "https://wakatime.example",
                "wakatime_api_key": secret,
                "wakatime_user_id": "leslie",
            },
        },
    )
    assert response.status_code == 201
    assert secret not in str(response.json()["summary"])
    assert response.json()["summary"][0]["value"] == "leslie"


def test_schedule_update_preserves_params_when_only_name_changes(api_client):
    device_id = create_device(api_client)
    created = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Original",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Hello"},
        },
    ).json()

    updated = api_client.put(
        f"/api/devices/schedules/{created['id']}",
        json={"name": "Renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["params"]["main_title"] == "Hello"


def test_schedule_create_rejects_exact_cron_conflict(api_client):
    device_id = create_device(api_client)
    first = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Morning title",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Hello"},
        },
    )
    assert first.status_code == 201

    conflict = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Also morning",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "World"},
        },
    )
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert "Morning title" in detail["message"]
    assert detail["fields"]["cron"]
    assert len(detail["conflicts"]) == 1
    assert detail["conflicts"][0]["name"] == "Morning title"
    assert detail["conflicts"][0]["cron"] == "0 9 * * *"
    assert "sample_at" in detail["conflicts"][0]


def test_schedule_create_rejects_semantic_cron_conflict(api_client):
    device_id = create_device(api_client)
    first = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Every five",
            "cron": "*/5 * * * *",
            "type": "title_image",
            "params": {"main_title": "A"},
        },
    )
    assert first.status_code == 201

    conflict = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Enumerated five",
            "cron": "0,5,10,15,20,25,30,35,40,45,50,55 * * * *",
            "type": "title_image",
            "params": {"main_title": "B"},
        },
    )
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["conflicts"][0]["name"] == "Every five"
    assert "Every five" in detail["message"]


def test_schedule_create_allows_non_overlapping_crons(api_client):
    device_id = create_device(api_client)
    morning = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Morning",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "AM"},
        },
    )
    assert morning.status_code == 201

    evening = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Evening",
            "cron": "0 18 * * *",
            "type": "title_image",
            "params": {"main_title": "PM"},
        },
    )
    assert evening.status_code == 201


def test_schedule_update_allows_unchanged_cron_without_self_conflict(api_client):
    device_id = create_device(api_client)
    created = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Solo",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Hello"},
        },
    ).json()

    updated = api_client.put(
        f"/api/devices/schedules/{created['id']}",
        json={
            "name": "Solo renamed",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Hello"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Solo renamed"


def test_schedule_update_rejects_cron_conflict_with_sibling(api_client):
    device_id = create_device(api_client)
    first = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Morning",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "AM"},
        },
    ).json()
    second = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Evening",
            "cron": "0 18 * * *",
            "type": "title_image",
            "params": {"main_title": "PM"},
        },
    ).json()

    conflict = api_client.put(
        f"/api/devices/schedules/{second['id']}",
        json={"cron": "0 9 * * *"},
    )
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["conflicts"][0]["id"] == first["id"]
    assert detail["conflicts"][0]["name"] == "Morning"


def test_find_cron_conflicts_unit():
    from datetime import datetime, timezone

    from web.backend.schedule_conflicts import find_cron_conflicts

    now = datetime(2026, 7, 31, 0, 0, tzinfo=timezone.utc)
    existing = [(1, "Every five", "*/5 * * * *")]
    conflicts = find_cron_conflicts(
        "0,5,10,15,20,25,30,35,40,45,50,55 * * * *",
        existing,
        now=now,
    )
    assert len(conflicts) == 1
    assert conflicts[0].id == 1
    assert conflicts[0].sample_at.minute % 5 == 0

    none = find_cron_conflicts(
        "0 18 * * *",
        [(1, "Morning", "0 9 * * *")],
        now=now,
    )
    assert none == []

    self_ok = find_cron_conflicts(
        "0 9 * * *",
        [(1, "Self", "0 9 * * *")],
        exclude_id=1,
        now=now,
    )
    assert self_ok == []


def test_run_schedule_pushes_immediately(api_client, monkeypatch):
    device_id = create_device(api_client)
    created = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Morning title",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Hello"},
        },
    ).json()

    calls = []

    def fake_execute(view_type, client, device_remote_id, params, overlay, profile):
        calls.append(
            {
                "view_type": view_type,
                "device_id": device_remote_id,
                "params": params,
                "overlay": overlay,
                "profile_name": profile.name,
                "width": profile.width,
                "height": profile.height,
            }
        )

    monkeypatch.setattr(
        "web.backend.scheduler.ViewFactory.execute_view", fake_execute
    )

    response = api_client.post(f"/api/devices/schedules/{created['id']}/run")
    assert response.status_code == 200
    assert response.json()["message"] == "Pushed 'Morning title' to Desk"
    assert len(calls) == 1
    assert calls[0]["view_type"] == "title_image"
    assert calls[0]["device_id"] == "device-1"
    assert calls[0]["params"]["main_title"] == "Hello"
    assert calls[0]["profile_name"] == "quote0"
    assert calls[0]["width"] == 296
    assert calls[0]["height"] == 152


def test_run_schedule_reports_vendor_push_failure(api_client, monkeypatch):
    device_id = create_device(api_client)
    created = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Failed text",
            "cron": "0 9 * * *",
            "type": "text",
            "params": {"message": "Hello"},
        },
    ).json()

    class FailingClient:
        def display_text(self, device_id, payload):
            raise RuntimeError("vendor unavailable")

    monkeypatch.setattr(
        scheduler_module,
        "create_vendor_client",
        lambda vendor, key, interval: FailingClient(),
    )

    response = api_client.post(f"/api/devices/schedules/{created['id']}/run")

    assert response.status_code == 502
    assert response.json()["detail"] == "Unable to push schedule: vendor unavailable"


def test_run_schedule_not_found(api_client):
    response = api_client.post("/api/devices/schedules/99999/run")
    assert response.status_code == 404
    assert response.json()["detail"] == "Schedule not found"


def test_run_schedule_rejects_text_on_image_only_device(api_client):
    credential_id = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "Zectrix", "vendor": "zectrix", "api_key": "zt_key"}
            ]
        },
    ).json()["results"][0]["credential"]["id"]
    device = api_client.post(
        "/api/devices",
        json={
            "name": "Note",
            "device_id": "AA:BB:CC:DD:EE:FF",
            "api_credential_id": credential_id,
            "device_model": "note4",
        },
    ).json()

    # Bypass create validation by inserting a text schedule directly.
    from web.backend.models import Schedule

    with Session(db.engine) as session:
        schedule = Schedule(
            device_id=device["id"],
            name="Text",
            cron="0 9 * * *",
            type="text",
            params=json.dumps({"message": "hi"}),
        )
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
        schedule_id = schedule.id

    response = api_client.post(f"/api/devices/schedules/{schedule_id}/run")
    assert response.status_code == 422
    assert "text support" in response.json()["detail"]


def test_raw_image_cannot_be_created_from_web(api_client):
    device_id = create_device(api_client)
    response = api_client.post(
        f"/api/devices/{device_id}/schedules",
        json={
            "name": "Image",
            "cron": "0 9 * * *",
            "type": "image",
            "params": {"image_data": "not-an-image"},
        },
    )
    assert response.status_code == 422
    assert "type" in response.json()["detail"]["fields"]


def test_auth_status_handles_open_and_protected_modes(api_client, monkeypatch):
    monkeypatch.setattr(auth_routes, "ADMIN_TOKEN", "")
    assert api_client.get("/api/auth/status").json() == {
        "auth_required": False,
        "authenticated": True,
    }

    monkeypatch.setattr(auth_routes, "ADMIN_TOKEN", "expected")
    assert api_client.get("/api/auth/status").json()["authenticated"] is False
    assert api_client.get(
        "/api/auth/status", headers={"Authorization": "Bearer expected"}
    ).json() == {"auth_required": True, "authenticated": True}


def test_settings_are_restored_when_scheduler_reload_fails(api_client, monkeypatch):
    monkeypatch.setattr(
        settings_routes,
        "reload_scheduler",
        lambda: (_ for _ in ()).throw(RuntimeError("reload failed")),
    )
    response = api_client.put(
        "/api/settings",
        json={"request_interval": 2},
    )
    assert response.status_code == 500
    settings = api_client.get("/api/settings").json()
    assert settings == {"request_interval": 1.0}


def test_batch_keys_import_and_dedupe_devices_in_input_order(api_client, monkeypatch):
    devices_by_key = {
        "first": [
            RemoteDevice(
                id="shared",
                alias="Shared from first",
                series="quote",
                model="quote_0",
                edition=1,
            ),
            RemoteDevice(
                id="first-only",
                alias=None,
                series="quote",
                model="quote_0",
                edition=1,
            ),
        ],
        "second": [
            RemoteDevice(
                id="shared",
                alias="Shared from second",
                series="quote",
                model="quote_0",
                edition=1,
            )
        ],
    }

    class Client:
        def __init__(self, key):
            self.key = key

        def list_devices(self):
            return devices_by_key[self.key]

    monkeypatch.setattr(
        api_key_routes,
        "create_vendor_client",
        lambda vendor, key, interval: Client(key),
    )
    response = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "First", "vendor": "mindreset", "api_key": "first"},
                {"name": "Second", "vendor": "mindreset", "api_key": "second"},
            ]
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["sync"]["created"] == 2
    assert results[1]["sync"]["created"] == 0
    assert results[1]["sync"]["duplicates"] == 1
    devices = api_client.get("/api/devices").json()
    assert {device["device_id"] for device in devices} == {"shared", "first-only"}
    shared = next(device for device in devices if device["device_id"] == "shared")
    assert shared["name"] == "Shared from first"
    assert shared["api_credential_name"] == "First"


def test_batch_keys_reports_invalid_vendor_without_rejecting_valid_rows(api_client):
    response = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "Unknown", "vendor": "other", "api_key": "other-key"},
                {"name": "Valid", "vendor": "mindreset", "api_key": "valid-key"},
            ]
        },
    )
    assert response.status_code == 200
    assert [item["status"] for item in response.json()["results"]] == [
        "error",
        "success",
    ]
    key = api_client.get("/api/api-keys").json()[0]
    assert key["masked_key"] != "valid-key"
    assert "api_key" not in key


def test_api_credential_vendor_defaults_to_mindreset(api_client):
    response = api_client.post(
        "/api/api-keys/batch",
        json={"items": [{"name": "Default vendor", "api_key": "default-key"}]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["vendor"] == "mindreset"


def test_device_duplicate_and_cross_vendor_reassignment_are_rejected(api_client):
    credential_id = create_api_key(api_client)
    created = api_client.post(
        "/api/devices",
        json={
            "name": "Desk",
            "device_id": "same-id",
            "api_credential_id": credential_id,
        },
    )
    assert created.status_code == 201
    duplicate = api_client.post(
        "/api/devices",
        json={
            "name": "Duplicate",
            "device_id": "same-id",
            "api_credential_id": credential_id,
        },
    )
    assert duplicate.status_code == 409
    assert api_client.delete(f"/api/api-keys/{credential_id}").status_code == 409


def test_device_update_rejects_non_positive_credential_id(api_client):
    device_id = create_device(api_client)

    response = api_client.put(
        f"/api/devices/{device_id}",
        json={"api_credential_id": 0},
    )

    assert response.status_code == 422
    assert api_client.get(f"/api/devices/{device_id}").json()[
        "api_credential_id"
    ] > 0


def test_spa_fallback_rejects_encoded_path_traversal(api_client):
    response = api_client.get(
        "/%2e%2e%2f%2e%2e%2f%2e%2e%2fpyproject.toml"
    )

    assert response.status_code == 404
    assert "[project]" not in response.text


def test_status_cache_policy_and_async_refresh_endpoints(api_client):
    device_id = create_device(api_client)
    device = api_client.get(f"/api/devices/{device_id}").json()
    assert device["remote_status"] is None
    assert device["status_policy"]["state"] == "pending"

    with Session(db.engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        record.payload_json = json.dumps(
            {
                "remote_device_id": "device-1",
                "alias": "Desk",
                "location": "Office",
                "version": "1.2.3",
                "current": "Power Active",
                "description": "Ready",
                "battery": "Charging",
                "wifi": "-62 dBm",
                "last_render": "12/18/2025 14:11",
                "rotated": False,
                "border": 0,
                "image_count": 1,
                "next_battery_render": "12/18/2025 17:11",
                "next_power_render": "12/18/2025 14:16",
            }
        )
        session.add(record)
        session.commit()

    cached = api_client.get(f"/api/devices/{device_id}").json()
    assert cached["remote_status"]["battery"] == "Charging"
    assert "image" not in cached["remote_status"]

    custom = api_client.patch(
        f"/api/devices/{device_id}/remote/status/policy",
        json={"refresh_interval_minutes": 17},
    )
    assert custom.status_code == 200
    assert custom.json()["refresh_interval_minutes"] == 17
    assert (
        api_client.patch(
            f"/api/devices/{device_id}/remote/status/policy",
            json={"refresh_interval_minutes": 721},
        ).status_code
        == 422
    )

    single = api_client.post(
        f"/api/devices/{device_id}/remote/status/refresh"
    )
    assert single.status_code == 202
    assert single.json()["queued"] == 1
    batch = api_client.post("/api/devices/remote/statuses/refresh")
    assert batch.status_code == 202
    assert batch.json()["queued"] == 1


def test_device_identity_change_clears_status_and_delete_removes_cache(api_client):
    device_id = create_device(api_client)
    with Session(db.engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        record.payload_json = json.dumps(
            {
                "remote_device_id": "device-1",
                "alias": None,
                "location": None,
                "version": "old",
                "current": "old",
                "description": "old",
                "battery": "old",
                "wifi": "old",
                "last_render": "old",
                "rotated": False,
                "border": 0,
                "image_count": 0,
                "next_battery_render": "old",
                "next_power_render": "old",
            }
        )
        session.add(record)
        session.commit()

    updated = api_client.put(
        f"/api/devices/{device_id}", json={"device_id": "device-2"}
    )
    assert updated.status_code == 200
    assert updated.json()["remote_status"] is None
    assert updated.json()["status_policy"]["state"] == "pending"

    assert api_client.delete(f"/api/devices/{device_id}").status_code == 204
    with Session(db.engine) as session:
        assert session.get(DeviceStatusRecord, device_id) is None


def test_remote_controls_use_bound_credential_and_redact_binary_data(
    api_client, monkeypatch
):
    device_id = create_device(api_client)

    class RemoteClient:
        def get_device_settings(self, remote_id):
            assert remote_id == "device-1"
            return DeviceSettings(
                alias="Desk",
                location="Office",
                timezone="Asia/Shanghai",
                interval=DeviceIntervalSettings(powerMs=60000, batteryMs=120000),
                sleep=DeviceSleepSettings(enabled=True, start="22:00", end="07:00"),
            )

        def update_device_settings(self, remote_id, payload):
            return self.get_device_settings(remote_id)

        def list_timezones(self):
            return [
                TimezoneInfo(
                    key="Asia/Shanghai",
                    name="Shanghai",
                    utcOffsetMinutes=480,
                    utcOffsetLabel="UTC+8",
                )
            ]

        def switch_next_content(self, remote_id):
            return ApiResponse(message="switched")

        def list_device_content(self, remote_id, task_type="loop"):
            assert task_type == "loop"
            return [
                DeviceTask(
                    type="IMAGE_API",
                    key="image-1",
                    image={"key": "dot/user/secret.png"},
                    icon={"key": "dot/user/secret-icon.png"},
                )
            ]

    monkeypatch.setattr(
        device_routes,
        "create_vendor_client",
        lambda vendor, key, interval: RemoteClient(),
    )
    settings = api_client.get(f"/api/devices/{device_id}/remote/settings")
    assert settings.status_code == 200
    assert settings.json()["power_interval_minutes"] == 1
    assert (
        api_client.get(f"/api/devices/{device_id}/remote/timezones").status_code == 200
    )
    assert api_client.post(f"/api/devices/{device_id}/remote/next").json() == {
        "message": "switched"
    }
    content = api_client.get(f"/api/devices/{device_id}/remote/content").json()[0]
    assert content["has_image"] is True
    assert content["has_icon"] is True
    assert "secret" not in str(content)


def test_scheduler_reuses_one_vendor_client_per_credential(api_client, monkeypatch):
    credential_id = create_api_key(api_client)
    for index in range(2):
        device = api_client.post(
            "/api/devices",
            json={
                "name": f"Desk {index}",
                "device_id": f"device-{index}",
                "api_credential_id": credential_id,
            },
        ).json()
        response = api_client.post(
            f"/api/devices/{device['id']}/schedules",
            json={
                "name": f"Title {index}",
                "cron": "0 9 * * *",
                "type": "title_image",
                "params": {"main_title": "Hello"},
            },
        )
        assert response.status_code == 201

    clients = []

    def create_client(vendor, key, interval):
        client = object()
        clients.append(client)
        return client

    monkeypatch.setattr(scheduler_module, "create_vendor_client", create_client)
    specs = scheduler_module._build_job_specs()
    assert len(specs) == 2
    assert len(clients) == 1
    assert specs[0].args[1] is specs[1].args[1]


class FakeScheduler:
    def __init__(self):
        self.running = True
        self.paused = False
        self.jobs = []

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def remove_all_jobs(self):
        self.jobs = []

    def add_job(self, *, id, name, **kwargs):
        if name == "bad":
            raise RuntimeError("cannot install")
        self.jobs.append(id)


def test_scheduler_restores_last_known_good_snapshot(monkeypatch):
    fake = FakeScheduler()
    trigger = CronTrigger.from_crontab("* * * * *")
    old = scheduler_module.JobSpec("old", "old", trigger, [])
    bad = scheduler_module.JobSpec("bad", "bad", trigger, [])
    monkeypatch.setattr(scheduler_module, "scheduler", fake)
    monkeypatch.setattr(scheduler_module, "_active_job_specs", [old])

    with pytest.raises(RuntimeError):
        scheduler_module._replace_jobs([bad])

    assert fake.jobs == ["old"]
    assert fake.paused is False
    assert scheduler_module._active_job_specs == [old]


def test_vendors_and_device_models_are_listed(api_client):
    vendors = api_client.get("/api/vendors").json()
    assert {item["id"] for item in vendors} == {"mindreset", "zectrix"}
    mindreset = next(item for item in vendors if item["id"] == "mindreset")
    zectrix = next(item for item in vendors if item["id"] == "zectrix")
    assert mindreset["supports_device_discovery"] is True
    assert zectrix["supports_device_discovery"] is True
    assert "status" in mindreset["capabilities"]
    assert zectrix["capabilities"] == ["devices"]

    models = api_client.get("/api/device-models").json()
    assert {item["id"] for item in models} == {"quote0", "note4"}
    note4 = api_client.get("/api/device-models?vendor=zectrix").json()
    assert len(note4) == 1
    assert note4[0]["id"] == "note4"
    assert note4[0]["width"] == 400
    assert note4[0]["supports_text"] is False


def test_zectrix_credential_discovers_note4_devices(api_client, monkeypatch):
    class Client:
        def list_devices(self):
            return [
                RemoteDevice(
                    id="AA:BB:CC:DD:EE:FF",
                    alias="我的设备",
                    series="zectrix",
                    model="bread-compact-wifi",
                ),
                RemoteDevice(
                    id="11:22:33:44:55:66",
                    alias=None,
                    series="zectrix",
                    model="bread-compact-wifi",
                ),
            ]

    monkeypatch.setattr(
        api_key_routes,
        "create_vendor_client",
        lambda vendor, key, interval: Client(),
    )
    response = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "Zectrix Key", "vendor": "zectrix", "api_key": "zt_test_key"}
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "success"
    assert result["validation_status"] == "validated"
    assert result["sync"] == {
        "fetched": 2,
        "created": 2,
        "linked": 0,
        "duplicates": 0,
    }
    assert result["credential"]["vendor"] == "zectrix"

    devices = api_client.get("/api/devices").json()
    assert {device["device_id"] for device in devices} == {
        "AA:BB:CC:DD:EE:FF",
        "11:22:33:44:55:66",
    }
    named = next(d for d in devices if d["device_id"] == "AA:BB:CC:DD:EE:FF")
    assert named["name"] == "我的设备"
    assert named["device_model"] == "note4"
    unnamed = next(d for d in devices if d["device_id"] == "11:22:33:44:55:66")
    assert unnamed["name"] == "11:22:33:44:55:66"
    assert unnamed["device_model"] == "note4"

    sync = api_client.post(f"/api/api-keys/{result['credential']['id']}/sync")
    assert sync.status_code == 200
    assert sync.json()["sync"]["duplicates"] == 2
    assert sync.json()["sync"]["created"] == 0


def test_note4_device_and_schedule_schema(api_client):
    credential_id = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "Zectrix Key", "vendor": "zectrix", "api_key": "zt_note4"}
            ]
        },
    ).json()["results"][0]["credential"]["id"]

    created = api_client.post(
        "/api/devices",
        json={
            "name": "Note 4 Desk",
            "device_id": "AA:BB:CC:DD:EE:FF",
            "api_credential_id": credential_id,
            "device_model": "note4",
            "show_battery_icon": True,
            "show_battery_percentage": True,
            "show_refresh_time": True,
        },
    )
    assert created.status_code == 201
    device = created.json()
    assert device["device_model"] == "note4"
    assert device["device_model_label"] == "Note 4"
    assert device["display_width"] == 400
    assert device["display_height"] == 300
    assert device["show_battery_icon"] is False
    assert device["show_battery_percentage"] is False
    assert device["show_refresh_time"] is True
    assert "battery_overlay" not in device["display_capabilities"]

    mismatched = api_client.post(
        "/api/devices",
        json={
            "name": "Bad",
            "device_id": "bad-id",
            "api_credential_id": credential_id,
            "device_model": "quote0",
        },
    )
    assert mismatched.status_code == 422

    schema = api_client.get(f"/api/devices/{device['id']}/schedule-types").json()
    assert "text" not in schema
    assert "title_image" in schema
    assert "page_id" in schema["title_image"]["fields"]
    assert "border" not in schema["title_image"]["fields"]
    assert "link" not in schema["title_image"]["fields"]
    dither = schema["title_image"]["fields"]["dither_type"]
    assert [option["value"] for option in dither["options"]] == ["DIFFUSION", "NONE"]

    text = api_client.post(
        f"/api/devices/{device['id']}/schedules",
        json={
            "name": "Text",
            "cron": "0 9 * * *",
            "type": "text",
            "params": {"message": "hi"},
        },
    )
    assert text.status_code == 422

    bad_page = api_client.post(
        f"/api/devices/{device['id']}/schedules",
        json={
            "name": "Title",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {"main_title": "Hello", "page_id": 9},
        },
    )
    assert bad_page.status_code == 422
    assert "page_id" in bad_page.json()["detail"]["fields"]

    created_schedule = api_client.post(
        f"/api/devices/{device['id']}/schedules",
        json={
            "name": "Title",
            "cron": "0 9 * * *",
            "type": "title_image",
            "params": {
                "main_title": "Hello",
                "page_id": 3,
                "border": 1,
                "link": "https://example.com",
            },
        },
    )
    assert created_schedule.status_code == 201
    body = created_schedule.json()
    assert body["params"]["page_id"] == 3
    assert "border" not in body["params"]
    assert "link" not in body["params"]
    assert any(item["value"] == "Page 3" for item in body["summary"])


def test_quote0_schedule_schema_hides_page_id(api_client):
    device_id = create_device(api_client)
    device = api_client.get(f"/api/devices/{device_id}").json()
    assert device["device_model"] == "quote0"
    assert device["display_width"] == 296

    schema = api_client.get(f"/api/devices/{device_id}/schedule-types").json()
    assert "text" in schema
    assert "page_id" not in schema["title_image"]["fields"]
    assert "border" in schema["title_image"]["fields"]


def test_scheduler_passes_device_profile(api_client, monkeypatch):
    credential_id = api_client.post(
        "/api/api-keys/batch",
        json={
            "items": [
                {"name": "Zectrix Key", "vendor": "zectrix", "api_key": "zt_sched"}
            ]
        },
    ).json()["results"][0]["credential"]["id"]
    device = api_client.post(
        "/api/devices",
        json={
            "name": "Note",
            "device_id": "mac-1",
            "api_credential_id": credential_id,
            "device_model": "note4",
        },
    ).json()
    assert (
        api_client.post(
            f"/api/devices/{device['id']}/schedules",
            json={
                "name": "Title",
                "cron": "0 9 * * *",
                "type": "title_image",
                "params": {"main_title": "Hello", "page_id": 2},
            },
        ).status_code
        == 201
    )

    monkeypatch.setattr(
        scheduler_module,
        "create_vendor_client",
        lambda vendor, key, interval: object(),
    )
    specs = scheduler_module._build_job_specs()
    assert len(specs) == 1
    profile = specs[0].args[5]
    assert profile.name == "note4"
    assert profile.width == 400
    assert profile.height == 300
    assert profile.supports_text is False


def test_status_worker_skips_vendors_without_status(tmp_path, monkeypatch):
    from web.backend import status_worker
    from web.backend.models import ApiCredential, Device, DeviceStatusRecord

    engine = create_engine(f"sqlite:///{tmp_path / 'status-skip.db'}")
    monkeypatch.setattr(db, "engine", engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        mindreset = ApiCredential(
            name="MR", vendor="mindreset", api_key="mr-key"
        )
        zectrix = ApiCredential(
            name="ZX", vendor="zectrix", api_key="zt-key"
        )
        session.add(mindreset)
        session.add(zectrix)
        session.flush()
        quote = Device(
            name="Quote",
            device_id="q1",
            api_credential_id=mindreset.id,
            device_model="quote0",
        )
        note = Device(
            name="Note",
            device_id="n1",
            api_credential_id=zectrix.id,
            device_model="note4",
        )
        session.add(quote)
        session.add(note)
        session.commit()
        quote_id, note_id = quote.id, note.id

    created = status_worker.ensure_all_status_records(Session(engine))
    assert created == 1
    with Session(engine) as session:
        assert session.get(DeviceStatusRecord, quote_id) is not None
        assert session.get(DeviceStatusRecord, note_id) is None

    due = status_worker._due_device_ids(status_worker.utc_now())
    assert quote_id in due
    assert note_id not in due


def test_migrate_schema_backfills_quote0(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    monkeypatch.setattr(db, "engine", engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE api_credential (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                vendor VARCHAR NOT NULL,
                api_key VARCHAR NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE device (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                device_id VARCHAR NOT NULL,
                api_credential_id INTEGER NOT NULL,
                show_battery_icon BOOLEAN NOT NULL,
                show_battery_percentage BOOLEAN NOT NULL,
                show_refresh_time BOOLEAN NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO api_credential (id, name, vendor, api_key) "
            "VALUES (1, 'Personal', 'mindreset', 'key')"
        )
        conn.exec_driver_sql(
            "INSERT INTO device "
            "(id, name, device_id, api_credential_id, show_battery_icon, "
            "show_battery_percentage, show_refresh_time) "
            "VALUES (1, 'Desk', 'device-1', 1, 1, 1, 0)"
        )

    db.init_db()
    with Session(engine) as session:
        from web.backend.models import Device

        device = session.get(Device, 1)
        assert device.device_model == "quote0"
        assert device.show_battery_icon is True
