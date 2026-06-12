"""Solver runner — ties encoding, execution, and output together."""

from __future__ import annotations

from pathlib import Path

from .domain import PlannedMeeting, Schedule
from .encoding.wbo import WBOEncoder


_WBO_DEFAULT = Path(__file__).parent.parent / "bin" / "wbo"


def solve(
    schedule: Schedule,
    solver: str = "wbo",
    wbo_binary: str | Path | None = None,
) -> list[PlannedMeeting] | None:
    """
    Encode and solve a scheduling problem.

    Parameters
    ----------
    schedule:
        Fully populated Schedule (including timeslots).
    solver:
        'wbo' (default) — use the bundled WBO binary.
    wbo_binary:
        Path to the WBO binary. Defaults to bin/wbo relative to the package root.

    Returns
    -------
    list[PlannedMeeting] if a solution was found, None if UNSAT.
    """
    if solver == "wbo":
        binary = Path(wbo_binary) if wbo_binary else _WBO_DEFAULT
        enc = WBOEncoder(wbo_binary=binary)
        enc.encode(schedule)
        return enc.solve()
    else:
        raise ValueError(f"Unknown solver '{solver}'. Supported: 'wbo'.")
