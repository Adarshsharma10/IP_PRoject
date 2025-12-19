# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## What this repo is
CARPAS is a desktop application for managing college academic records and generating basic performance analytics.

- UI: Tkinter desktop app (+ embedded Matplotlib charts)
- Persistence: SQLAlchemy ORM
- Default DB: SQLite file at `data/carpas.db` (created on first run)

## Common commands (Windows)
All commands assume you are in the repo root.

### Environment setup
Create venv:
```powershell
py -m venv .venv
```
Install deps:
```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### Run the app
Primary entrypoint:
```powershell
.\.venv\Scripts\python main.py
```
Alternative module entrypoint (same behavior):
```powershell
.\.venv\Scripts\python -m carpas
```

### Seed demo data
Seed deterministic demo data into the configured database:
```powershell
.\.venv\Scripts\python -m carpas.seed
```
Reset (drops all tables) and reseed:
```powershell
.\.venv\Scripts\python -m carpas.seed --reset
```

### “Lint” / “tests”
This repo currently does not include a configured linter/formatter (no `pyproject.toml`, `ruff.toml`, etc.) and does not include an automated test suite (no `tests/` or `pytest`/`unittest` config found).

If you need a quick sanity check after edits, a lightweight option is:
```powershell
.\.venv\Scripts\python -m compileall .
```

## Configuration and runtime behavior
- Optional env file: `.env` at repo root (see `.env.example`). Loaded by `carpas/config.py`.
- Key settings:
  - `CARPAS_DATABASE_URL`: SQLAlchemy URL. Defaults to SQLite at `data/carpas.db`.
  - `CARPAS_SQL_ECHO`: set to `1`/`true` to enable SQLAlchemy echo logging.
  - `CARPAS_APP_TITLE`: window title.

## High-level architecture (big picture)
### Entry + startup
- `main.py` and `carpas/__main__.py` are thin wrappers that:
  1) create the `data/` directory (for the default SQLite path)
  2) call `carpas/db.py:init_db()`
  3) start the UI via `carpas/ui/app.py:run()`

### Configuration
- `carpas/config.py`
  - Defines `PROJECT_ROOT` and loads `.env` from the repo root.
  - Builds `DATABASE_URL` (defaults to SQLite file under `data/`).

### Database layer
- `carpas/models.py`
  - SQLAlchemy models:
    - `Student`
    - `Course`
    - `Enrollment` (unique on student/course)
    - `Attendance` (1:1 with Enrollment)
    - `Mark` (many per Enrollment)
- `carpas/db.py`
  - Creates the SQLAlchemy engine + `SessionLocal`.
  - Enforces SQLite foreign keys via a connect event.
  - Exposes `session_scope()` context manager (unit-of-work style: commit on success, rollback on error).

### Domain/service layer (CRUD + analytics)
- `carpas/services.py`
  - Pure(ish) functions that accept a SQLAlchemy `Session` and perform:
    - CRUD for students/courses
    - Enrollment management
    - Attendance and marks updates
    - Analytics:
      - per-student enrollment summaries (attendance% + marks%)
      - course-level averages (computed in SQL)
      - “at risk” detection (computed in Python)
  - Raises `ServiceError` for user-facing/validation errors; the UI catches these and shows message boxes.

### UI layer
- `carpas/ui/app.py`
  - `CarpasApp` is the Tk root window.
  - Uses a `ttk.Notebook` with separate tabs (Students/Courses/Enrollments/Attendance/Marks/Analysis).
  - Each user action opens a `session_scope()` and delegates to `carpas/services.py`.
  - Analysis tab embeds Matplotlib plots and uses service-layer analytics.

### Demo data
- `carpas/seed.py`
  - Idempotent seeding of demo students/courses/enrollments.
  - Can optionally `--reset` to drop all tables first.

## Where to look when changing behavior
- DB schema changes: `carpas/models.py` (+ consider seed impacts in `carpas/seed.py`)
- Validation or business rules: `carpas/services.py`
- UI interactions/layout: `carpas/ui/app.py`
- DB connection issues / engine config: `carpas/config.py` and `carpas/db.py`
