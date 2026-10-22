"""Per-session UI state.

The initial release has no authentication; the acting engineer is entered
per action. To avoid retyping, the last-used name is remembered for the
lifetime of the window and pre-filled into prompts.
"""

from __future__ import annotations


class Session:
    """Holds transient UI state shared across views."""

    def __init__(self) -> None:
        self._engineer: str = ""

    @property
    def engineer(self) -> str:
        return self._engineer

    def remember_engineer(self, name: str) -> None:
        cleaned = (name or "").strip()
        if cleaned:
            self._engineer = cleaned
