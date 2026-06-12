"""Abstract base class for constraint encoders."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain import PlannedMeeting, Schedule


class Encoder(ABC):
    @abstractmethod
    def encode(self, schedule: Schedule) -> None:
        """Encode the scheduling problem from the given schedule."""

    @abstractmethod
    def solve(self) -> list[PlannedMeeting] | None:
        """
        Run the solver and return a list of PlannedMeetings, or None if UNSAT.
        Must be called after encode().
        """
