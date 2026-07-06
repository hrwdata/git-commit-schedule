from __future__ import annotations

import random
from datetime import datetime
from zoneinfo import ZoneInfo

from git_commit_schedule.config import Config
from git_commit_schedule.slots import next_slot, now_in_window, timestamp_within_window
from git_commit_schedule.state import State


def test_next_slot_rolls_over_after_window_end() -> None:
    cfg = Config()
    state = State(slot_cursor="2026-07-06T21:20:00-05:00")
    slot = next_slot(cfg, state, rng=random.Random(7))
    assert slot.date().isoformat() == "2026-07-07"
    assert slot.hour == 17
    assert 30 <= slot.minute <= 49


def test_now_in_window_handles_daylight_saving_offsets() -> None:
    cfg = Config()
    summer = datetime(2026, 7, 6, 18, 0, tzinfo=ZoneInfo("America/Chicago"))
    winter = datetime(2026, 12, 6, 18, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert now_in_window(cfg, now=summer)
    assert now_in_window(cfg, now=winter)
    assert summer.utcoffset().total_seconds() == -5 * 3600
    assert winter.utcoffset().total_seconds() == -6 * 3600


def test_timestamp_within_window_checks_configured_timezone() -> None:
    cfg = Config()
    ok, local = timestamp_within_window("2026-07-06T18:15:00-05:00", cfg)
    assert ok is True
    assert local.tzinfo == ZoneInfo("America/Chicago")

