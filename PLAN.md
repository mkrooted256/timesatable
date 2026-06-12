# TimeSATable — Implementation Plan

## Overview

A timetable scheduling tool that takes a set of meetings, participants, rooms, and constraints,
and produces a conflict-free schedule. The core solver can be swapped (WBO, ILP via cvxpy, pure SAT via pycosat).

---

## Project Structure

```
timesatable/
├── bin/wbo                     # bundled WBO solver binary
├── timetable/
│   ├── __init__.py
│   ├── domain.py               # core data classes
│   ├── builder.py              # TimesheetBuilder, TimeConstraintBuilder
│   ├── serialization.py        # load/save from human-readable file
│   ├── encoding/
│   │   ├── __init__.py
│   │   ├── base.py             # abstract Encoder interface
│   │   ├── wbo.py              # WBO (.wcnf) encoder
│   │   ├── ilp.py              # cvxpy ILP encoder
│   │   └── sat.py              # pycosat SAT encoder (optional)
│   ├── solver.py               # solver runner, parses solver output -> PlannedMeeting list
│   └── cli.py                  # entry point
├── examples/
│   └── example.yaml            # sample input file
├── tests/
│   ├── test_domain.py
│   ├── test_encoding.py
│   └── test_serialization.py
├── PLAN.md
└── README.md
```

---

## Phases

### Phase 1 — Domain Model

Implement all data classes from the README as plain Python dataclasses or attrs classes.

Classes to implement (in `domain.py`):
- `Time` — wraps minutes-since-midnight; parses "HH:MM"; supports comparison and arithmetic
- `TimeInterval` — `start_time`, `duration_minutes`; computed `end_time`; static `does_intersect`, `merge`
- `Day` — `name: str`
- `Timeslot` — `day: Day`, `start_time: Time`
- `Room` — `name: str`, `unavailable_times: list[TimeInterval]`
- `Participant` — `name: str`, `unavailable_times: list[TimeInterval]`
- `Meeting` — `title`, `duration_minutes`, `participants`, `unavailable_times`
- `PlannedMeeting` — extends Meeting with `room`, `day`, `start_time`, computed `end_time`

**Design note:** keep constraints on the entity itself (not separate constraint objects) for simplicity.

---

### Phase 2 — Builders

Implement in `builder.py`:

**`TimeConstraintBuilder`**  
Normalises a list of `TimeInterval`s (merges overlapping intervals).  
Constructors:
- `from_unavailable(intervals)` — direct
- `from_available(intervals, day_start, day_end)` — invert
- `from_timeslots(timeslots, meeting_duration)` — derive unavailability from available start times

**`TimesheetBuilder`**  
Generates the list of candidate `Timeslot`s for a week:
- `from_days_and_times(days, available_times, step_minutes)` — regular grid
- `from_days_and_slots(days, slot_times)` — explicit list per day

---

### Phase 3 — Serialization

**Format: YAML** (human-readable, easy to edit, widely supported; use `PyYAML` or `ruamel.yaml`)

Schema sketch:
```yaml
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
      - "12:00-13:00"  # Monday lunch

meetings:
  - title: Standup
    duration_minutes: 30
    participants: [Alice, Bob]
    unavailable: []
```

Implement `load(path) -> Schedule` and `save(schedule, path)` in `serialization.py`.  
`Schedule` is a container dataclass holding all domain objects before solving.

---

### Phase 4 — Constraint Encoding

The scheduling problem in Boolean terms:

**Decision variable:**  
`x[meeting, timeslot, room]` = 1 if meeting is assigned to that timeslot in that room.

**Implicit domain constraints (always enforced, not user-configurable):**
- At most one meeting per room at any point in time (rooms are not shared).
- At most one simultaneous meeting per participant (no double-booking).
- Every meeting must be assigned to exactly one room (rooms are mandatory).
- Any room is eligible for any meeting, subject only to room availability.
- Meetings are not split across days (single-day only).
- Meeting start times are aligned to `step_minutes` (the candidate timeslot grid).
- No soft constraints — all constraints are hard.

**Hard constraints (encoding):**
1. Each meeting is assigned to exactly one (timeslot, room) pair.
2. No two meetings share the same room at an overlapping time.
3. No two meetings share a participant at an overlapping time.
4. Meeting is not placed in a timeslot that intersects any of its `unavailable_times`.
5. Room/participant unavailability intervals are respected.

**Encoding targets:**
- `wbo.py` — emit `.wcnf` format consumed by `bin/wbo`; hard clauses get weight `top`
- `ilp.py` — model with `cvxpy` binary variables and linear constraints

Start with `wbo.py` as the primary backend; `ilp.py` as a fallback/comparison.

---

### Phase 5 — Solver Runner

`solver.py` — orchestrates encoding + invocation + parsing:

```
Schedule → Encoder → solver input file
                  → subprocess call (wbo binary or cvxpy solve)
                  → parse output
                  → list[PlannedMeeting]
```

For WBO: parse the `v` line of the solver output (variable assignments).  
For cvxpy: read variable values directly from the cvxpy solution object.

Handle UNSAT (no solution) and report which constraints conflict if possible.

---

### Phase 6 — CLI & Output

`cli.py` using `argparse`:
```
timetable solve input.yaml [--solver wbo|ilp] [--output out.yaml]
timetable validate input.yaml       # check for obvious conflicts before solving
timetable example                   # write an example input file
```

Output formats:
- Pretty-printed table to stdout (primary)
- YAML file with `PlannedMeeting` entries (for reuse / archiving)

---

## Open Questions / Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Meeting duration vs. fixed timeslot grid — are meetings always aligned to `step_minutes`? | **Yes** — all start times snap to grid |
| 2 | Should rooms be optional (open-plan)? | **No** — every meeting requires a room |
| 3 | Any room suitable for any meeting? | **Yes** — no room-type restrictions |
| 4 | Multi-day meetings? | **Out of scope** |
| 5 | Soft constraints (preferences, not hard limits)? | **Out of scope for now** |
| 6 | Python version target? | **3.13+** |

---

## Testing Strategy

- **Unit tests** for `Time`, `TimeInterval` arithmetic and intersection logic
- **Unit tests** for `TimeConstraintBuilder` normalisation (especially inversion)
- **Integration tests** for encoder → solver → parse round-trip on small toy instances (2–3 meetings)
- **Serialization round-trip** test: `load(save(schedule)) == schedule`
