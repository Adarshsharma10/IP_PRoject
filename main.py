from __future__ import annotations

from carpas.config import PROJECT_ROOT
from carpas.db import init_db
from carpas.ui import run


def main() -> None:
    # Ensure local data directory exists for SQLite default.
    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)

    init_db()
    run()


if __name__ == "__main__":
    main()
