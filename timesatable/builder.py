"""Builders for TimeSATable — normalise constraints and generate timeslot grids."""

from __future__ import annotations

from .domain import Day, Time, TimeInterval, Timeslot


class TimeConstraintBuilder:
    """Produces a normalised (non-overlapping, sorted) list of unavailable TimeIntervals."""

    @staticmethod
    def normalise(intervals: list[TimeInterval]) -> list[TimeInterval]:
        """Merge overlapping/adjacent intervals and return sorted list."""
        if not intervals:
            return []
        sorted_ivs = sorted(intervals, key=lambda iv: iv.start_time)
        merged: list[TimeInterval] = [sorted_ivs[0]]
        for iv in sorted_ivs[1:]:
            last = merged[-1]
            # adjacent or overlapping
            if iv.start_time <= last.end_time:
                merged[-1] = TimeInterval.merge(last, iv)
            else:
                merged.append(iv)
        return merged

    @staticmethod
    def from_unavailable(intervals: list[TimeInterval]) -> list[TimeInterval]:
        """Direct: normalise and return."""
        return TimeConstraintBuilder.normalise(intervals)

    @staticmethod
    def from_available(
        available: list[TimeInterval],
        day_start: Time,
        day_end: Time,
    ) -> list[TimeInterval]:
        """Invert available windows within [day_start, day_end] to get unavailable."""
        norm = TimeConstraintBuilder.normalise(available)
        unavailable: list[TimeInterval] = []
        cursor = day_start
        for iv in norm:
            if cursor < iv.start_time:
                unavailable.append(TimeInterval(cursor, iv.start_time - cursor))
            cursor = max(cursor, iv.end_time)
        if cursor < day_end:
            unavailable.append(TimeInterval(cursor, day_end - cursor))
        return unavailable

    @staticmethod
    def from_timeslots(
        available_slots: list[Time],
        meeting_duration: int,
        day_start: Time,
        day_end: Time,
    ) -> list[TimeInterval]:
        """
        Derive unavailability from a list of allowed start times.
        Any minute not covered by an allowed [slot, slot+duration) window is unavailable.
        """
        available_ivs = [
            TimeInterval(t, meeting_duration) for t in available_slots
        ]
        return TimeConstraintBuilder.from_available(available_ivs, day_start, day_end)


class TimesheetBuilder:
    """Generates the list of candidate Timeslots (day × start_time pairs)."""

    @staticmethod
    def from_days_and_times(
        days: list[Day],
        available_times: list[TimeInterval],
        step_minutes: int,
    ) -> list[Timeslot]:
        """
        Regular grid: for each day and each available window, emit one Timeslot
        per step_minutes-aligned start time that fits inside the window.
        """
        timeslots: list[Timeslot] = []
        for day in days:
            for window in available_times:
                t = window.start_time
                while t.minutes + step_minutes <= window.end_time.minutes:
                    timeslots.append(Timeslot(day=day, start_time=t))
                    t = t + step_minutes
        return timeslots

    @staticmethod
    def from_days_and_slots(
        days: list[Day],
        slot_times: list[Time],
    ) -> list[Timeslot]:
        """Explicit list of start times, same set applied to every day."""
        return [
            Timeslot(day=day, start_time=t)
            for day in days
            for t in slot_times
        ]
