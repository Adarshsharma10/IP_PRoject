from __future__ import annotations

from .config import PROJECT_ROOT
from .db import init_db
from .ui import run


def main() -> None:
    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    init_db()
    run()


if __name__ == "__main__":
    main()
