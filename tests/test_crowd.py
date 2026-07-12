from __future__ import annotations

import pytest

from src.services.crowd import compute_density


@pytest.fixture
def _venue():
    from src.services.stadium_data import load_venue

    return load_venue()


def test_effective_crowd_no_time_returns_base(_venue):
    assert compute_density(_venue, "gate_a", None) == "medium"
    assert compute_density(_venue, "seating_upper", None) == "low"


def test_gates_surge_before_match(_venue):
    # 25 mins out -> +1 level
    assert compute_density(_venue, "gate_a", 25) == "high"
    # 5 mins out -> +2 levels
    assert compute_density(_venue, "gate_a", 5) == "high"


def test_gates_relax_in_play(_venue):
    # match started 10 mins ago
    assert compute_density(_venue, "gate_a", -10) == "low"


def test_seating_never_surges(_venue):
    # Seating areas are not "surge_zone_types"
    assert compute_density(_venue, "seating_upper", 5) == "low"
    assert compute_density(_venue, "seating_upper", -10) == "low"
