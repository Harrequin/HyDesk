"""Tests for DeskService: updates, history, audit, validation, rollback."""

from __future__ import annotations

import pytest

from hydesk.errors import NotFoundError, ValidationError
from hydesk.models import DeskStatus
from hydesk.repositories.audit_repo import AuditRepository
from hydesk.services.desk_service import DeskService, validate_halo_ticket


@pytest.fixture()
def service(seeded_engine, fixed_clock) -> DeskService:
    return DeskService(seeded_engine, clock=fixed_clock)


# ---- Halo validation -----------------------------------------------------

@pytest.mark.parametrize("value", ["1234567", " 1234567 ", "0000000"])
def test_valid_halo_tickets(value):
    assert validate_halo_ticket(value) == value.strip()


@pytest.mark.parametrize("value", ["123456", "12345678", "12a4567", "abcdefg", "123 567"])
def test_invalid_halo_tickets(value):
    with pytest.raises(ValidationError):
        validate_halo_ticket(value)


def test_empty_halo_is_none():
    assert validate_halo_ticket(None) is None
    assert validate_halo_ticket("") is None
    assert validate_halo_ticket("   ") is None


# ---- status changes ------------------------------------------------------

def test_change_status_updates_desk_and_stamps_engineer(service):
    desk = service.get_desk_by_identifier("4-001")
    updated = service.change_status(desk.id, DeskStatus.DOWN, "A. Engineer")

    assert updated.status is DeskStatus.DOWN
    assert updated.last_engineer == "A. Engineer"
    assert updated.last_updated is not None


def test_change_status_writes_history(service):
    desk = service.get_desk_by_identifier("4-002")
    service.change_status(desk.id, DeskStatus.IN_REPAIR, "Eng", history_note="PSU swap")

    history = service.view_history(desk.id)
    assert len(history) == 1
    assert history[0].previous_status is DeskStatus.ACTIVE
    assert history[0].new_status is DeskStatus.IN_REPAIR
    assert history[0].engineer == "Eng"
    assert history[0].notes == "PSU swap"


def test_change_status_writes_audit(service, seeded_engine):
    desk = service.get_desk_by_identifier("4-003")
    service.change_status(desk.id, DeskStatus.DOWN, "Eng")

    audit = AuditRepository()
    with seeded_engine.connect() as conn:
        entries = audit.for_entity(conn, "desk", desk.id)
    assert len(entries) == 1
    assert entries[0].field_changed == "status"
    assert entries[0].previous_value == "ACTIVE"
    assert entries[0].new_value == "DOWN"


def test_history_is_retained_across_multiple_changes(service):
    desk = service.get_desk_by_identifier("4-004")
    service.change_status(desk.id, DeskStatus.DOWN, "Eng")
    service.change_status(desk.id, DeskStatus.IN_REPAIR, "Eng")
    service.change_status(desk.id, DeskStatus.ACTIVE, "Eng")

    history = service.view_history(desk.id)
    assert len(history) == 3  # nothing overwritten


# ---- notes and halo ------------------------------------------------------

def test_update_notes(service):
    desk = service.get_desk_by_identifier("4-005")
    updated = service.update_desk(
        desk.id, "Eng", notes="Keyboard replaced", update_notes=True
    )
    assert updated.notes == "Keyboard replaced"


def test_associate_valid_halo_ticket(service):
    desk = service.get_desk_by_identifier("4-006")
    updated = service.update_desk(
        desk.id, "Eng", halo_ticket="1234567", update_halo=True
    )
    assert updated.halo_ticket == "1234567"


def test_invalid_halo_ticket_rejected_by_service(service):
    desk = service.get_desk_by_identifier("4-007")
    with pytest.raises(ValidationError):
        service.update_desk(desk.id, "Eng", halo_ticket="99", update_halo=True)


# ---- validation and integrity -------------------------------------------

def test_update_requires_engineer(service):
    desk = service.get_desk_by_identifier("4-008")
    with pytest.raises(ValidationError):
        service.change_status(desk.id, DeskStatus.DOWN, "   ")


def test_update_requires_some_change(service):
    desk = service.get_desk_by_identifier("4-009")
    with pytest.raises(ValidationError):
        service.update_desk(desk.id, "Eng")  # nothing to change


def test_update_missing_desk_raises(service):
    with pytest.raises(NotFoundError):
        service.change_status(999999, DeskStatus.DOWN, "Eng")


def test_rollback_on_invalid_halo_leaves_no_changes(service):
    """An invalid Halo in a combined update must roll back everything."""
    desk = service.get_desk_by_identifier("4-010")
    with pytest.raises(ValidationError):
        service.update_desk(
            desk.id,
            "Eng",
            status=DeskStatus.DOWN,
            halo_ticket="bad",
            update_halo=True,
        )

    # Status unchanged, no history, no audit - validation happens first.
    reloaded = service.get_desk(desk.id)
    assert reloaded.status is DeskStatus.ACTIVE
    assert service.view_history(desk.id) == []
