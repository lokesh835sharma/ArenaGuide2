"""Schema validation tests — the first line of input defense."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.schemas import MobilityRequirement, Locale, FanRequest


def _ctx(**overrides) -> dict:
    base = {
        "language": "en",
        "current_location": "concourse_lower_sw",
        "destination_intent": "restroom",
        "time_to_event": 20,
    }
    base.update(overrides)
    return base


def test_valid_context_parses():
    req = FanRequest(**_ctx())
    assert req.language is Locale.en
    assert req.accessibility_needs == [MobilityRequirement.none]


@pytest.mark.parametrize("lang", ["en", "es", "fr"])
def test_supported_languages_accepted(lang):
    assert FanRequest(**_ctx(language=lang)).language.value == lang


def test_unsupported_language_rejected():
    # German is out of scope; only the three host-nation languages are supported.
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(language="de"))


def test_invalid_accessibility_need_rejected():
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(accessibility_needs=["teleport"]))


def test_invalid_intent_rejected():
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(destination_intent="teleport"))


def test_unknown_zone_rejected():
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(current_location="mars_base"))


def test_oversized_ticket_section_rejected():
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(ticket_section="TOO-LONG-SECTION"))


def test_oversized_question_rejected():
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(question="x" * 281))


@pytest.mark.parametrize("minutes", [-121, 1441])
def test_minutes_out_of_range_rejected(minutes):
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(time_to_event=minutes))


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        FanRequest(**_ctx(is_admin=True))


def test_needs_are_normalized():
    # "none" alongside a real need is dropped; duplicates collapse.
    req = FanRequest(**_ctx(accessibility_needs=["none", "wheelchair", "wheelchair"]))
    assert req.accessibility_needs == [MobilityRequirement.wheelchair]


def test_question_is_sanitized():
    req = FanRequest(**_ctx(question="Hello\x00\x07   world\n\n"))
    assert req.question == "Hello world"


def test_empty_needs_defaults_to_none():
    req = FanRequest(**_ctx(accessibility_needs=[]))
    assert req.accessibility_needs == [MobilityRequirement.none]


def test_explicit_none_question_stays_none():
    req = FanRequest(**_ctx(question=None))
    assert req.question is None
