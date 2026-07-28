import pytest
import json
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import inspect
from sqlmodel import Session, create_engine

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
    assert "api_credential_id" in {
        column["name"] for column in inspector.get_columns("device")
    }
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
    assert body["summary"] == [{"label": "Main Title", "value": "Good morning"}]


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
