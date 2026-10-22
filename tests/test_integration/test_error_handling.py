"""Error-handling consistency tests.

The GUI will catch the typed HyDeskError hierarchy to show friendly
messages. These tests assert the service layer uses that hierarchy (not
bare exceptions) across the user-correctable failure paths, and that
ValidationError / NotFoundError / ConflictError are all subclasses of
HyDeskError so a single except clause can cover them.
"""

from __future__ import annotations

import pytest

from hydesk.app_context import AppContext
from hydesk.errors import (
    ConflictError,
    HyDeskError,
    NotFoundError,
    ValidationError,
)
from hydesk.models import DeskStatus


def test_hierarchy_is_coherent():
    assert issubclass(ValidationError, HyDeskError)
    assert issubclass(NotFoundError, HyDeskError)
    assert issubclass(ConflictError, HyDeskError)


def test_desk_errors_are_hydesk_errors(context: AppContext):
    with pytest.raises(HyDeskError):
        context.desks.change_status(999999, DeskStatus.DOWN, "Eng")  # NotFound
    with pytest.raises(HyDeskError):
        context.desks.change_status(
            context.desks.get_desk_by_identifier("4-001").id,
            DeskStatus.DOWN,
            "",  # blank engineer -> Validation
        )


def test_stock_errors_are_hydesk_errors(context: AppContext):
    with pytest.raises(HyDeskError):
        context.stock.get_item(999999)  # NotFound
    with pytest.raises(HyDeskError):
        context.stock.create_item("", "x", "Eng")  # Validation


def test_incoming_errors_are_hydesk_errors(context: AppContext):
    item = context.stock.create_item("Cat", "Item", "Eng")
    delivery = context.incoming.record_expected(item.id, 5, "Eng")
    context.incoming.receive_delivery(delivery.id, 5, "Eng")
    with pytest.raises(HyDeskError):
        context.incoming.receive_delivery(delivery.id, 1, "Eng")  # Conflict


def test_specific_types_still_distinguishable(context: AppContext):
    """A caller that wants to can still tell the error types apart."""
    with pytest.raises(NotFoundError):
        context.stock.get_item(999999)
    with pytest.raises(ValidationError):
        context.stock.create_item("", "x", "Eng")
