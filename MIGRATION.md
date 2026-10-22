# Migrating HyDesk off OneDrive to a local disk

OneDrive's background sync intermittently locks files, which has caused
package-install failures (`os error 396`), build file-locks, and torn-down
PyInstaller runs. Moving the project to a local, non-synced path removes
this whole class of problem.

The golden rule: **move the git-tracked source, never the `.venv`, `build`
or `dist` folders.** Those are rebuilt at the destination.

Suggested destination: `C:\dev\HyDesk` (any local, non-OneDrive path works).

---

## Option A — Clone from git (recommended)

The repo is already initialised and committed, so git gives you a perfect
filter: it carries exactly the source and nothing ignored.

```powershell
# 1. Create the destination parent and clone the working copy into it.
New-Item -ItemType Directory -Force -Path C:\dev | Out-Null
git clone "C:\Users\JS131\OneDrive - Hyde Housing Association\Documents\python_scripts\HyDesk" C:\dev\HyDesk

# 2. Move into the new location.
Set-Location C:\dev\HyDesk

# 3. Recreate the virtual environment (do NOT copy the old one).
uv venv --python 3.12
uv pip install -e ".[dev]"     # app + dev tools (pytest, pytest-qt, pyinstaller)

# 4. Verify the backend.
.\.venv\Scripts\python.exe -m pytest -q          # expect: 126 passed

# 5. Verify the app boots (initialises DB + migrations, no GUI).
.\.venv\Scripts\python.exe -m hydesk --no-gui    # expect: "initialised successfully"

# 6. Launch the GUI to eyeball it.
.\.venv\Scripts\python.exe -m hydesk
```

> On a local disk you no longer need `UV_LINK_MODE=copy`. If you ever see a
> hardlink error again, set it, but it should not recur off OneDrive.

---

## Option B — Plain copy (if you prefer not to use git clone)

```powershell
# Copy source only. Exclude the folders that must be rebuilt.
$src = "C:\Users\JS131\OneDrive - Hyde Housing Association\Documents\python_scripts\HyDesk"
$dst = "C:\dev\HyDesk"
robocopy $src $dst /E /XD .venv build dist .pytest_cache __pycache__ .git
# Then follow steps 2-6 from Option A (recreate venv, install, verify).
```

(Git history is not carried in Option B. Option A is preferable.)

---

## Rebuild the packaged executable (Phase 6)

Once the venv is recreated at the local path:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller hydesk.spec --noconfirm --clean
.\dist\HyDesk\HyDesk.exe
```

The spec bundles `config/default.toml`, the `migrations/` tree, `alembic.ini`
and `ui/assets/`; the frozen app resolves them via `src/hydesk/resources.py`.

---

## What stays where it is

- **The application database** lives at `%LOCALAPPDATA%\HyDesk\hydesk.db`,
  already off OneDrive. It is found via configuration, not the project path,
  so it keeps working after the move with no action needed.
- **Logs** live beside it in `%LOCALAPPDATA%\HyDesk`.

## Post-move sanity checks

| Check | Command | Expected |
|---|---|---|
| Python resolves | `uv run python --version` | Python 3.12.x |
| Tests pass | `pytest -q` | 126 passed |
| App initialises | `python -m hydesk --no-gui` | "initialised successfully" |
| Build works | `pyinstaller hydesk.spec --noconfirm` | `dist\HyDesk\HyDesk.exe` created |

## After you confirm the move is good

Once the local copy passes the checks above, you can delete (or leave
archived) the OneDrive copy. Nothing depends on it.
