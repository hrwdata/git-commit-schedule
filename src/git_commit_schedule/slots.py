from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import Config
from .state import State


INITIAL_JITTER_MAX_MINUTES = 19


def localize(day: date, clock: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, clock, tzinfo=tz)


def format_git_date(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S %z")


def now_in_window(cfg: Config, now: datetime | None = None) -> bool:
    tz = ZoneInfo(cfg.timezone)
    current = now.astimezone(tz) if now else datetime.now(tz)
    start = localize(current.date(), cfg.window_start, tz)
    end = localize(current.date(), cfg.window_end, tz)
    return start <= current <= end


def next_slot(
    cfg: Config,
    state: State,
    *,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> datetime:
    tz = ZoneInfo(cfg.timezone)
    current = now.astimezone(tz) if now else datetime.now(tz)
    randomizer = rng or random.Random()

    if state.slot_cursor:
        previous = datetime.fromisoformat(state.slot_cursor).astimezone(tz)
        candidate = previous + timedelta(
            minutes=randomizer.randint(cfg.min_gap_minutes, cfg.max_gap_minutes)
        )
        candidate_start = localize(candidate.date(), cfg.window_start, tz)
        candidate_end = localize(candidate.date(), cfg.window_end, tz)
        if candidate < candidate_start:
            candidate = candidate_start + timedelta(
                minutes=randomizer.randint(0, INITIAL_JITTER_MAX_MINUTES)
            )
        if candidate > candidate_end:
            next_day = candidate.date() + timedelta(days=1)
            candidate = localize(next_day, cfg.window_start, tz) + timedelta(
                minutes=randomizer.randint(0, INITIAL_JITTER_MAX_MINUTES)
            )
        return candidate

    base_day = current.date()
    if current.time() > cfg.window_end:
        base_day = base_day + timedelta(days=1)
    return localize(base_day, cfg.window_start, tz) + timedelta(
        minutes=randomizer.randint(0, INITIAL_JITTER_MAX_MINUTES)
    )


def timestamp_within_window(iso_value: str, cfg: Config) -> tuple[bool, datetime]:
    tz = ZoneInfo(cfg.timezone)
    moment = datetime.fromisoformat(iso_value).astimezone(tz)
    start = localize(moment.date(), cfg.window_start, tz)
    end = localize(moment.date(), cfg.window_end, tz)
    return start <= moment <= end, moment

