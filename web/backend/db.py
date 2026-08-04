import os
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from web.backend import models as _models  # noqa: F401 - registers SQLModel tables
from web.backend.device_models import DEFAULT_DEVICE_MODEL, get_device_model
from web.backend.models import ApiCredential, Device

DB_PATH = os.environ.get("DOTMATE_DB_PATH", str(Path("data") / "dotmate.db"))

# Ensure the parent directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)


def _column_names(session: Session, table: str) -> set[str]:
    rows = session.connection().execute(text(f"PRAGMA table_info({table})")).all()
    return {row[1] for row in rows}


def migrate_schema(session: Session) -> None:
    """Apply additive schema upgrades and backfill device models.

    Runs inside the caller's transaction. Aborts on unknown vendors or
    model/vendor ownership conflicts rather than deleting data.
    """
    columns = _column_names(session, "device")
    if "device_model" not in columns:
        session.connection().execute(
            text(
                "ALTER TABLE device ADD COLUMN device_model VARCHAR "
                f"NOT NULL DEFAULT '{DEFAULT_DEVICE_MODEL}'"
            )
        )
        session.flush()

    devices = session.exec(select(Device)).all()
    for device in devices:
        model_id = (device.device_model or "").strip() or DEFAULT_DEVICE_MODEL
        try:
            model = get_device_model(model_id)
        except ValueError as exc:
            raise RuntimeError(
                f"Migration aborted: device id={device.id} has unknown "
                f"device_model '{device.device_model}'"
            ) from exc

        credential = session.get(ApiCredential, device.api_credential_id)
        if credential is None:
            raise RuntimeError(
                f"Migration aborted: device id={device.id} has no API credential"
            )
        if model.vendor_id != credential.vendor:
            raise RuntimeError(
                f"Migration aborted: device id={device.id} model '{model.id}' "
                f"belongs to vendor '{model.vendor_id}' but credential vendor is "
                f"'{credential.vendor}'"
            )

        device.device_model = model.id
        if not model.supports_battery_overlay:
            device.show_battery_icon = False
            device.show_battery_percentage = False
        session.add(device)


def init_db():
    """Create the current database schema and run additive migrations."""
    SQLModel.metadata.create_all(engine)
    from web.backend.status_worker import ensure_all_status_records

    with Session(engine) as session:
        try:
            migrate_schema(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        ensure_all_status_records(session)


def get_session():
    """Dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
