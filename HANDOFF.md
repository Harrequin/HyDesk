# HyDesk — Session Handoff

A short orientation for anyone (human or a fresh AI session) picking up this
project. For architecture and operations detail, read `README.md` and
`docs/DEPLOYMENT.md`; for the OneDrive move, see `MIGRATION.md`.

## Status: MVP complete

All six planned phases are delivered and the application runs end to end with
branding applied.

| Phase | Scope | State |
|---|---|---|
| 1 | Requirements & architecture | Delivered, reviewed |
| 2 | Foundation (config, logging, DB, models, repositories) | Done, tested |
| 3 | Desk management (repo, services, history, dashboard, search/sort/paginate) + Alembic | Done, tested |
| 4 | Stock management (items, movements, incoming deliveries, dashboard) | Done, tested |
| 5 | Integration & QA (composition root, audit/data-integrity, error handling) | Done, tested |
| 6 | Packaging (PyInstaller) & deployment docs | Done |
| — | Branding: Heebo font + slate/navy/stone palette, +35% font scale | Done |

**Tests: 126 passing.** Backend is covered thoroughly; the GUI is verified by
a headless construction smoke test and manual eyeballing.

## How to run

From the project root (local, non-OneDrive path — currently `C:\dev\HyDesk`):

```powershell
# One-time setup
uv venv --python 3.12
uv pip install -e ".[dev]"

# Run the GUI
.\.venv\Scripts\python.exe -m hydesk

# Run tests
.\.venv\Scripts\python.exe -m pytest -q          # expect 126 passed

# Initialise DB without GUI (health check)
.\.venv\Scripts\python.exe -m hydesk --no-gui

# Build the Windows executable
.\.venv\Scripts\python.exe -m PyInstaller hydesk.spec --noconfirm --clean
```

## Key facts to know

- **Architecture:** strict layering — Presentation (PySide6) → Services →
  Domain models → Repositories → Database. SQL lives only in repositories
  (SQLAlchemy Core, dialect-free). Business logic has no SQLite-specific code,
  so a future PostgreSQL move is a config + migration change, not a rewrite.
- **Composition root:** `src/hydesk/app_context.py` wires the engine and all
  services. The GUI receives one `AppContext` and never touches the DB
  directly.
- **Database & logs** live in `%LOCALAPPDATA%\HyDesk\` (outside the install
  dir). Schema is versioned with Alembic and migrated automatically on
  startup, then the 280 Park Street desks are seeded if absent.
- **Theming** is centralised in `src/hydesk/ui/theme.py`. Font scale is a
  single constant (`FONT_SCALE`). The brand font (`Heebo-Regular.ttf`) lives
  in `src/hydesk/ui/assets/` and is loaded by `apply_brand_font` so it ships
  with the app regardless of what is installed.
- **Desk status colours** (green/red/amber/blue) are semantic and live on the
  `DeskStatus` enum in `src/hydesk/models/desk.py` — deliberately NOT part of
  the brand palette, and mandated by the spec.

## Deferred / not yet done (by agreement, not gaps)

- **Brand logo** — not added. Branding is changing and the old logos were
  pulled from SharePoint. When the new logo is available, drop it into
  `src/hydesk/ui/assets/` and wire it into the header/nav (isolated change).
- **pytest-qt UI interaction tests** — the framework is installed via the
  `dev` extra but no widget-interaction tests are written yet. Backend is
  fully tested; UI is manual-verify for now.
- **GUI visual polish** — functional and branded; fine-tuning of spacing /
  layout can continue freely without touching the backend.

## Environment notes (learned the hard way)

- **Do not run the project from a OneDrive-synced folder.** OneDrive's
  background file locking caused install failures (`os error 396`), build
  file-locks and torn-down PyInstaller runs. The project now lives on a local
  disk. If a hardlink error ever recurs, set `UV_LINK_MODE=copy`.
- **Python/venv** are managed with `uv`. Never copy a `.venv` between
  locations — recreate it (`uv venv` + `uv pip install -e ".[dev]"`).
- Pre-Alembic databases need a one-time `alembic stamp 0001` (see
  `docs/DEPLOYMENT.md` §7.4). New databases do not.

## Git

Single `main` branch. History:

```
ee68f47  Scale app font +35% and embolden nav labels
93adb36  Apply brand theme: Heebo font + palette
968a1f7  Phase 6: deployment guide; mark MVP complete
f6895c9  Migration guide (off OneDrive)
88207bf  Initial commit: backend, GUI, packaging
```

No remote is configured yet. Adding a backup remote (GitHub / Azure DevOps /
network share) is recommended so the code is not only on one machine.
