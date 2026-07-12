from __future__ import annotations

import pytest

from src.services.pathfinder import calculate_route, route_distance


@pytest.fixture
def _venue():
    from src.services.stadium_data import load_venue

    return load_venue()


def test_path_to_self_is_empty(_venue):
    path = calculate_route(_venue, "gate_a", "gate_a")
    assert path == []
    assert route_distance(path) == 0


def test_unknown_zones_return_none(_venue):
    assert calculate_route(_venue, "unknown_a", "gate_a") is None
    assert calculate_route(_venue, "gate_a", "unknown_b") is None


def test_valid_path_found(_venue):
    path = calculate_route(_venue, "gate_a", "concourse_lower_sw")
    assert path is not None
    assert len(path) == 1
    assert path[0].to == "concourse_lower_sw"
    assert path[0].distance == 40


def test_accessible_path_avoids_stairs(_venue):
    # From lower concourse to upper seating, default route takes stairs (shorter).
    default_path = calculate_route(_venue, "concourse_lower_sw", "seating_upper")
    assert default_path is not None
    assert any(e.means == "stairs" for e in default_path)

    # Accessible route must take the elevator (longer).
    acc_path = calculate_route(
        _venue, "concourse_lower_sw", "seating_upper", step_free_only=True
    )
    assert acc_path is not None
    assert not any(e.means == "stairs" for e in acc_path)
    assert any(e.means == "elevator" for e in acc_path)

    assert route_distance(acc_path) > route_distance(default_path)
