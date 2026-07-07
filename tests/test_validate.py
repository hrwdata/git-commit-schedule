from __future__ import annotations

from git_commit_schedule import cli, state as state_module, validate
from git_commit_schedule.config import load_effective_config

from .conftest import run_git


def test_validate_reports_commit_outside_window(repo) -> None:
    assert cli.main(["setup"]) == 0
    assert cli.main(["enable"]) == 0

    env = {
        "GIT_AUTHOR_DATE": "2026-07-06 12:00:00 -0500",
        "GIT_COMMITTER_DATE": "2026-07-06 12:00:00 -0500",
        "GIT_COMMIT_SCHEDULE_POST_COMMIT": "1",
    }
    run_git(
        repo,
        ["commit", "--allow-empty", "--no-verify", "--date=2026-07-06 12:00:00 -0500", "-m", "bad"],
        env=env,
    )

    report = validate.run_local_validation(load_effective_config())
    assert report.ok is False
    assert any("outside the approved window" in message.message for message in report.messages)


def test_validate_reports_commit_outside_window_without_any_remote(repo) -> None:
    assert cli.main(["setup"]) == 0
    assert cli.main(["enable"]) == 0

    env = {
        "GIT_AUTHOR_DATE": "2026-07-06 12:00:00 -0500",
        "GIT_COMMITTER_DATE": "2026-07-06 12:00:00 -0500",
        "GIT_COMMIT_SCHEDULE_POST_COMMIT": "1",
    }
    run_git(
        repo,
        ["commit", "--allow-empty", "--no-verify", "--date=2026-07-06 12:00:00 -0500", "-m", "bad"],
        env=env,
    )

    assert run_git(repo, ["remote"]).stdout.strip() == ""

    report = validate.run_local_validation(load_effective_config())
    assert report.ok is False
    assert any("outside the approved window" in message.message for message in report.messages)


def test_validate_clears_dirty_state_after_success(repo, monkeypatch) -> None:
    assert cli.main(["setup"]) == 0
    assert cli.main(["enable"]) == 0

    env = {
        "GIT_AUTHOR_DATE": "2026-07-06 18:30:00 -0500",
        "GIT_COMMITTER_DATE": "2026-07-06 18:30:00 -0500",
    }
    run_git(
        repo,
        ["commit", "--allow-empty", "--no-verify", "--date=2026-07-06 18:30:00 -0500", "-m", "good"],
        env=env,
    )
    state_module.mark_dirty_state()

    report = validate.run_local_validation(load_effective_config())
    assert report.ok is True
    assert state_module.load_state().state_dirty is False

