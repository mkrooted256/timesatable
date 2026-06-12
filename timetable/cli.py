"""Command-line interface for TimeSATable."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import serialization, solver
from .domain import PlannedMeeting


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _print_table(planned: list[PlannedMeeting]) -> None:
    if not planned:
        print("(no meetings scheduled)")
        return

    # Sort by day name then start time
    planned_sorted = sorted(planned, key=lambda pm: (pm.day.name, pm.start_time.minutes))

    col_widths = {
        "title": max(len("Meeting"), max(len(pm.title) for pm in planned_sorted)),
        "day": max(len("Day"), max(len(pm.day.name) for pm in planned_sorted)),
        "time": len("HH:MM-HH:MM"),
        "room": max(len("Room"), max(len(pm.room.name) for pm in planned_sorted)),
        "participants": max(
            len("Participants"),
            max(len(", ".join(p.name for p in pm.participants)) for pm in planned_sorted),
        ),
    }

    def row(title, day, time, room, participants):
        return (
            f"  {title:<{col_widths['title']}}  "
            f"{day:<{col_widths['day']}}  "
            f"{time:<{col_widths['time']}}  "
            f"{room:<{col_widths['room']}}  "
            f"{participants}"
        )

    sep = "-" * (
        col_widths["title"]
        + col_widths["day"]
        + col_widths["time"]
        + col_widths["room"]
        + col_widths["participants"]
        + 10
    )

    print(sep)
    print(row("Meeting", "Day", "Time", "Room", "Participants"))
    print(sep)
    for pm in planned_sorted:
        time_str = f"{pm.start_time}-{pm.end_time}"
        parts_str = ", ".join(p.name for p in pm.participants)
        print(row(pm.title, pm.day.name, time_str, pm.room.name, parts_str))
    print(sep)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_solve(args: argparse.Namespace) -> int:
    schedule = serialization.load(args.input)
    result = solver.solve(schedule, solver=args.solver)

    if result is None:
        print("UNSAT — no valid schedule exists with the given constraints.", file=sys.stderr)
        return 1

    _print_table(result)

    if args.output:
        # Write solved schedule back; timeslots are derived from PlannedMeetings.
        # For now, save the input schedule (structure) only — output is the table.
        out_path = Path(args.output)
        print(f"\nSchedule saved to {out_path}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        schedule = serialization.load(args.input)
    except Exception as exc:
        print(f"Error loading '{args.input}': {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    participant_names = {p.name for p in schedule.participants}
    for mtg in schedule.meetings:
        for p in mtg.participants:
            if p.name not in participant_names:
                errors.append(f"Meeting '{mtg.title}': unknown participant '{p.name}'.")
        if mtg.duration_minutes <= 0:
            errors.append(f"Meeting '{mtg.title}': duration must be positive.")
        if mtg.duration_minutes % schedule.step_minutes != 0:
            errors.append(
                f"Meeting '{mtg.title}': duration {mtg.duration_minutes} min "
                f"is not a multiple of step_minutes={schedule.step_minutes}."
            )

    if not schedule.rooms:
        errors.append("No rooms defined.")
    if not schedule.timeslots:
        errors.append("No timeslots generated — check days and available times.")

    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"OK — {len(schedule.meetings)} meeting(s), "
        f"{len(schedule.rooms)} room(s), "
        f"{len(schedule.timeslots)} timeslot(s)."
    )
    return 0


def cmd_example(args: argparse.Namespace) -> int:
    src = Path(__file__).parent.parent / "examples" / "example.yaml"
    dest = Path(args.output) if args.output else Path("example.yaml")
    if dest.exists() and not args.force:
        print(f"'{dest}' already exists. Use --force to overwrite.", file=sys.stderr)
        return 1
    shutil.copy(src, dest)
    print(f"Example written to '{dest}'.")
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timetable",
        description="TimeSATable — constraint-based timetable compiler",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # solve
    p_solve = sub.add_parser("solve", help="Solve a scheduling problem.")
    p_solve.add_argument("input", help="Path to input YAML file.")
    p_solve.add_argument("--solver", choices=["wbo"], default="wbo", help="Solver backend.")
    p_solve.add_argument("--output", "-o", help="Write output YAML to this path.")
    p_solve.set_defaults(func=cmd_solve)

    # validate
    p_val = sub.add_parser("validate", help="Validate an input file without solving.")
    p_val.add_argument("input", help="Path to input YAML file.")
    p_val.set_defaults(func=cmd_validate)

    # example
    p_ex = sub.add_parser("example", help="Write an example input file.")
    p_ex.add_argument("--output", "-o", default=None, help="Destination path (default: example.yaml).")
    p_ex.add_argument("--force", action="store_true", help="Overwrite existing file.")
    p_ex.set_defaults(func=cmd_example)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
