from __future__ import annotations

from pathlib import Path

from git_commit_schedule.config import Config
from git_commit_schedule import windows_tasks


def test_task_name_is_sanitized() -> None:
    task_name = windows_tasks.task_name_for_repo(Path("C:/tmp/My Repo"))
    assert task_name == "git-commit-schedule-My-Repo"


def test_render_scheduled_push_script_contains_expected_command(monkeypatch) -> None:
    monkeypatch.setattr(windows_tasks, "repo_root", lambda: Path("C:/tmp/repo"))
    monkeypatch.setattr(windows_tasks, "ensure_state_dir", lambda: Path("C:/tmp/repo/.git/git-commit-schedule"))
    script = windows_tasks.render_scheduled_push_script(Config(), python_executable="C:/Python310/python.exe")

    assert "git_commit_schedule.cli push --scheduled" in script
    assert "$Repo = 'C:/tmp/repo'" in script
    assert "$Python = 'C:/Python310/python.exe'" in script
