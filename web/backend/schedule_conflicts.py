"""Detect overlapping cron fire times for schedules on the same device."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

from apscheduler.triggers.cron import CronTrigger


@dataclass(frozen=True)
class ConflictInfo:
    id: int
    name: str
    cron: str
    sample_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cron": self.cron,
            "sample_at": self.sample_at.isoformat(),
        }


def _iter_fire_times(
    cron: str,
    start: datetime,
    end: datetime,
) -> Iterable[datetime]:
    trigger = CronTrigger.from_crontab(cron)
    previous: Optional[datetime] = None
    fire_time = trigger.get_next_fire_time(None, start)
    while fire_time is not None and fire_time <= end:
        yield fire_time
        previous = fire_time
        fire_time = trigger.get_next_fire_time(previous, previous)


def _fire_minutes(cron: str, start: datetime, end: datetime) -> set[datetime]:
    return {
        fire_time.replace(second=0, microsecond=0)
        for fire_time in _iter_fire_times(cron, start, end)
    }


def find_cron_conflicts(
    candidate_cron: str,
    existing: Sequence[tuple[int, str, str]],
    *,
    exclude_id: Optional[int] = None,
    horizon_days: int = 7,
    now: Optional[datetime] = None,
) -> list[ConflictInfo]:
    """Return schedules whose fire times share a minute with ``candidate_cron``.

    ``existing`` entries are ``(id, name, cron)``. Schedules with empty cron are
    ignored. ``exclude_id`` skips the schedule being updated.
    """
    if not candidate_cron or not candidate_cron.strip():
        return []

    start = now or datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(days=horizon_days)

    candidate_minutes = _fire_minutes(candidate_cron, start, end)
    if not candidate_minutes:
        return []

    conflicts: list[ConflictInfo] = []
    for schedule_id, name, cron in existing:
        if exclude_id is not None and schedule_id == exclude_id:
            continue
        if not cron or not cron.strip():
            continue
        try:
            other_minutes = _fire_minutes(cron, start, end)
        except ValueError:
            continue
        overlap = candidate_minutes & other_minutes
        if not overlap:
            continue
        sample_at = min(overlap)
        conflicts.append(
            ConflictInfo(
                id=schedule_id,
                name=name,
                cron=cron,
                sample_at=sample_at,
            )
        )
    return conflicts


def format_conflict_message(conflicts: Sequence[ConflictInfo]) -> str:
    """Build a human-readable message for the first conflict."""
    first = conflicts[0]
    sample = first.sample_at.strftime("%Y-%m-%d %H:%M")
    message = (
        f'Schedule conflicts with "{first.name}" ({first.cron}); '
        f"next overlap at {sample}"
    )
    if len(conflicts) > 1:
        message += f" (+{len(conflicts) - 1} more)"
    return message
