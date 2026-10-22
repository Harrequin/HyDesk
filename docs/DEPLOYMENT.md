# HyDesk Deployment & Operations Guide

This guide covers installing, configuring, operating and maintaining HyDesk
for local desktop deployment, plus the path toward future centralised
(PostgreSQL) deployment.

Contents:

1. [Overview](#1-overview)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Database location](#4-database-location)
5. [Database initialisation](#5-database-initialisation)
6. [Backup and restore](#6-backup-and-restore)
7. [Application updates](#7-application-updates)
8. [Logging](#8-logging)
9. [Troubleshooting](#9-troubleshooting)
10. [Future: PostgreSQL / central database](#10-future-postgresql--central-database)

---

## 1. Overview

HyDesk is a Python desktop application (PySide6) with a layered architecture:

```
Presentation (PySide6)  ->  Services  ->  Domain models  ->  Repositories  ->  Database
```

- **Data** (the SQLite database and log files) is stored in a per-user data
  directory **outside** the installation folder, so reinstalling or updating
  the application never risks the data.
- **Schema** is versioned with Alembic and migrated automatically on startup.
- The business logic contains no SQLite-specific code, so moving to a central
  SQL database later does not require rewriting it.

There are two ways to run HyDesk:

- **Packaged executable** (`HyDesk.exe`) — for end users. No Python needed.
- **From source** (`python -m hydesk`) — for developers and for building the
  executable.

---

## 2. Installation

### 2.1 End users (packaged executable)

1. Obtain the `HyDesk` distribution folder (produced by the build in §7.3).
2. Copy the whole `HyDesk\` folder to a stable location, e.g.
   `C:\Program Files\HyDesk\` or `%LOCALAPPDATA%\Programs\HyDesk\`.
3. Launch `HyDesk.exe`.

On first launch the application creates its data directory, builds the
database schema and seeds the 280 Park Street desks automatically (see §5).

> The distribution is a one-folder build: `HyDesk.exe` sits beside an
> `_internal\` folder containing the runtime. Keep them together; move the
> folder, not just the exe.

### 2.2 Developers (from source)

Prerequisites: [`uv`](https://docs.astral.sh/uv/) (which can also install
Python).

```powershell
# From the project root:
uv venv --python 3.12
uv pip install -e ".[dev]"      # app + dev tools (pytest, pytest-qt, pyinstaller)

# Run from source:
.\.venv\Scripts\python.exe -m hydesk
```

> **Do not install the project inside a OneDrive-synced folder.** OneDrive's
> background file locking causes intermittent install and build failures. Use
> a local path such as `C:\dev\HyDesk`. See `MIGRATION.md` for details.

---

## 3. Configuration

Configuration is layered. Later sources override earlier ones:

1. **Shipped defaults** — `config/default.toml`, bundled with the app.
2. **User override** — an optional `config.toml` placed in the data directory
   (see §4). Only the keys you want to change need to be present.

### 3.1 Settings

| Section     | Key                 | Default                 | Meaning |
|-------------|---------------------|-------------------------|---------|
| `database`  | `filename`          | `hydesk.db`             | Database file name (within the data directory). |
| `database`  | `path`              | `""` (empty)            | Absolute path to the database file. If set, overrides the data-directory location entirely. |
| `logging`   | `level`             | `INFO`                  | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `logging`   | `filename`          | `hydesk.log`            | Log file name (within the data directory). |
| `logging`   | `max_bytes`         | `1048576` (1 MiB)       | Size at which a log file rotates. |
| `logging`   | `backup_count`      | `5`                     | Number of rotated log files kept. |
| `ui`        | `default_page_size` | `50`                    | Default rows per page in listings. |
| `ui`        | `page_size_options` | `[25, 50, 100, 200]`    | Page-size choices offered in the UI. |

### 3.2 Example user override

Create `%LOCALAPPDATA%\HyDesk\config.toml`:

```toml
[logging]
level = "DEBUG"

[ui]
default_page_size = 100
```

This raises the log level and default page size while leaving everything else
at its default. Restart the application for changes to take effect.

---

## 4. Database location

By default the database and logs live in the per-user data directory:

- **Windows:** `%LOCALAPPDATA%\HyDesk\`
  (typically `C:\Users\<you>\AppData\Local\HyDesk\`)

So, by default:

- Database: `%LOCALAPPDATA%\HyDesk\hydesk.db`
- Log file: `%LOCALAPPDATA%\HyDesk\hydesk.log`

This directory is deliberately **outside** the installation folder so that
reinstalling or updating the application never touches the data.

To store the database elsewhere (e.g. a backed-up network drive for a single
user), set an absolute `database.path` in the user `config.toml`:

```toml
[database]
path = "D:/HyDeskData/hydesk.db"
```

> Use forward slashes or escaped backslashes in TOML. The parent directory
> must exist.

---

## 5. Database initialisation

Initialisation is automatic and idempotent. On every startup HyDesk:

1. Ensures the data directory exists.
2. Runs Alembic migrations up to the latest revision (creating the schema on a
   fresh database).
3. Seeds the 280 Park Street desks **if the desks table is empty** (150 on the
   4th floor, `4-001`..`4-150`; 130 on the 5th, `5-001`..`5-130`).

Subsequent launches apply any new migrations and leave existing data intact.

To initialise (or verify) without opening the GUI — useful for a scripted
first-run or a health check:

```powershell
.\.venv\Scripts\python.exe -m hydesk --no-gui
```

Expected output ends with `HyDesk initialised successfully (no GUI).` and the
resolved database path.

---

## 6. Backup and restore

The entire application state is a single SQLite file. Back it up by copying
that file while the application is **closed** (or at least idle).

### 6.1 Backup

```powershell
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "$env:LOCALAPPDATA\HyDesk\hydesk.db" "$env:LOCALAPPDATA\HyDesk\backups\hydesk_$stamp.db"
```

Create the `backups` folder first if it does not exist. Schedule this via
Windows Task Scheduler for regular backups. Because all history (desk history,
stock movements, incoming deliveries, audit log) lives in the same file, a
single copy captures the complete audit trail.

### 6.2 Restore

1. Close HyDesk.
2. Replace the live database with a backup copy:
   ```powershell
   Copy-Item "$env:LOCALAPPDATA\HyDesk\backups\hydesk_<stamp>.db" "$env:LOCALAPPDATA\HyDesk\hydesk.db" -Force
   ```
3. Relaunch. On startup, migrations will bring an older backup up to the
   current schema automatically if needed.

> Keep backups off the machine (network share or cloud) for disaster recovery.
> Avoid storing the **live** database on OneDrive — sync locking can corrupt an
> open SQLite file. Backups copied to OneDrive are fine.

---

## 7. Application updates

### 7.1 Updating the packaged executable

1. Close HyDesk.
2. Replace the old `HyDesk\` distribution folder with the new one.
3. Relaunch. The data directory is untouched; any schema changes in the new
   version are applied automatically on startup.

Because data lives outside the install folder, updates never risk the data.

### 7.2 Updating from source

```powershell
git pull
uv pip install -e ".[dev]"     # pick up any dependency changes
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m hydesk
```

### 7.3 Building the executable (PyInstaller)

```powershell
.\.venv\Scripts\python.exe -m PyInstaller hydesk.spec --noconfirm --clean
```

Output: `dist\HyDesk\HyDesk.exe` plus its `_internal\` folder. The spec bundles
`config/default.toml`, the `migrations/` tree, `alembic.ini`, and
`src/hydesk/ui/assets/`; the frozen app locates them via
`src/hydesk/resources.py` (which handles both source and frozen layouts).

### 7.4 Databases created before Alembic was introduced

Early development databases were created directly from the schema and lack
Alembic's `alembic_version` table, so a migration run would try to re-create
existing tables and fail. If you encounter such a database, stamp it once so
Alembic treats it as already at the baseline revision:

```powershell
.\.venv\Scripts\python.exe -m alembic -x db_url="sqlite:///C:/path/to/hydesk.db" stamp 0001
```

After stamping, normal startup migrations work. New databases never need this.

---

## 8. Logging

- Logs are written to `%LOCALAPPDATA%\HyDesk\hydesk.log` and echoed to the
  console when run from source.
- Format: `timestamp | LEVEL | logger | message` with ISO-8601 timestamps.
- Files rotate at `logging.max_bytes` (1 MiB default), keeping
  `logging.backup_count` (5 default) rotated files: `hydesk.log`,
  `hydesk.log.1`, … `hydesk.log.5`.
- Raise detail by setting `logging.level = "DEBUG"` in the user `config.toml`
  (§3.2) when diagnosing an issue, then revert to `INFO`.

When reporting a problem, include the relevant tail of `hydesk.log`.

---

## 9. Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| App won't start; log mentions a migration/schema error | Database predates Alembic, or is from a newer app version | Stamp a pre-Alembic DB (§7.4); do not downgrade the app against a newer DB. Restore a compatible backup if needed. |
| `os error 396` / hardlink failure during `uv pip install` | Project is in a OneDrive-synced folder | Move the project to a local path (see `MIGRATION.md`); or set `UV_LINK_MODE=copy` as a stopgap. |
| Build or install hangs / files locked | OneDrive sync holding file handles | Move off OneDrive; pause OneDrive while building. |
| Database "locked" errors at runtime | The DB file is on OneDrive or a network share being synced, or two instances are open | Keep the live DB on a local disk; run a single instance. |
| GUI fails to launch from the exe with an import error | Stale/old build | Rebuild with `--clean` (§7.3). |
| Changes to `config.toml` have no effect | Edited the wrong file, or app not restarted | Edit `%LOCALAPPDATA%\HyDesk\config.toml` (not the bundled `default.toml`); restart. |
| Need to confirm the data location | — | Run `python -m hydesk --no-gui`; it prints the resolved database path. |

### Resetting to a clean database (destructive)

Deleting the database discards **all** desk history, stock, movements and
audit data. Back it up first. With HyDesk closed:

```powershell
Remove-Item "$env:LOCALAPPDATA\HyDesk\hydesk.db"
```

The next launch recreates and reseeds a fresh database.

---

## 10. Future: PostgreSQL / central database

HyDesk was built for a future move to a centrally hosted SQL database without
rewriting business logic:

- Repositories use **SQLAlchemy Core** with no SQLite-specific SQL; timestamps
  are stored as portable ISO-8601 text.
- The database URL is resolved centrally from configuration, and Alembic reads
  the same URL, so pointing at PostgreSQL is a configuration change plus a
  migration run — not a code change.

Indicative steps when the time comes (not part of the current release):

1. Provision a PostgreSQL database and add the driver dependency
   (e.g. `psycopg`).
2. Supply the PostgreSQL URL via configuration (a future `database.url`
   setting or environment variable), rather than the SQLite file path.
3. Run `alembic upgrade head` against the new database to build the schema.
4. Migrate existing data if required (export/import), then run multiple
   clients against the shared database.

Multi-user concerns (concurrent-edit policies, authentication, and an optional
API layer) are deliberately out of scope for the initial local release and
would be designed alongside the central-database rollout.
