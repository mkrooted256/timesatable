# TimeSATable
A timetable compiler for personal usage based on WBO SAT solver, linear programming solver or something similar. 

maybe there are some basic algorithms for this?
Available tools (not all are needed): cvxpy, pycosat (actually, entire pip ecosystem), bin/wbo (Weighted Boolean Optimization Solver from https://sat.inesc-id.pt/wbo/index.html).

Input:
- Meetings
- Days and timeslots for each day (possible times to start a meeting)
- Meeting participants
- Rooms (number of rooms)
- Constraints


# Domain

## Inputs and aux classes

Time:
    whatever.
    user input in hh:mm format, stored in some other format.
    comparison operators.
    accuracy up to a minute.
    All times within a single day.

TimeInterval:
    start_time: Time
    duration_minutes: int
    # getter for end_time -> Time
    # static does_intersect(a, b: TimeInterval) -> bool
    # static merge(a, b: TimeInterval) -> TimeInterval

Day:
    name: str

Timeslot:
    start_time: Time
    day: Day
    # no end time. just a list of possible start times

Room:
    name: str

Room constraints:
    # meeting in this room should not intersect these intervals
    unavailable_times: list[TimeInterval]

Meeting:
    title: str
    duration (minutes): int
    participants: list[Participant]

Meeting constraints:
    # meeting should not intersect these intervals
    unavailable_times: list[TimeInterval] 

Participant:
    name: str

Participant constraints:
    # meetings this participant takes part in should not intersect these intervals
    unavailable_times: list[TimeInterval] 

TimeConstraintBuilder:
    build normalized unavailable_times 
    - from a list of unavailable times 
    - from a list of available times (other are unavailable)
    - from a list of available/unavailable timeslots

TimesheetBuilder:
    build a system of timeslots by rules
    from list of days, list of (un)available times for each day

The whole input setup should be serializable to a human-readable text file 
that is easy to edit manually if needed.
The point is to save the file and reuse it for the next week without creating the objects in python.

## Constraints

### Implicit (always enforced)

- At most one meeting per room at any point in time — rooms cannot be shared.
- At most one simultaneous meeting per participant — no double-booking.
- Every meeting must be assigned to a room — open-plan (no room) is not supported.
- Any room is eligible for any meeting (subject to room availability) — no room-type restrictions.
- Meetings are confined to a single day — multi-day meetings are not supported.
- Meeting start times are aligned to `step_minutes` — the scheduling grid.

### Explicitly not supported (yet)

- Soft constraints / preferences — all constraints are hard.
- Room capacity / equipment requirements.


## Outputs

PlannedMeeting:
    title: str
    duration (minutes): int
    participants: list[Participant]
    room: Room
    day: Day
    start_time: Time
    end_time: Time

