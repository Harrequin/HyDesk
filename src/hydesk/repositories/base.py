"""Shared repository primitives: pagination request/response types.

These small value objects keep pagination consistent across every listing
in the application and keep the SQL ``LIMIT/OFFSET`` details inside the
data-access layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    """A request for one page of results.

    ``page`` is 1-based. ``page_size`` is the configurable number of rows
    per page. A ``page_size`` of 0 or less means "no pagination" (return
    everything), which the repository honours by omitting LIMIT/OFFSET.
    """

    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            object.__setattr__(self, "page", 1)

    @property
    def paginated(self) -> bool:
        return self.page_size > 0

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size if self.paginated else 0

    @property
    def limit(self) -> int | None:
        return self.page_size if self.paginated else None


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of results plus the metadata needed to render pagination."""

    items: Sequence[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 1
        if self.total == 0:
            return 1
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1
