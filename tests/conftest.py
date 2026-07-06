from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def run_git(repo: Path, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.setdefault("GIT_AUTHOR_NAME", "Test User")
    merged_env.setdefault("GIT_AUTHOR_EMAIL", "test")
    merged_env.setdefault("GIT_COMMITTER_NAME", "Test User")
    merged_env.setdefault("GIT_COMMITTER_EMAIL", "test")
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_git(tmp_path, ["init"])
    run_git(tmp_path, ["config", "user.name", "Test User"])
    run_git(tmp_path, ["config", "user.email", "test"])
    monkeypatch.chdir(tmp_path)
    return tmp_path
