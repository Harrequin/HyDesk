"""Frozen-app entry script for PyInstaller.

PyInstaller runs its entry script as a top-level module with no parent
package, so the package's own ``__main__.py`` (which uses relative imports)
cannot be the entry point. This thin launcher imports the package
absolutely and delegates to ``hydesk.__main__.main``.

In development the application is still run with ``python -m hydesk``; this
file exists only to give the packaged build a valid, import-safe entry
point.
"""

from __future__ import annotations

import sys

from hydesk.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
