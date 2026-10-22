# PyInstaller spec for HyDesk.
#
# Bundles the application plus the data files that must exist at runtime:
#   - config/default.toml        (shipped default configuration)
#   - migrations/ + alembic.ini  (Alembic needs these to migrate on startup)
#   - src/hydesk/ui/assets/       (brand logo/font, picked up by theme.py)
#
# Build:   pyinstaller hydesk.spec
# Output:  dist/HyDesk/HyDesk.exe   (one-folder build)
#
# A one-folder build is used (not --onefile) so startup is fast and the
# bundled migrations/config are easy to inspect. Switch to onefile later if
# a single artefact is preferred for distribution.

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    ("config/default.toml", "config"),
    ("alembic.ini", "."),
    ("migrations", "migrations"),
    ("src/hydesk/ui/assets", "hydesk/ui/assets"),
]

# Alembic loads parts of itself dynamically. Collect its submodules so the
# runtime migration path works, but exclude the test-only ``alembic.testing``
# package: it imports optional test dependencies and raises during analysis,
# and it is never used at runtime.
hiddenimports = [
    m for m in collect_submodules("alembic")
    if not m.startswith("alembic.testing")
]

a = Analysis(
    ["run_hydesk.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HyDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HyDesk",
)
