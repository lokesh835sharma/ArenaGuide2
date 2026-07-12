"""Context-driven navigation engine — deterministic rules run BEFORE the LLM.

``resolve_navigation`` resolves every fact (target facility, accessible route, crowd,
assistance mode, urgency) purely from the structured :class:`FanRequest`,
with zero LLM involvement. ``process_request`` then optionally hands those facts to the
LLM for natural-language phrasing/translation. Because the decision never depends
on the free-text ``question``, prompt injection cannot change routing or facts.
"""

from __future__ import annotations

from src.models.api_models import (
    AssistanceMode,
    DensityLevel,
    DirectionStep,
    FanRequest,
    GuidanceResponse,
    Locale,
    MobilityRequirement,
    NavigationGoal,
    NavigationResult,
    VenuePoint,
)
from src.services import phrasing
from src.services.ai_client import LanguageModel
from src.services.crowd import compute_density
from src.services.pathfinder import calculate_route, route_distance
from src.services.phrasing import ResponseContext
from src.services.venue_manager import Edge, Facility, VenueData, localized

# Which facility types satisfy each navigation goal.
_GOAL_FACILITY_MAP: dict[NavigationGoal, set[str]] = {
    NavigationGoal.restroom: {"restroom", "accessible_restroom"},
    NavigationGoal.first_aid: {"first_aid"},
    NavigationGoal.concession: {"concession"},
    NavigationGoal.guest_services: {"guest_services"},
    NavigationGoal.water: {"water"},
    NavigationGoal.sensory_room: {"sensory_room"},
    NavigationGoal.exit: {"exit"},
    NavigationGoal.gate: {"gate"},
    NavigationGoal.merchandise: {"merchandise"},
    # `seat` is resolved specially from the ticket section, not by proximity.
}

# Goals where swapping to a quieter equivalent facility is appropriate.
# Excludes `seat` (fixed) and `first_aid` (never reroute an emergency for crowd).
_SWAP_ELIGIBLE = {
    NavigationGoal.restroom,
    NavigationGoal.concession,
    NavigationGoal.water,
    NavigationGoal.guest_services,
    NavigationGoal.sensory_room,
    NavigationGoal.gate,
    NavigationGoal.exit,
}

_DENSITY_INDEX = {DensityLevel.low: 0, DensityLevel.medium: 1, DensityLevel.high: 2}
_TIME_SENSITIVE_GOALS = {NavigationGoal.gate, NavigationGoal.seat}


class PathUnavailable(Exception):
    """Raised when no facility/route satisfies the request under the constraints."""


def _to_venue_point(facility: Facility, language: str) -> VenuePoint:
    return VenuePoint(
        id=facility.id,
        name=localized(facility.names, language) or facility.id,
        type=facility.type,
        zone=facility.zone,
        accessible=facility.accessible,
        landmark=localized(facility.landmarks, language),
    )


def _locate_assigned_seat(req: FanRequest, venue: VenueData) -> Facility:
    """Pick the seat facility implied by the ticket section (100s → lower, else upper)."""
    section = (req.ticket_section or "").strip()
    upper = bool(section) and section[0] in {"2", "3", "4"}
    target_id = "seat_upper" if upper else "seat_lower"
    for facility in venue.facilities:
        if facility.id == target_id:
            return facility
    raise PathUnavailable("seat facility fixture missing")


def _reachable_facilities(
    req: FanRequest, venue: VenueData, types: set[str], *, accessible_only: bool, step_free: bool
) -> list[tuple[Facility, list[Edge], int]]:
    """Return (facility, path, distance) for every reachable candidate facility."""
    results: list[tuple[Facility, list[Edge], int]] = []
    for facility in venue.facilities_of_types(types, accessible_only=accessible_only):
        path = calculate_route(venue, req.current_location, facility.zone, step_free_only=step_free)
        if path is None:
            continue
        results.append((facility, path, route_distance(path)))
    # Deterministic ordering: nearest first, then by id.
    results.sort(key=lambda item: (item[2], item[0].id))
    return results


def _compile_directions(
    venue: VenueData, start: str, path: list[Edge], facility: Facility, language: str
) -> list[DirectionStep]:
    """Turn a path of edges into localized, accessibility-aware direction steps."""
    steps: list[DirectionStep] = []
    facility_name = localized(facility.names, language) or facility.id
    node = start
    for i, edge in enumerate(path):
        is_final = i == len(path) - 1
        landmark = localized(facility.landmarks, language) if is_final else None
        steps.append(
            DirectionStep(
                order=i + 1,
                from_zone=node,
                to_zone=edge.to,
                means=edge.means,
                step_free=edge.step_free,
                distance=edge.distance,
                landmark=landmark,
                instruction=phrasing.direction_text(
                    edge.means,
                    venue.zone_name(edge.to, language),
                    landmark,
                    is_final=is_final,
                    facility_name=facility_name,
                    language=language,
                ),
            )
        )
        node = edge.to
    return steps


def resolve_navigation(req: FanRequest, venue: VenueData) -> NavigationResult:
    """Run the deterministic rule pipeline and return a :class:`NavigationResult`."""
    needs = set(req.accessibility_needs)
    wheelchair = MobilityRequirement.wheelchair in needs
    visual = MobilityRequirement.visual in needs
    hearing = MobilityRequirement.hearing in needs

    # Rule: wheelchair or visual users get accessible facilities + step-free routes.
    accessible_only = wheelchair or visual
    step_free = wheelchair or visual

    if visual:
        mode = AssistanceMode.screen_reader
    elif hearing:
        mode = AssistanceMode.captioned
    else:
        mode = AssistanceMode.standard

    # --- Resolve the target facility + route ---
    if req.destination_intent == NavigationGoal.seat:
        facility = _locate_assigned_seat(req, venue)
        path = calculate_route(venue, req.current_location, facility.zone, step_free_only=step_free)
        if path is None:
            raise PathUnavailable("no accessible route to seat")
        swap_note: str | None = None
    else:
        types = _GOAL_FACILITY_MAP[req.destination_intent]
        candidates = _reachable_facilities(
            req, venue, types, accessible_only=accessible_only, step_free=step_free
        )
        if not candidates:
            raise PathUnavailable(f"no reachable facility for goal {req.destination_intent.value}")
        facility, path, _dist = candidates[0]
        facility, path, swap_note = _crowd_aware_reroute(
            req, venue, facility, path, candidates
        )

    # --- Crowd at the final target ---
    density = DensityLevel(compute_density(venue, facility.zone, req.time_to_event))

    # --- Urgency ---
    hurry = req.time_to_event < 15 and req.destination_intent in _TIME_SENSITIVE_GOALS
    urgency = phrasing.time_alert(req.language.value) if hurry else None

    directions = _compile_directions(
        venue, req.current_location, path, facility, req.language.value
    )

    # Calculate estimated time based on distance and crowd level
    total_distance = sum(step.distance for step in directions)
    if density == DensityLevel.low:
        speed = 1.4
    elif density == DensityLevel.medium:
        speed = 1.0
    else:
        speed = 0.6

    estimated_time = max(1, int(total_distance / speed / 60))

    # Provide offline advice if in a hurry
    offline_advice = None
    if hurry:
        if req.language == Locale.fr:
            offline_advice = "Mode rapide: restez à droite et utilisez les voies rapides."
        elif req.language == Locale.es:
            offline_advice = "Modo rápido: manténgase a la derecha y use carriles rápidos."
        else:
            offline_advice = "Express mode: stay to the right and use designated fast-walk lanes."

    return NavigationResult(
        facility=_to_venue_point(facility, req.language.value),
        route_steps=directions,
        crowd_level=density,
        language=req.language,
        accessibility_mode=mode,
        landmark_based=visual,
        hurry=hurry,
        alternatives_note=swap_note,
        urgency=urgency,
        estimated_time_minutes=estimated_time,
        offline_advice=offline_advice,
    )


def _crowd_aware_reroute(
    req: FanRequest,
    venue: VenueData,
    facility: Facility,
    path: list[Edge],
    candidates: list[tuple[Facility, list[Edge], int]],
) -> tuple[Facility, list[Edge], str | None]:
    """If the nearest facility is crowded, swap to the quietest nearby alternative."""
    if req.destination_intent not in _SWAP_ELIGIBLE:
        return facility, path, None

    primary_density = DensityLevel(compute_density(venue, facility.zone, req.time_to_event))
    if primary_density != DensityLevel.high:
        return facility, path, None

    alternatives: list[tuple[int, int, str, Facility, list[Edge]]] = []
    for cand, cand_path, cand_dist in candidates:
        if cand.id == facility.id:
            continue
        cand_density = DensityLevel(compute_density(venue, cand.zone, req.time_to_event))
        if cand_density == DensityLevel.high:
            continue
        alternatives.append((_DENSITY_INDEX[cand_density], cand_dist, cand.id, cand, cand_path))

    if not alternatives:
        return facility, path, None  # everywhere is busy; keep the nearest

    # Quietest first, then nearest, then id — fully deterministic.
    alternatives.sort(key=lambda a: (a[0], a[1], a[2]))
    _, _, _, alt_facility, alt_path = alternatives[0]
    note = phrasing.quieter_option_hint(alt_facility.type, req.language.value)
    return alt_facility, alt_path, note


async def process_request(req: FanRequest, venue: VenueData, llm: LanguageModel) -> GuidanceResponse:
    """Resolve facts (rules), then phrase them (templates or LLM) into a response."""
    result = resolve_navigation(req, venue)

    response_ctx = ResponseContext(
        language=result.language.value,
        facility_name=result.facility.name,
        facility_type=result.facility.type,
        facility_landmark=result.facility.landmark,
        crowd_level=result.crowd_level.value,
        accessibility_mode=result.accessibility_mode.value,
        landmark_based=result.landmark_based,
        hurry=result.hurry,
        alternative_type=result.facility.type if result.alternatives_note else None,
        total_distance=sum(step.distance for step in result.route_steps),
        step_count=len(result.route_steps),
        estimated_time_minutes=result.estimated_time_minutes,
        offline_advice=result.offline_advice,
    )

    if req.question:
        # Free-text question present → engage the LLM layer for phrasing/translation.
        answer = await llm.phrase(response_ctx, req.question)
        used_llm = llm.is_live
    else:
        # Short-circuit: rules fully answer the query; skip the LLM entirely.
        answer = phrasing.compose_reply(response_ctx)
        used_llm = False

    return GuidanceResponse(
        answer=answer,
        route_steps=result.route_steps,
        facility=result.facility,
        crowd_level=result.crowd_level,
        language=result.language,
        accessibility_mode=result.accessibility_mode,
        alternatives_note=result.alternatives_note,
        urgency=result.urgency,
        used_llm=used_llm,
        estimated_time_minutes=result.estimated_time_minutes,
        offline_advice=result.offline_advice,
    )