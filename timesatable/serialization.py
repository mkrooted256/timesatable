"""YAML serialization for TimeSATable schedules.

Format:

settings:
  step_minutes: 30

days:
  - name: Monday
    available:
      - "09:00-13:00"
      - "14:00-18:00"

rooms:
  - name: Room A
    unavailable: []

participants:
  - name: Alice
    unavailable:
      - "12:00-13:00"

meetings:
  - title: Standup
    duration_minutes: 30
    participants: [Alice, Bob]
    unavailable: []
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .builder import TimesheetBuilder, TimeConstraintBuilder
from .domain import (
    Day,
    Meeting,
    Participant,
    Room,
    Schedule,
    Time,
    TimeInterval,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_interval(s: str) -> TimeInterval:
    """Parse 'HH:MM-HH:MM' into a TimeInterval."""
    start_s, end_s = s.split("-", 1)
    start = Time.parse(start_s.strip())
    end = Time.parse(end_s.strip())
    duration = end.minutes - start.minutes
    if duration <= 0:
        raise ValueError(f"Invalid interval '{s}': end must be after start.")
    return TimeInterval(start, duration)


def _parse_intervals(raw: list[str] | None) -> list[TimeInterval]:
    if not raw:
        return []
    return [_parse_interval(s) for s in raw]


def _interval_to_str(iv: TimeInterval) -> str:
    return f"{iv.start_time}-{iv.end_time}"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load(path: str | Path) -> Schedule:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    settings = data.get("settings", {})
    step_minutes: int = int(settings.get("step_minutes", 30))

    # --- days & timeslots ---
    days: list[Day] = []
    all_available: dict[str, list[TimeInterval]] = {}
    for d in data.get("days", []):
        day = Day(name=d["name"])
        days.append(day)
        all_available[day.name] = _parse_intervals(d.get("available"))

    # Build timeslot grid: for each day use its own available windows
    timeslots = []
    for day in days:
        windows = all_available.get(day.name, [])
        if windows:
            timeslots.extend(
                TimesheetBuilder.from_days_and_times([day], windows, step_minutes)
            )

    # --- rooms ---
    rooms: list[Room] = []
    for r in data.get("rooms", []):
        rooms.append(Room(
            name=r["name"],
            unavailable_times=TimeConstraintBuilder.from_unavailable(
                _parse_intervals(r.get("unavailable"))
            ),
        ))

    # --- participants ---
    participants: list[Participant] = []
    participant_by_name: dict[str, Participant] = {}
    for p in data.get("participants", []):
        part = Participant(
            name=p["name"],
            unavailable_times=TimeConstraintBuilder.from_unavailable(
                _parse_intervals(p.get("unavailable"))
            ),
        )
        participants.append(part)
        participant_by_name[part.name] = part

    # --- meetings ---
    meetings: list[Meeting] = []
    for m in data.get("meetings", []):
        names = m.get("participants", [])
        mtg_participants = []
        for n in names:
            if n not in participant_by_name:
                raise ValueError(f"Meeting '{m['title']}' references unknown participant '{n}'.")
            mtg_participants.append(participant_by_name[n])
        meetings.append(Meeting(
            title=m["title"],
            duration_minutes=int(m["duration_minutes"]),
            participants=mtg_participants,
            unavailable_times=TimeConstraintBuilder.from_unavailable(
                _parse_intervals(m.get("unavailable"))
            ),
        ))

    return Schedule(
        step_minutes=step_minutes,
        days=days,
        rooms=rooms,
        participants=participants,
        meetings=meetings,
        timeslots=timeslots,
    )


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save(schedule: Schedule, path: str | Path) -> None:
    data: dict = {
        "settings": {"step_minutes": schedule.step_minutes},
        "days": [],
        "rooms": [],
        "participants": [],
        "meetings": [],
    }

    # Reconstruct available windows per day from the timeslot list.
    # We store them as individual step_minutes windows; consumers should merge them.
    day_slots: dict[str, list[str]] = {d.name: [] for d in schedule.days}
    for ts in schedule.timeslots:
        iv = TimeInterval(ts.start_time, schedule.step_minutes)
        day_slots[ts.day.name].append(_interval_to_str(iv))

    for day in schedule.days:
        data["days"].append({
            "name": day.name,
            "available": day_slots.get(day.name, []),
        })

    for room in schedule.rooms:
        data["rooms"].append({
            "name": room.name,
            "unavailable": [_interval_to_str(iv) for iv in room.unavailable_times],
        })

    for part in schedule.participants:
        data["participants"].append({
            "name": part.name,
            "unavailable": [_interval_to_str(iv) for iv in part.unavailable_times],
        })

    for mtg in schedule.meetings:
        data["meetings"].append({
            "title": mtg.title,
            "duration_minutes": mtg.duration_minutes,
            "participants": [p.name for p in mtg.participants],
            "unavailable": [_interval_to_str(iv) for iv in mtg.unavailable_times],
        })

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
