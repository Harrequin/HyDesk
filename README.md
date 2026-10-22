# HyDesk

Internal IT operations desktop application for managing Park Street desk
infrastructure and departmental IT stock.

> Status: **MVP feature-complete.** Foundation, desk and stock management,
> integration & QA, and the PySide6 GUI are all in place. Remaining:
> packaging/deployment docs (Phase 6) and brand assets (logo + font).

## Architecture

Layered, with dependencies pointing one direction only:

```
Presentation (PySide6)  ->  Services  ->  Domain Models  ->  Repositories  ->  Database
```

- **Domain models** (`src/hydesk/models`) are pure Python with no framework
  dependency.
- **Repositories** (`src/hydesk/repositories`) are the only layer that emits
  SQL, via SQLAlchemy Core, keeping business logic database-agnostic
  (SQLite now, PostgreSQL later).
- **Config and logging** are centralised (`config.py`, `logging_setup.py`).
- The **database and log files live outside the install directory**, in the
  per-user data directory (`%LOCALAPPDATA%\HyDesk` on Windows).

## Requirements

- Python 3.11+ (the project is developed and tested against 3.12).

## Setup

This project uses [`uv`](https://docs.astral.sh/uv/). If you don't have a
system Python, `uv` can install one:

```powershell
uv python install 3.12
uv venv --python 3.12
uv pip install -e ".[dev]"
```

> **OneDrive note:** if the project folder is inside OneDrive, set
> `UV_LINK_MODE=copy` before installing, otherwise package installation
> fails with a hardlink error (`os error 396`):
>
> ```powershell
> $env:UV_LINK_MODE = "copy"
> uv pip install -e ".[dev]"
> ```

## Running

```powershell
.\.venv\Scripts\python.exe -m hydesk
```

This launches the desktop GUI: a left-hand navigation between **Desks** and
**Stock**, each with its own dashboard, listing (search / filter / sort /
paginate) and editing. On first run it creates the SQLite database in the
per-user data directory, runs Alembic migrations to build the schema, and
seeds the 280 Park Street desks (150 on the 4th floor, 130 on the 5th). The
operation is idempotent — subsequent runs apply any pending migrations and
reuse the existing data.

To initialise the database without opening the GUI (e.g. a startup check):

```powershell
.\.venv\Scripts\python.exe -m hydesk --no-gui
```

### Brand assets (post-MVP)

Drop a logo and a font file into `src/hydesk/ui/assets/`. Any `.ttf`/`.otf`
there is picked up automatically as the application font (see
`ui/theme.py`); no code change is needed to switch the brand font.

## Database migrations

Schema changes are managed with Alembic. The application runs migrations
automatically on startup, but they can also be run manually:

```powershell
# Upgrade the application database to the latest revision
.\.venv\Scripts\python.exe -m alembic upgrade head

# Target a specific database (e.g. a throwaway copy)
.\.venv\Scripts\python.exe -m alembic -x db_url="sqlite:///C:/path/to/test.db" upgrade head

# After editing the Core schema, autogenerate a new revision
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"

# Confirm the migrations match the Core metadata (no drift)
.\.venv\Scripts\python.exe -m alembic check
```

The migration URL is resolved from the application config, so migrations
target the same database the app uses and the future PostgreSQL move needs
no change to the Alembic setup.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite runs against an in-memory SQLite database with foreign keys
enforced, so it is fast and isolated.

## Project layout

```
alembic.ini                Alembic configuration
config/default.toml        Shipped default configuration
migrations/                Alembic environment + versioned migrations
  env.py                   Resolves DB URL from app config
  versions/0001_*.py       Baseline schema (all six tables)
src/hydesk/
  __main__.py              Entry point: config -> logging -> migrate -> seed
  app_context.py           Composition root: wires engine + all services
  config.py                Centralised, typed configuration
  logging_setup.py         Rotating-file + console structured logging
  errors.py                Application exception hierarchy
  db/                       Engine, Core schema, bootstrap, migration runner
  models/                   Domain models (desks, stock, incoming, audit)
  repositories/             SQL-only data-access layer + pagination
  services/                 Business logic: desk, stock, incoming, dashboards
  ui/                       PySide6 GUI
    app.py                  QApplication launcher
    theme.py                Colours, spacing, brand-font hook, stylesheet
    main_window.py          Left-nav + stacked Desks/Stock sections
    session.py              Remembers the acting engineer for the session
    assets/                 Brand logo/font drop-in (post-MVP)
    common/                 Status badge, cards, table model, pagination
    desks/                  Dashboard, listing, detail/edit, history
    stock/                  Dashboard, items, movements, incoming deliveries
tests/
  test_config.py
  test_db/                  Schema, seed, repository, integrity, rollback
  test_desks/               Desk service + search/filter/sort
  test_stock/               Stock service, movements, incoming deliveries
  test_dashboards/          Desk and stock dashboard calculations
  test_integration/         Composition root, audit + data integrity, errors
```
