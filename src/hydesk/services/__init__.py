"""Application service layer.

Services own business logic and transactions. They are GUI-free: every
method takes plain arguments (and the acting engineer, since there is no
authenticated user in the initial release) and returns domain models, so
they can be driven entirely from tests without a Qt event loop.
"""

from .desk_service import DeskService
from .dashboard_service import DeskDashboard, DeskDashboardService
from .stock_service import StockService
from .incoming_service import IncomingService
from .stock_dashboard_service import StockDashboard, StockDashboardService

__all__ = [
    "DeskService",
    "DeskDashboard",
    "DeskDashboardService",
    "StockService",
    "IncomingService",
    "StockDashboard",
    "StockDashboardService",
]
