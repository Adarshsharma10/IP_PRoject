from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load optional .env from project root
load_dotenv(PROJECT_ROOT / ".env", override=False)

APP_TITLE: str = os.getenv(
    "CARPAS_APP_TITLE", "College Academic Record & Performance Analysis System"
)

# Default to a local SQLite database file in ./data
_default_sqlite_path = (PROJECT_ROOT / "data" / "carpas.db").as_posix()
DATABASE_URL: str = os.getenv("CARPAS_DATABASE_URL", f"sqlite:///{_default_sqlite_path}")

SQL_ECHO: bool = os.getenv("CARPAS_SQL_ECHO", "0").strip().lower() in {"1", "true", "yes"}
