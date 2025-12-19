from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_URL, SQL_ECHO
from .models import Base

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    # Ensure SQLite enforces foreign keys.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """Create tables if they don't exist.

    Notes:
    - `create_all()` does not apply migrations. If the DB was created before some constraints
      existed, duplicates may already exist. We run a small cleanup step to merge/remove
      duplicates for core entities (students/courses/enrollments).
    """
    Base.metadata.create_all(engine)

    # Best-effort cleanup of historical duplicates (especially common with old SQLite files).
    # Safe to run on every startup; it only acts when duplicates are detected.
    from .maintenance import cleanup_duplicates, ensure_sqlite_unique_indexes

    with session_scope() as session:
        cleanup_duplicates(session)
        ensure_sqlite_unique_indexes(session)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
