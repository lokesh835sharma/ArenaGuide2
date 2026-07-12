from __future__ import annotations

import pytest

from src.services.phrasing import (
    ResponseContext,
    quieter_option_hint,
    compose_reply,
    direction_text,
    time_alert,
)


def _ctx(**overrides) -> ResponseContext:
    base = {
        "language": "en",
        "facility_name": "Test Restroom",
        "facility_type": "restroom",
        "facility_landmark": "near Section 101",
        "crowd_level": "low",
        "accessibility_mode": "standard",
        "landmark_based": False,
        "hurry": False,
        "alternative_type": None,
        "total_distance": 100,
        "step_count": 2,
        "estimated_time_minutes": 2,
        "offline_advice": None,
    }
    base.update(overrides)
    return ResponseContext(**base)


def test_render_answer_english_happy_path():
    ctx = _ctx()
    ans = compose_reply(ctx)
    assert "Your destination is Test Restroom (near Section 101)." in ans
    assert "Follow the 2-step route below" in ans
    assert "Crowd level there is currently low." in ans


def test_render_answer_zero_steps_means_already_there():
    ctx = _ctx(step_count=0)
    ans = compose_reply(ctx)
    assert "You're already at this location." in ans
    assert "Follow the" not in ans


def test_render_answer_includes_alternative_note():
    ctx = _ctx(alternative_type="restroom")
    ans = compose_reply(ctx)
    assert "A closer restroom was crowded" in ans


def test_render_answer_landmark_mode():
    ctx = _ctx(landmark_based=True)
    ans = compose_reply(ctx)
    assert "These directions use landmarks" in ans


def test_render_answer_captioned_mode():
    ctx = _ctx(accessibility_mode="captioned")
    ans = compose_reply(ctx)
    assert "Look for visual signage" in ans


def test_render_answer_hurry():
    ctx = _ctx(hurry=True)
    ans = compose_reply(ctx)
    assert "Kickoff is very soon" in ans


def test_render_answer_offline_advice():
    ctx = _ctx(offline_advice="Express mode on.")
    ans = compose_reply(ctx)
    assert "Express mode on." in ans


def test_render_answer_french_localization():
    ctx = _ctx(
        language="fr",
        facility_name="Toilettes Nord",
        facility_landmark="près de l'entrée",
        crowd_level="high",
    )
    ans = compose_reply(ctx)
    assert "Votre destination est Toilettes Nord (près de l'entrée)." in ans
    assert "L'affluence sur place est actuellement élevée." in ans


def test_step_instruction_mid_step():
    inst = direction_text(
        "walk", "Gate A", None, is_final=False, facility_name="Restroom", language="en"
    )
    assert inst == "Walk to Gate A."


def test_step_instruction_final_step_with_landmark():
    inst = direction_text(
        "elevator",
        "Level 2",
        "red doors",
        is_final=True,
        facility_name="Restroom",
        language="en",
    )
    assert inst == "Take the elevator to Level 2, where you'll find Restroom (red doors)."


def test_step_instruction_spanish():
    inst = direction_text(
        "stairs", "Nivel 2", None, is_final=False, facility_name="Aseo", language="es"
    )
    assert inst == "Suba por las escaleras hasta Nivel 2."


def test_urgency_note_french():
    assert "moins de 15 minutes" in time_alert("fr")


def test_alternatives_note_spanish():
    note = quieter_option_hint("restroom", "es")
    assert "aseo" in note
    assert "concurrido" in note
