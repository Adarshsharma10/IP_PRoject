# College Academic Record & Performance Analysis System (CARPAS)
Desktop-based college academic record management and performance analysis system built with **Python (Tkinter)** and **SQL (via SQLAlchemy)**.

## Features
- Student management (add/update/delete)
- Course management (add/update/delete)
- Enrollment management (enroll/remove)
- Attendance management (store total classes + attended classes per enrollment)
- Marks management (multiple assessments per enrollment)
- Performance analysis
  - Attendance percentage
  - Marks percentage
  - Course class averages
  - At-risk list (low attendance / low marks)

## Tech stack
- Python 3.10+ (works with Python 3.13)
- Tkinter (built into standard Python on Windows)
- SQLAlchemy ORM
- SQLite by default (file DB in `data/carpas.db`)
- Optional: MySQL / PostgreSQL via SQLAlchemy drivers

## Project structure
- `main.py` – entrypoint
- `carpas/` – application package
  - `config.py` – environment/config loader
  - `models.py` – database models
  - `db.py` – engine/session and DB init
  - `services.py` – CRUD + analysis logic
  - `ui/` – Tkinter UI
- `data/` – local database folder (SQLite file is gitignored)

## Setup (Windows PowerShell)
1) Create a virtual environment:
```powershell
py -m venv .venv
```

2) Install dependencies:
```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

3) (Optional) Configure environment variables:
- Copy `.env.example` to `.env`
- Set `CARPAS_DATABASE_URL` if you want MySQL/PostgreSQL

4) (Optional) Seed synthetic/demo data (for screenshots/viva):
```powershell
.\.venv\Scripts\python -m carpas.seed
```
To delete existing data and reseed (dangerous):
```powershell
.\.venv\Scripts\python -m carpas.seed --reset
```

5) Run the app:
```powershell
.\.venv\Scripts\python main.py
```
Alternative:
```powershell
.\.venv\Scripts\python -m carpas
```

## Database configuration
By default, the app uses SQLite:
- `sqlite:///data/carpas.db`

To use MySQL (requires a MySQL server running):
- `mysql+pymysql://username:password@localhost:3306/carpas`

To use PostgreSQL (requires a PostgreSQL server running):
- `postgresql+pg8000://username:password@localhost:5432/carpas`

Set one of these in `.env` as:
- `CARPAS_DATABASE_URL=...`

## Notes / Troubleshooting
- If you get an error about `tkinter`, reinstall Python with **Tcl/Tk** support enabled.
- The SQLite database file is created automatically on first run.

## Future work ideas
- Export reports to PDF
- Advanced graphical reports (charts)
- Role-based login (admin/operator)
