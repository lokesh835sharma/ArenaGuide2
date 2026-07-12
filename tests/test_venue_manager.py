from __future__ import annotations

from src.services.venue_manager import VenueData, load_venue


def test_stadium_fixture_loads_successfully():
    venue: VenueData = load_venue()
    assert venue.name == "MetLife Stadium"
    assert venue.capacity == 82500
    assert "concourse_lower_sw" in venue.zones
    assert len(venue.facilities) > 0


def test_zone_name_falls_back_to_id():
    venue: VenueData = load_venue()
    # If a zone has no name mapped, it should return its ID.
    assert venue.zone_name("non_existent_zone") == "non_existent_zone"


def test_facilities_of_types():
    venue: VenueData = load_venue()
    restrooms = venue.facilities_of_types({"restroom", "accessible_restroom"})
    assert len(restrooms) > 0
    assert all(f.type in ("restroom", "accessible_restroom") for f in restrooms)

    acc_restrooms = venue.facilities_of_types(
        {"restroom", "accessible_restroom"}, accessible_only=True
    )
    assert all(f.accessible for f in acc_restrooms)
