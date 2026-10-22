"""Tests for desk search, filtering, sorting and paginated results."""

from __future__ import annotations

import pytest

from hydesk.models import DeskStatus
from hydesk.repositories import DeskQuery, PageRequest
from hydesk.repositories.desk_repo import DeskSort
from hydesk.services.desk_service import DeskService


@pytest.fixture()
def service(seeded_engine, fixed_clock) -> DeskService:
    svc = DeskService(seeded_engine, clock=fixed_clock)
    # Create a small, known spread of changes to search/filter against.
    svc.change_status(svc.get_desk_by_identifier("4-001").id, DeskStatus.DOWN, "Alice",
                      halo_ticket="1111111")
    svc.change_status(svc.get_desk_by_identifier("4-002").id, DeskStatus.IN_REPAIR, "Bob")
    svc.change_status(svc.get_desk_by_identifier("5-001").id, DeskStatus.DOWN, "Alice")
    svc.update_desk(svc.get_desk_by_identifier("5-002").id, "Carol",
                    notes="awaiting new monitor", update_notes=True)
    return svc


def test_filter_by_floor(service):
    page = service.search_desks(DeskQuery(floor=5), PageRequest(page_size=0))
    assert page.total == 130
    assert all(d.floor == 5 for d in page.items)


def test_filter_by_status(service):
    page = service.search_desks(
        DeskQuery(status=DeskStatus.DOWN), PageRequest(page_size=0)
    )
    assert page.total == 2
    assert {d.identifier for d in page.items} == {"4-001", "5-001"}


def test_filter_by_floor_and_status(service):
    page = service.search_desks(
        DeskQuery(floor=4, status=DeskStatus.DOWN), PageRequest(page_size=0)
    )
    assert page.total == 1
    assert page.items[0].identifier == "4-001"


def test_search_by_engineer(service):
    page = service.search_desks(DeskQuery(search="Alice"), PageRequest(page_size=0))
    assert {d.identifier for d in page.items} == {"4-001", "5-001"}


def test_search_by_identifier(service):
    page = service.search_desks(DeskQuery(search="4-002"), PageRequest(page_size=0))
    assert page.total == 1
    assert page.items[0].identifier == "4-002"


def test_search_by_halo_ticket(service):
    page = service.search_desks(DeskQuery(search="1111111"), PageRequest(page_size=0))
    assert page.total == 1
    assert page.items[0].identifier == "4-001"


def test_search_by_notes(service):
    page = service.search_desks(DeskQuery(search="monitor"), PageRequest(page_size=0))
    assert page.total == 1
    assert page.items[0].identifier == "5-002"


def test_sort_by_identifier_descending(service):
    page = service.search_desks(
        DeskQuery(sort=DeskSort.IDENTIFIER, descending=True),
        PageRequest(page_size=5),
    )
    assert page.items[0].identifier == "5-130"


def test_sort_by_engineer(service):
    # Engineers set: Alice, Bob, Carol on four desks; rest are NULL.
    page = service.search_desks(
        DeskQuery(search="", sort=DeskSort.ENGINEER, descending=True),
        PageRequest(page_size=5),
    )
    # Descending by engineer puts Carol/Bob/Alice above the NULLs.
    top_engineers = [d.last_engineer for d in page.items if d.last_engineer]
    assert top_engineers[0] == "Carol"


def test_filtered_pagination_total_is_consistent(service):
    """Filtered total must reflect the filter, not the whole table."""
    page = service.search_desks(
        DeskQuery(floor=4), PageRequest(page=1, page_size=50)
    )
    assert page.total == 150
    assert page.total_pages == 3
    assert len(page.items) == 50


def test_search_no_results(service):
    page = service.search_desks(
        DeskQuery(search="nonexistent-term"), PageRequest(page_size=0)
    )
    assert page.total == 0
    assert page.items == []
    assert page.total_pages == 1
