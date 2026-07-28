from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from web.backend import db
from web.backend.app import app
from web.backend.routes import devices as device_routes
from web.backend.routes import api_keys as api_key_routes
from web.backend.routes import settings as settings_routes
from web.backend import scheduler as scheduler_module


class EmptyVendorClient:
    def list_devices(self):
        return []


@pytest.fixture
def api_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(scheduler_module, "engine", engine)
    monkeypatch.setattr(device_routes, "reload_scheduler", lambda: None)
    monkeypatch.setattr(settings_routes, "reload_scheduler", lambda: None)
    monkeypatch.setattr(
        api_key_routes,
        "create_vendor_client",
        lambda vendor, api_key, request_interval: EmptyVendorClient(),
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db.get_session] = override_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
