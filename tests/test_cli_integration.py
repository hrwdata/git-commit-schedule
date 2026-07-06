from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .conftest import ROOT, run_git


def run_cli(
    repo: Path,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    paths = [str(ROOT / "src")]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env.setdefault("GIT_AUTHOR_NAME", "Test User")
    env.setdefault("GIT_AUTHOR_EMAIL", "test")
    env.setdefault("GIT_COMMITTER_NAME", "Test User")
    env.setdefault("GIT_COMMITTER_EMAIL", "test")
    return subprocess.run(
        [sys.executable, "-m", "git_commit_schedule.cli", *args],
        cwd=repo,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def test_cli_subprocess_temp_repo_workflow(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, ["init"])
    run_git(repo, ["config", "user.name", "Test User"])
    run_git(repo, ["config", "user.email", "test"])

    run_cli(repo, "setup")
    run_cli(repo, "enable")

    (repo / "note.txt").write_text("first\n", encoding="utf-8")
    run_git(repo, ["add", "note.txt"])
    run_cli(repo, "commit", "--", "-m", "first scheduled commit")

    (repo / "note.txt").write_text("first\nsecond\n", encoding="utf-8")
    run_git(repo, ["add", "note.txt"])
    run_cli(repo, "commit", "--", "-m", "second scheduled commit")

    log_output = run_git(repo, ["log", "--reverse", "-2", "--format=%H%x09%aI%x09%cI"]).stdout
    rows = [line.split("\t") for line in log_output.splitlines() if line.strip()]
    assert len(rows) == 2

    previous_author = None
    previous_committer = None
    for _sha, author_iso, committer_iso in rows:
        author_local = author_iso[11:16]
        committer_local = committer_iso[11:16]
        assert "17:30" <= author_local <= "21:30"
        assert "17:30" <= committer_local <= "21:30"
        if previous_author is not None:
            assert author_iso >= previous_author
            assert committer_iso >= previous_committer
        previous_author = author_iso
        previous_committer = committer_iso

    state_before = json.loads((repo / ".git" / "git-commit-schedule" / "state.json").read_text(encoding="utf-8"))
    assert state_before["slot_cursor"]
    assert state_before["last_commit"]

    run_git(repo, ["config", "--local", "git-commit-schedule.windowStart", "23:58"])
    run_git(repo, ["config", "--local", "git-commit-schedule.windowEnd", "23:59"])
    head = run_git(repo, ["rev-parse", "HEAD"]).stdout.strip()
    hook_result = run_cli(
        repo,
        "_hook-pre-push",
        "origin",
        "local",
        check=False,
        input_text=f"refs/heads/main {head} refs/heads/main 0000000000000000000000000000000000000000\n",
    )
    assert hook_result.returncode == 1
    assert "blocked push outside the approved window" in hook_result.stderr

    run_cli(repo, "reset-state")
    state_after = json.loads((repo / ".git" / "git-commit-schedule" / "state.json").read_text(encoding="utf-8"))
    assert state_after["slot_cursor"] is None
    assert state_after["last_commit"] is None
    assert run_git(repo, ["config", "--local", "--get", "git-commit-schedule.enabled"]).stdout.strip() == "true"
