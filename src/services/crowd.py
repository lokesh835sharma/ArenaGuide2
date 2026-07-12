"""Time-based crowd density simulation.

The base crowd level of each zone (from ``crowd.json``) is escalated or relaxed
according to ``time_to_event``: gates and concourses surge as kickoff nears
and empty out once the match is underway. The mapping is deterministic, so it is
straightforward to unit-test.
"""

from __future__ import annotations

from src.services.venue_manager import VenueData

_LEVELS = ("low", "medium", "high")
_LEVEL_INDEX = {level: i for i, level in enumerate(_LEVELS)}


def _clamp(index: int) -> str:
    return _LEVELS[max(0, min(len(_LEVELS) - 1, index))]


def compute_density(venue: VenueData, zone_id: str, time_to_event: int | None) -> str:
    """Return the simulated density level (``low`` / ``medium`` / ``high``) for a zone.

    Rules (only applied to surge zone types, e.g. gates & concourses):
      * imminent window (0..10 min before kickoff): +2 levels
      * pre-match window (10..30 min before kickoff): +1 level
      * match underway (minutes < 0): gates relax by 1 level
    """
    base_index = _LEVEL_INDEX.get(venue.base_crowd(zone_id), 0)
    if time_to_event is None:
        return _clamp(base_index)

    sim = venue.crowd_sim
    surge_types = set(sim.get("surge_zone_types", []))
    zone_type = venue.zone_type(zone_id)
    bump = 0

    if zone_type in surge_types:
        pre = int(sim.get("pre_match_window_minutes", 30))
        imminent = int(sim.get("imminent_window_minutes", 10))
        if 0 <= time_to_event <= imminent:
            bump += 2
        elif imminent < time_to_event <= pre:
            bump += 1

    if time_to_event < 0 and zone_type == "gate" and sim.get("in_play_gate_relief"):
        bump -= 1

    return _clamp(base_index + bump)