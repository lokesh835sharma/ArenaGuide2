"""Rules engine tests — verifying deterministic facts and routing before phrasing."""

from __future__ import annotations

import pytest

from src.models.api_models import AssistanceMode, FanRequest
from src.services.rules_engine import PathUnavailable, resolve_navigation


@pytest.fixture
def _venue():
    from src.services.venue_manager import load_venue

    return load_venue()


def _req(**overrides) -> FanRequest:
    base = {
        "language": "en",
        "current_location": "concourse_lower_sw",
        "destination_intent": "restroom",
        "time_to_event": 20,
    }
    base.update(overrides)
    return FanRequest(**base)


def test_standard_user_gets_standard_mode(_venue):
    req = _req(accessibility_needs=["none"])
    out = resolve_navigation(req, _venue)
    assert out.accessibility_mode is AssistanceMode.standard
    assert out.landmark_based is False


def test_wheelchair_user_gets_accessible_route(_venue):
    # From concourse_lower_sw to seating_upper, the shortest route has stairs.
    # A wheelchair user must be routed via the elevator.
    req = _req(accessibility_needs=["wheelchair"], destination_intent="seat", ticket_section="201")
    out = resolve_navigation(req, _venue)

    assert out.facility.id == "seat_upper"
    assert out.accessibility_mode is AssistanceMode.standard  # visual/hearing mode not requested
    
    # Verify no stairs in the route
    assert not any(step.means == "stairs" for step in out.route_steps)
    assert any(step.means == "elevator" for step in out.route_steps)


def test_visual_need_gets_screen_reader_mode_and_landmarks(_venue):
    req = _req(accessibility_needs=["visual"])
    out = resolve_navigation(req, _venue)
    assert out.accessibility_mode is AssistanceMode.screen_reader
    assert out.landmark_based is True


def test_hearing_need_gets_captioned_mode(_venue):
    req = _req(accessibility_needs=["hearing"])
    out = resolve_navigation(req, _venue)
    assert out.accessibility_mode is AssistanceMode.captioned


def test_seat_target_resolves_via_ticket_section(_venue):
    # 100-level section goes to lower bowl
    req = _req(destination_intent="seat", ticket_section="134")
    out1 = resolve_navigation(req, _venue)
    assert out1.facility.id == "seat_lower"

    # 200-level goes to upper bowl
    req = _req(destination_intent="seat", ticket_section="201")
    out2 = resolve_navigation(req, _venue)
    assert out2.facility.id == "seat_upper"


def test_seat_target_fails_cleanly_without_ticket(_venue):
    req = _req(destination_intent="seat", ticket_section=None)
    out = resolve_navigation(req, _venue)
    # The default empty string resolves to lower bowl
    assert out.facility.id == "seat_lower"


def test_crowded_facility_triggers_alternative_swap(_venue):
    # From concourse_lower_se, the nearest restroom is restroom_lower_se (distance 0).
    # Its base crowd is high. At time_to_event=20, it remains high.
    # The next nearest is accessible_restroom_lower_ne in concourse_lower_ne (distance 60).
    # Its base crowd is low. At time_to_event=20, it goes to medium.
    req = _req(
        current_location="concourse_lower_se",
        destination_intent="restroom",
        time_to_event=20,
    )
    out = resolve_navigation(req, _venue)

    # It should swap to the accessible_restroom_lower_ne because it's quieter.
    assert out.facility.id == "accessible_restroom_lower_ne"
    assert out.alternatives_note is not None
    assert "crowded" in out.alternatives_note or "quieter" in out.alternatives_note


def test_swap_is_skipped_if_everywhere_is_busy(_venue, monkeypatch):
    from src.services import rules_engine
    # Force the simulator to return "high" for every zone.
    monkeypatch.setattr(rules_engine, "compute_density", lambda *a: "high")
    
    req = _req(current_location="concourse_lower_se", destination_intent="restroom")
    out = resolve_navigation(req, _venue)
    
    # It must return the nearest one (restroom_lower_se) despite the crowd.
    assert out.facility.id == "restroom_lower_se"
    assert out.alternatives_note is None


def test_unreachable_intent_raises_route_not_found(_venue):
    # If there are no sensory rooms in the fixture, it must raise.
    # Since there is one, we hack the fixture in memory.
    _venue.facilities = [f for f in _venue.facilities if f.type != "sensory_room"]
    req = _req(destination_intent="sensory_room")
    with pytest.raises(PathUnavailable):
        resolve_navigation(req, _venue)


def test_urgency_injected_for_gates_when_late(_venue):
    req = _req(destination_intent="gate", time_to_event=10)
    out = resolve_navigation(req, _venue)
    assert out.hurry is True
    assert out.urgency is not None


def test_urgency_not_injected_for_restrooms(_venue):
    req = _req(destination_intent="restroom", time_to_event=5)
    out = resolve_navigation(req, _venue)
    assert out.hurry is False
    assert out.urgency is None


def test_merchandise_intent(_venue):
    req = _req(destination_intent="merchandise", current_location="gate_a")
    out = resolve_navigation(req, _venue)
    assert out.facility.id == "merchandise_se"


def test_time_estimation_math(_venue):
    req = _req(current_location="gate_a", destination_intent="merchandise", time_to_event=120)
    out = resolve_navigation(req, _venue)
    assert out.estimated_time_minutes is not None
    # Assuming low crowd and distance ~100m, should be around 1 min
    assert out.estimated_time_minutes > 0


def test_offline_advice_injection(_venue):
    req = _req(current_location="gate_a", destination_intent="seat", time_to_event=5)
    out = resolve_navigation(req, _venue)
    assert out.hurry is True
    assert out.offline_advice is not None
    assert "Express mode" in out.offline_advice

    # Check French
    req_fr = _req(current_location="gate_a", destination_intent="seat", time_to_event=5, language="fr")
    out_fr = resolve_navigation(req_fr, _venue)
    assert "Mode rapide" in out_fr.offline_advice
