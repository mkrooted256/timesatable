"""Core domain model for TimeSATable."""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class Time:
    """A point in time within a single day, stored as minutes since midnight."""

    minutes: int  # 0–1439

    @staticmethod
    def parse(s: str) -> "Time":
        """Parse 'HH:MM' string."""
        h, m = s.split(":")
        return Time(int(h) * 60 + int(m))

    def __str__(self) -> str:
        return f"{self.minutes // 60:02d}:{self.minutes % 60:02d}"

    def __add__(self, minutes: int) -> "Time":
        return Time(self.minutes + minutes)

    def __sub__(self, other: "Time") -> int:
        """Difference in minutes."""
        return self.minutes - other.minutes


# ---------------------------------------------------------------------------
# TimeInterval
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeInterval:
    start_time: Time
    duration_minutes: int

    @property
    def end_time(self) -> Time:
        return self.start_time + self.duration_minutes

    @staticmethod
    def does_intersect(a: "TimeInterval", b: "TimeInterval") -> bool:
        return a.start_time < b.end_time and b.start_time < a.end_time

    @staticmethod
    def merge(a: "TimeInterval", b: "TimeInterval") -> "TimeInterval":
        """Merge two overlapping or adjacent intervals into one."""
        start = min(a.start_time, b.start_time)
        end = max(a.end_time, b.end_time)
        return TimeInterval(start, end - start)

    def __str__(self) -> str:
        return f"{self.start_time}-{self.end_time}"


# ---------------------------------------------------------------------------
# Day
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Day:
    name: str

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Timeslot
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Timeslot:
    """A candidate start position for a meeting."""

    day: Day
    start_time: Time

    def __str__(self) -> str:
        return f"{self.day} {self.start_time}"


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

@dataclass
class Room:
    name: str
    unavailable_times: list[TimeInterval] = field(default_factory=list)

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Room) and self.name == other.name


# ---------------------------------------------------------------------------
# Participant
# ---------------------------------------------------------------------------

@dataclass
class Participant:
    name: str
    unavailable_times: list[TimeInterval] = field(default_factory=list)

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Participant) and self.name == other.name


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------

@dataclass
class Meeting:
    title: str
    duration_minutes: int
    participants: list[Participant] = field(default_factory=list)
    unavailable_times: list[TimeInterval] = field(default_factory=list)

    def __str__(self) -> str:
        return self.title

    def __hash__(self) -> int:
        return hash(self.title)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Meeting) and self.title == other.title


# ---------------------------------------------------------------------------
# PlannedMeeting (output)
# ---------------------------------------------------------------------------

@dataclass
class PlannedMeeting:
    title: str
    duration_minutes: int
    participants: list[Participant]
    room: Room
    day: Day
    start_time: Time

    @property
    def end_time(self) -> Time:
        return self.start_time + self.duration_minutes

    @property
    def interval(self) -> TimeInterval:
        return TimeInterval(self.start_time, self.duration_minutes)

    def __str__(self) -> str:
        return (
            f"{self.title} | {self.day} {self.start_time}-{self.end_time}"
            f" | {self.room}"
        )


# ---------------------------------------------------------------------------
# Schedule (pre-solve container)
# ---------------------------------------------------------------------------

@dataclass
class Schedule:
    """Container for all inputs before solving."""

    step_minutes: int
    days: list[Day]
    rooms: list[Room]
    participants: list[Participant]
    meetings: list[Meeting]
    timeslots: list[Timeslot] = field(default_factory=list)
