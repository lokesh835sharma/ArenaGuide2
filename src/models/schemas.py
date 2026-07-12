"""Pydantic v2 request/response models and enumeration types.

All external input flows through :class:`FanRequest`, which constrains every
field with enums, bounds and validators. Unknown zone ids and unknown fields are
rejected, and the free-text ``question`` is sanitized on the way in.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Locale(StrEnum):
    """Supported response locales — the three FIFA WC 2026 host-nation languages
    (USA/Canada → English/French, Mexico → Spanish)."""

    en = "en"
    es = "es"
    fr = "fr"


class MobilityRequirement(StrEnum):
    wheelchair = "wheelchair"
    visual = "visual"
    hearing = "hearing"
    none = "none"


class NavigationGoal(StrEnum):
    restroom = "restroom"
    gate = "gate"
    seat = "seat"
    exit = "exit"
    first_aid = "first_aid"
    concession = "concession"
    guest_services = "guest_services"
    water = "water"
    sensory_room = "sensory_room"
    merchandise = "merchandise"


class DensityLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class AssistanceMode(StrEnum):
    """Server-side response mode controlling how the UI presents the answer.

    (The client also provides a purely visual "high-contrast" CSS theme toggle,
    which maps to the ``visual`` requirement → ``screen_reader`` mode server-side.)
    """

    standard = "standard"
    screen_reader = "screen_reader"  # visual need: landmark-based, SR-optimized
    captioned = "captioned"  # hearing need: emphasize visual signage / quiet space


class FanRequest(BaseModel):
    """Structured fan context — the sole body of ``POST /api/assist``."""

    model_config = ConfigDict(extra="forbid")  # reject unknown fields (defense in depth)

    language: Locale = Locale.en
    current_location: str = Field(..., min_length=1, max_length=40)
    destination_intent: NavigationGoal
    accessibility_needs: list[MobilityRequirement] = Field(
        default_factory=lambda: [MobilityRequirement.none]
    )
    ticket_section: str | None = Field(
        default=None, max_length=8, pattern=r"^[A-Za-z0-9\- ]{1,8}$"
    )
    time_to_event: int = Field(..., ge=-120, le=1440)
    question: str | None = Field(default=None, max_length=280)

    @field_validator("current_location")
    @classmethod
    def _zone_must_exist(cls, value: str) -> str:
        # Imported lazily to avoid a circular import at module load time.
        from src.services.stadium_data import load_venue

        if value not in load_venue().zone_ids():
            raise ValueError(f"unknown zone id: {value!r}")
        return value

    @field_validator("accessibility_needs")
    @classmethod
    def _normalize_needs(cls, needs: list[MobilityRequirement]) -> list[MobilityRequirement]:
        unique = set(needs)
        # "none" is meaningless alongside a real requirement; drop it.
        if MobilityRequirement.none in unique and len(unique) > 1:
            unique.discard(MobilityRequirement.none)
        if not unique:
            unique = {MobilityRequirement.none}
        return sorted(unique, key=lambda n: n.value)

    @field_validator("question")
    @classmethod
    def _sanitize_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from src.services.security import clean_user_input

        cleaned = clean_user_input(value)
        return cleaned or None


class DirectionStep(BaseModel):
    """One leg of a route, with an accessibility-aware, localized instruction."""

    order: int
    from_zone: str
    to_zone: str
    means: str
    step_free: bool
    distance: int
    landmark: str | None = None
    instruction: str


class VenuePoint(BaseModel):
    """Public representation of a resolved facility."""

    id: str
    name: str
    type: str
    zone: str
    accessible: bool
    landmark: str | None = None


class NavigationResult(BaseModel):
    """Internal, deterministic result of the navigation engine (pre-phrasing)."""

    facility: VenuePoint
    route_steps: list[DirectionStep]
    crowd_level: DensityLevel
    language: Locale
    accessibility_mode: AssistanceMode
    landmark_based: bool = False
    hurry: bool = False
    alternatives_note: str | None = None
    urgency: str | None = None
    estimated_time_minutes: int | None = None
    offline_advice: str | None = None


class GuidanceResponse(BaseModel):
    """Response body of ``POST /api/assist``."""

    answer: str
    route_steps: list[DirectionStep]
    facility: VenuePoint
    crowd_level: DensityLevel
    language: Locale
    accessibility_mode: AssistanceMode
    alternatives_note: str | None = None
    urgency: str | None = None
    used_llm: bool
    estimated_time_minutes: int | None = None
    offline_advice: str | None = None


class StatusResponse(BaseModel):
    status: str = "ok"
