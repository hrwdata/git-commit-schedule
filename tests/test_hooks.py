from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from git_commit_schedule import hooks
from git_commit_schedule.config import ensure_local_defaults, write_repo_config

from .conftest import run_git


def test_post_commit_rewrites_plain_git_commit(repo, monkeypatch) -> None:
    ensure_local_defaults()
    write_repo_config(enabled=True, enforce_push=True)

    fixed = datetime(2026, 7, 6, 19, 5, tzinfo=ZoneInfo("America/Chicago"))
    monkeypatch.setattr(hooks, "next_slot", lambda cfg, state: fixed)

    run_git(repo, ["commit", "--allow-empty", "--no-verify", "-m", "plain"])
    assert hooks.handle_post_commit() == 0

    result = run_git(repo, ["log", "-1", "--format=%aI%x09%cI"])
    author_iso, committer_iso = result.stdout.strip().split("\t")
    assert author_iso == "2026-07-06T19:05:00-05:00"
    assert committer_iso == "2026-07-06T19:05:00-05:00"


def test_pre_push_blocks_outside_window(repo, monkeypatch) -> None:
    ensure_local_defaults()
    write_repo_config(enabled=True, enforce_push=True)
    monkeypatch.setattr(hooks, "now_in_window", lambda cfg: False)
    result = hooks.handle_pre_push(
        ["refs/heads/main abcdef refs/heads/main 0000000000000000000000000000000000000000"]
    )
    assert result == 1

