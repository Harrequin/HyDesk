"""Application composition root.

``AppContext`` is the single place services are constructed and wired to
their shared dependencies: one engine, one audit repository, one clock.
The entry point builds it at startup and the GUI (added later) receives it
as its one handle to the application's use cases, so no view ever
constructs a service or touches the database directly.

Keeping construction here also makes wiring testable: a test can build an
AppContext around an in-memory engine (and an injected clock) and exercise
the services exactly as the real application does.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Engine

from .config import Config
from .repositories import (
    DeskRepository,
    IncomingRepository,
    StockRepository,
)
from .repositories.audit_repo import AuditRepository
from .services import (
    DeskDashboardService,
    DeskService,
    IncomingService,
    StockDashboardService,
    StockService,
)


class AppContext:
    """Owns the engine and the fully-wired service layer."""

    def __init__(
        self,
        engine: Engine,
        config: Config | None = None,
        *,
        clock=None,
    ) -> None:
        self.engine = engine
        self.config = config
        self._clock = clock or (lambda: datetime.now(timezone.utc))

        # Shared repositories (stateless; safe to share across services).
        self._desk_repo = DeskRepository()
        self._stock_repo = StockRepository()
        self._incoming_repo = IncomingRepository()
        self._audit_repo = AuditRepository()

        # Services, each given the shared engine, repositories and clock so
        # the audit trail and timestamps are consistent across the app.
        self.desks = DeskService(
            engine, self._desk_repo, self._audit_repo, clock=self._clock
        )
        self.desk_dashboard = DeskDashboardService(engine)
        self.stock = StockService(
            engine, self._stock_repo, self._audit_repo, clock=self._clock
        )
        self.incoming = IncomingService(
            engine,
            self._incoming_repo,
            self._stock_repo,
            self._audit_repo,
            clock=self._clock,
        )
        self.stock_dashboard = StockDashboardService(engine)

    @property
    def audit(self) -> AuditRepository:
        """The shared audit repository (for read-only audit queries)."""
        return self._audit_repo
