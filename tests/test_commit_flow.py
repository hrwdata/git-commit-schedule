from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from git_commit_schedule import cli

from .conftest import run_git


def test_commit_command_sets_author_and_committer_dates(
    repo, monkeypatch
) -> None:
    assert cli.main(["setup"]) == 0
    assert cli.main(["enable"]) == 0

    fixed = datetime(2026, 7, 6, 18, 15, tzinfo=ZoneInfo("America/Chicago"))
    monkeypatch.setattr(cli, "next_slot", lambda cfg, state: fixed)

    assert cli.main(["commit", "--", "-m", "scheduled", "--allow-empty"]) == 0
    result = run_git(repo, ["log", "-1", "--format=%aI%x09%cI"])
    author_iso, committer_iso = result.stdout.strip().split("\t")

    assert author_iso == "2026-07-06T18:15:00-05:00"
    assert committer_iso == "2026-07-06T18:15:00-05:00"

