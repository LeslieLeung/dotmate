import os
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

from web.backend import models as _models  # noqa: F401 - registers SQLModel tables

DB_PATH = os.environ.get("DOTMATE_DB_PATH", str(Path("data") / "dotmate.db"))

# Ensure the parent directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    """Create the current database schema."""
    SQLModel.metadata.create_all(engine)
    # Backfill one status row per existing device. The status table is additive,
    # so existing installations need no ALTER TABLE migration.
    from web.backend.status_worker import ensure_all_status_records

    with Session(engine) as session:
        ensure_all_status_records(session)


def get_session():
    """Dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
