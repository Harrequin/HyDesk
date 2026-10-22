"""Data-access repositories.

Repositories are the only layer that emits SQL. They translate between
database rows and domain models, keeping the service layer and GUI free of
any database-specific knowledge.
"""

from .base import Page, PageRequest
from .desk_repo import DeskQuery, DeskRepository, DeskSort
from .stock_repo import StockQuery, StockRepository, StockSort
from .incoming_repo import IncomingRepository

__all__ = [
    "Page",
    "PageRequest",
    "DeskQuery",
    "DeskRepository",
    "DeskSort",
    "StockQuery",
    "StockRepository",
    "StockSort",
    "IncomingRepository",
]
