import json
from datetime import datetime, timedelta

import requests
from sqlmodel import SQLModel, Session, create_engine

from dotmate.api.api import (
    DeviceIntervalSettings,
    DeviceSettings,
    DeviceStatus,
)
from web.backend import db, status_worker
from web.backend.models import (
    ApiCredential,
    Device,
    DeviceStatusRecord,
    Settings,
)


class StatusClient:
    def __init__(self):
        self.fail = False
        self.settings_calls = 0

    def get_device_status(self, device_id):
        if self.fail:
            raise requests.ConnectionError("offline")
        return DeviceStatus.model_validate(
            {
                "deviceId": device_id,
                "alias": "Desk",
                "location": "Office",
                "status": {
                    "version": "1.2.3",
                    "current": "Power Active",
                    "description": "Ready",
                    "battery": "Charging",
                    "wifi": "-62 dBm",
                },
                "renderInfo": {
                    "last": "12/18/2025 14:11",
                    "current": {
                        "rotated": False,
                        "border": 0,
                        "image": ["https://example.test/private.png"],
                    },
                    "next": {
                        "battery": "12/18/2025 17:11",
                        "power": "12/18/2025 14:16",
                    },
                },
            }
        )

    def get_device_settings(self, device_id):
        self.settings_calls += 1
        return DeviceSettings(
            interval=DeviceIntervalSettings(
                powerMs=5 * 60_000,
                batteryMs=120 * 60_000,
            )
        )


def setup_status_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'status.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db, "engine", engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        credential = ApiCredential(
            name="Personal", vendor="mindreset", api_key="secret"
        )
        session.add(credential)
        session.flush()
        device = Device(
            name="Desk",
            device_id="device-1",
            api_credential_id=credential.id,
        )
        session.add(device)
        session.flush()
        session.add(Settings(id=1, request_interval=0.1))
        session.add(DeviceStatusRecord(device_id=device.id))
        session.commit()
        device_id = device.id
    status_worker._client_cache.clear()
    return engine, device_id


def test_worker_persists_safe_status_and_follows_power_interval(
    tmp_path, monkeypatch
):
    engine, device_id = setup_status_db(tmp_path, monkeypatch)
    client = StatusClient()
    monkeypatch.setattr(
        status_worker, "create_vendor_client", lambda *args, **kwargs: client
    )
    now = datetime(2026, 7, 21, 8, 0)

    assert status_worker.refresh_device_status(device_id, now=now) is True

    with Session(engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        payload = json.loads(record.payload_json)
        assert payload["battery"] == "Charging"
        assert payload["image_count"] == 1
        assert "private.png" not in record.payload_json
        assert record.effective_interval_minutes == 5
        assert record.interval_source == "power"
        assert record.next_refresh_at == now + timedelta(minutes=5)
        assert record.last_error is None
    assert client.settings_calls == 1


def test_device_interval_uses_battery_interval_when_not_charging():
    status = DeviceStatus.model_validate(
        {
            "deviceId": "device-1",
            "status": {
                "current": "Battery Active",
                "battery": "82%",
            },
        }
    )
    settings = DeviceSettings(
        interval=DeviceIntervalSettings(
            powerMs=5 * 60_000,
            batteryMs=120 * 60_000,
        )
    )

    assert status_worker._device_interval(status, settings) == (120, "battery")


def test_custom_interval_skips_settings_and_failure_keeps_last_snapshot(
    tmp_path, monkeypatch
):
    engine, device_id = setup_status_db(tmp_path, monkeypatch)
    client = StatusClient()
    monkeypatch.setattr(
        status_worker, "create_vendor_client", lambda *args, **kwargs: client
    )
    with Session(engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        record.refresh_interval_minutes = 17
        session.add(record)
        session.commit()

    first = datetime(2026, 7, 21, 8, 0)
    assert status_worker.refresh_device_status(device_id, now=first) is True
    assert client.settings_calls == 0

    client.fail = True
    failed = first + timedelta(minutes=17)
    assert status_worker.refresh_device_status(device_id, now=failed) is False
    with Session(engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        assert json.loads(record.payload_json)["version"] == "1.2.3"
        assert record.last_success_at == first
        assert record.last_attempt_at == failed
        assert record.last_error == "Unable to connect to the vendor service"
        assert record.next_refresh_at == failed + timedelta(minutes=1)
        assert record.consecutive_failures == 1


def test_manual_refresh_requests_are_merged_in_the_persisted_queue(
    tmp_path, monkeypatch
):
    engine, device_id = setup_status_db(tmp_path, monkeypatch)

    first_requested, first_count = status_worker.request_status_refresh([device_id])
    second_requested, second_count = status_worker.request_status_refresh(
        [device_id, device_id]
    )

    assert first_count == second_count == 1
    assert second_requested >= first_requested
    with Session(engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        assert record.refresh_requested_at == second_requested
        assert record.next_refresh_at == second_requested


def test_worker_discards_response_when_device_identity_changes_mid_request(
    tmp_path, monkeypatch
):
    engine, device_id = setup_status_db(tmp_path, monkeypatch)

    class IdentityChangingClient(StatusClient):
        def get_device_status(self, remote_id):
            status = super().get_device_status(remote_id)
            with Session(engine) as session:
                device = session.get(Device, device_id)
                device.device_id = "device-2"
                session.add(device)
                session.commit()
            return status

    client = IdentityChangingClient()
    monkeypatch.setattr(
        status_worker, "create_vendor_client", lambda *args, **kwargs: client
    )
    now = datetime(2026, 7, 21, 8, 0)

    assert status_worker.refresh_device_status(device_id, now=now) is False
    with Session(engine) as session:
        record = session.get(DeviceStatusRecord, device_id)
        assert record.payload_json is None
        assert record.refresh_started_at is None
        assert record.next_refresh_at == now
