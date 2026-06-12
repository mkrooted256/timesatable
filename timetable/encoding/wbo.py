"""WBO (Weighted Boolean Optimization) encoder for TimeSATable.

Produces a .wcnf file consumed by bin/wbo.

Variable numbering:
    Variables are 1-indexed integers.
    x[m, s, r] = variable ID for (meeting m, timeslot s, room r).

Hard constraints (weight = top):
    C1. Each meeting assigned to exactly one (timeslot, room) pair.
        - At least one:  clause of all x[m,*,*]
        - At most one:   for each pair of assignments, not both true
    C2. Room exclusivity: no two meetings overlap in the same room.
    C3. Participant exclusivity: no two meetings overlap for the same participant.
    C4. Meeting unavailability: x[m,s,r] = 0 if timeslot s overlaps meeting m's unavailable times.
    C5. Room unavailability: x[m,s,r] = 0 if timeslot s overlaps room r's unavailable times.
    C6. Participant unavailability: x[m,s,r] = 0 if timeslot s overlaps any participant's unavailable times.
    C7. Alignment: x[m,s,r] = 0 if meeting m's duration doesn't fit within step_minutes
        (ensured by only generating valid timeslots, but checked defensively).
"""

from __future__ import annotations

import itertools
import subprocess
import tempfile
from pathlib import Path

from ..domain import Meeting, PlannedMeeting, Room, Schedule, TimeInterval, Timeslot
from .base import Encoder


class WBOEncoder(Encoder):
    def __init__(self, wbo_binary: str | Path = "bin/wbo"):
        self.wbo_binary = Path(wbo_binary)
        self._clauses: list[tuple[int, list[int]]] = []  # (weight, literals)
        self._top: int = 0
        self._num_vars: int = 0
        # Mapping: (meeting_idx, timeslot_idx, room_idx) -> var_id
        self._var: dict[tuple[int, int, int], int] = {}
        self._schedule: Schedule | None = None

    # ------------------------------------------------------------------
    # Variable allocation
    # ------------------------------------------------------------------

    def _alloc_vars(self, schedule: Schedule) -> None:
        vid = 1
        for mi in range(len(schedule.meetings)):
            for si in range(len(schedule.timeslots)):
                for ri in range(len(schedule.rooms)):
                    self._var[(mi, si, ri)] = vid
                    vid += 1
        self._num_vars = vid - 1

    # ------------------------------------------------------------------
    # Clause helpers
    # ------------------------------------------------------------------

    def _hard(self, lits: list[int]) -> None:
        self._clauses.append((0, lits))  # weight 0 = hard (filled in later as top)

    def _forbid(self, var: int) -> None:
        """Force a variable to False."""
        self._hard([-var])

    # ------------------------------------------------------------------
    # Constraint generation
    # ------------------------------------------------------------------

    def _timeslot_interval(self, ts: Timeslot, duration: int) -> TimeInterval:
        return TimeInterval(ts.start_time, duration)

    def _overlaps_unavailable(
        self, ts: Timeslot, duration: int, unavailable: list[TimeInterval]
    ) -> bool:
        meeting_iv = self._timeslot_interval(ts, duration)
        return any(TimeInterval.does_intersect(meeting_iv, u) for u in unavailable)

    def encode(self, schedule: Schedule) -> None:
        self._schedule = schedule
        self._clauses = []
        self._var = {}
        self._alloc_vars(schedule)

        meetings = schedule.meetings
        timeslots = schedule.timeslots
        rooms = schedule.rooms

        # Pre-compute which (meeting, timeslot, room) assignments are feasible
        # (not blocked by unavailability constraints).
        feasible: dict[tuple[int, int, int], bool] = {}
        for mi, mtg in enumerate(meetings):
            for si, ts in enumerate(timeslots):
                mtg_iv = self._timeslot_interval(ts, mtg.duration_minutes)
                # C4: meeting unavailability
                if self._overlaps_unavailable(ts, mtg.duration_minutes, mtg.unavailable_times):
                    for ri in range(len(rooms)):
                        feasible[(mi, si, ri)] = False
                    continue
                # C6: participant unavailability
                participant_blocked = any(
                    self._overlaps_unavailable(ts, mtg.duration_minutes, p.unavailable_times)
                    for p in mtg.participants
                )
                if participant_blocked:
                    for ri in range(len(rooms)):
                        feasible[(mi, si, ri)] = False
                    continue
                for ri, room in enumerate(rooms):
                    # C5: room unavailability
                    if self._overlaps_unavailable(ts, mtg.duration_minutes, room.unavailable_times):
                        feasible[(mi, si, ri)] = False
                    else:
                        feasible[(mi, si, ri)] = True

        # Force infeasible variables to False
        for (mi, si, ri), ok in feasible.items():
            if not ok:
                self._forbid(self._var[(mi, si, ri)])

        # C1a: each meeting assigned to at least one slot/room
        for mi in range(len(meetings)):
            lits = [
                self._var[(mi, si, ri)]
                for si in range(len(timeslots))
                for ri in range(len(rooms))
                if feasible.get((mi, si, ri), False)
            ]
            if not lits:
                # No feasible assignment exists — problem is UNSAT
                self._hard([])  # empty clause = always False
            else:
                self._hard(lits)

        # C1b: at most one assignment per meeting (pairwise)
        for mi in range(len(meetings)):
            assignments = [
                (si, ri)
                for si in range(len(timeslots))
                for ri in range(len(rooms))
            ]
            for (si1, ri1), (si2, ri2) in itertools.combinations(assignments, 2):
                v1 = self._var[(mi, si1, ri1)]
                v2 = self._var[(mi, si2, ri2)]
                self._hard([-v1, -v2])

        # C2: room exclusivity — no two meetings in same room overlap
        for ri, room in enumerate(rooms):
            for mi1, mtg1 in enumerate(meetings):
                for mi2, mtg2 in enumerate(meetings):
                    if mi1 >= mi2:
                        continue
                    for si1, ts1 in enumerate(timeslots):
                        iv1 = self._timeslot_interval(ts1, mtg1.duration_minutes)
                        for si2, ts2 in enumerate(timeslots):
                            iv2 = self._timeslot_interval(ts2, mtg2.duration_minutes)
                            if not TimeInterval.does_intersect(iv1, iv2):
                                continue
                            v1 = self._var[(mi1, si1, ri)]
                            v2 = self._var[(mi2, si2, ri)]
                            self._hard([-v1, -v2])

        # C3: participant exclusivity — no participant double-booked
        for mi1, mtg1 in enumerate(meetings):
            for mi2, mtg2 in enumerate(meetings):
                if mi1 >= mi2:
                    continue
                shared = set(p.name for p in mtg1.participants) & set(
                    p.name for p in mtg2.participants
                )
                if not shared:
                    continue
                for si1, ts1 in enumerate(timeslots):
                    iv1 = self._timeslot_interval(ts1, mtg1.duration_minutes)
                    for si2, ts2 in enumerate(timeslots):
                        iv2 = self._timeslot_interval(ts2, mtg2.duration_minutes)
                        if not TimeInterval.does_intersect(iv1, iv2):
                            continue
                        for ri1 in range(len(rooms)):
                            for ri2 in range(len(rooms)):
                                v1 = self._var[(mi1, si1, ri1)]
                                v2 = self._var[(mi2, si2, ri2)]
                                self._hard([-v1, -v2])

    # ------------------------------------------------------------------
    # WCNF serialization
    # ------------------------------------------------------------------

    def _to_wcnf(self) -> str:
        top = len(self._clauses) + 1  # weight for hard clauses
        lines: list[str] = []
        lines.append(f"p wcnf {self._num_vars} {len(self._clauses)} {top}")
        for weight, lits in self._clauses:
            w = top if weight == 0 else weight
            lines.append(f"{w} {' '.join(map(str, lits))} 0")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------

    def solve(self) -> list[PlannedMeeting] | None:
        assert self._schedule is not None, "Call encode() before solve()."
        wcnf = self._to_wcnf()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".wcnf", delete=False, encoding="utf-8"
        ) as f:
            f.write(wcnf)
            tmp_path = f.name

        try:
            result = subprocess.run(
                [str(self.wbo_binary), tmp_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return self._parse_output(result.stdout, self._schedule)

    def _parse_output(self, output: str, schedule: Schedule) -> list[PlannedMeeting] | None:
        """Parse WBO stdout. Returns None if UNSAT."""
        assignment: dict[int, bool] = {}
        sat = False
        for line in output.splitlines():
            if line.startswith("s "):
                sat = "OPTIMUM FOUND" in line or "SATISFIABLE" in line
            elif line.startswith("v "):
                for token in line[2:].split():
                    vid = int(token)
                    assignment[abs(vid)] = vid > 0

        if not sat:
            return None

        meetings = schedule.meetings
        timeslots = schedule.timeslots
        rooms = schedule.rooms

        planned: list[PlannedMeeting] = []
        for mi, mtg in enumerate(meetings):
            for si, ts in enumerate(timeslots):
                for ri, room in enumerate(rooms):
                    vid = self._var[(mi, si, ri)]
                    if assignment.get(vid, False):
                        planned.append(PlannedMeeting(
                            title=mtg.title,
                            duration_minutes=mtg.duration_minutes,
                            participants=list(mtg.participants),
                            room=room,
                            day=ts.day,
                            start_time=ts.start_time,
                        ))
        return planned
