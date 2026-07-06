from __future__ import annotations

import os
import sys

from . import git_ops, state as state_module, validate
from .config import load_effective_config
from .slots import format_git_date, next_slot, now_in_window


def _render_hook_template(command: str) -> str:
    return f"""#!/bin/sh
set -eu

GIT_DIR=$(git rev-parse --git-dir)
PYTHON_FILE="$GIT_DIR/git-commit-schedule/python-executable.txt"
if [ -f "$PYTHON_FILE" ]; then
  PYTHON_EXE=$(cat "$PYTHON_FILE")
  if [ -n "$PYTHON_EXE" ] && [ -x "$PYTHON_EXE" ]; then
    exec "$PYTHON_EXE" -m git_commit_schedule.cli {command} "$@"
  fi
fi

if command -v git-commit-schedule >/dev/null 2>&1; then
  exec git-commit-schedule {command} "$@"
fi

if command -v py >/dev/null 2>&1; then
  exec py -3 -m git_commit_schedule.cli {command} "$@"
fi

exec python -m git_commit_schedule.cli {command} "$@"
"""


HOOK_TEMPLATES = {
    "post-commit": _render_hook_template("_hook-post-commit"),
    "pre-push": _render_hook_template("_hook-pre-push"),
    "post-rewrite": _render_hook_template("_hook-post-rewrite"),
}


def install_repo_hooks() -> None:
    hooks_dir = git_ops.repo_root() / ".githooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for hook_name, content in HOOK_TEMPLATES.items():
        (hooks_dir / hook_name).write_text(content, encoding="utf-8", newline="\n")
    state_module.write_runtime_python()
    git_ops.git_config_set("core.hooksPath", ".githooks", local_only=True)


def _warn(message: str) -> None:
    print(f"git-commit-schedule: {message}", file=sys.stderr)


def handle_post_commit() -> int:
    if os.getenv("GIT_COMMIT_SCHEDULE_WRAPPER") == "1":
        return 0
    if os.getenv("GIT_COMMIT_SCHEDULE_POST_COMMIT") == "1":
        return 0

    cfg = load_effective_config()
    if not cfg.enabled or not cfg.fallback_hook:
        return 0

    lock_path = state_module.lock_path()
    if lock_path.exists():
        return 0

    if git_ops.is_merge_commit() and not cfg.allow_merge_rewrite:
        _warn("skipping fallback rewrite for merge commit")
        return 0
    if git_ops.is_commit_signed() and not cfg.allow_signed_rewrite:
        _warn("skipping fallback rewrite for signed commit")
        return 0
    if git_ops.head_is_published():
        _warn("skipping fallback rewrite because HEAD is already published")
        return 0

    state_module.ensure_state_dir()
    lock_path.write_text("locked\n", encoding="utf-8")
    try:
        current_state = state_module.load_state()
        slot = next_slot(cfg, current_state)
        date_string = format_git_date(slot)
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_DATE": date_string,
                "GIT_COMMITTER_DATE": date_string,
                "GIT_COMMIT_SCHEDULE_POST_COMMIT": "1",
                "GIT_COMMIT_SCHEDULE_IGNORE_POST_REWRITE": "1",
            }
        )
        git_ops.run_git(
            ["commit", "--amend", "--no-edit", "--allow-empty", f"--date={date_string}"],
            env=env,
        )
        state_module.update_state(
            slot_cursor=slot.isoformat(),
            last_commit=git_ops.rev_parse("HEAD"),
            state_dirty=False,
        )
        _warn(f"dated plain git commit at {date_string}")
        return 0
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _parse_pre_push_lines(lines: list[str]) -> list[tuple[str, str, str, str]]:
    updates: list[tuple[str, str, str, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 4:
            raise RuntimeError(f"unexpected pre-push input: {stripped}")
        updates.append((parts[0], parts[1], parts[2], parts[3]))
    return updates


def handle_pre_push(lines: list[str]) -> int:
    cfg = load_effective_config()
    if not cfg.enabled or not cfg.enforce_push:
        return 0
    if os.getenv("GIT_COMMIT_SCHEDULE_BYPASS") == "1":
        return 0

    if not now_in_window(cfg):
        _warn(
            "blocked push outside the approved window; rerun during the window or set "
            "GIT_COMMIT_SCHEDULE_BYPASS=1 for an explicit override"
        )
        return 1

    updates = _parse_pre_push_lines(lines)
    report = validate.validate_push_updates(cfg, updates)
    for message in report.messages:
        stream = sys.stderr if message.level != "info" else sys.stdout
        print(f"{message.level}: {message.message}", file=stream)
    return 0 if report.ok else 1


def handle_post_rewrite(arguments: list[str]) -> int:
    if os.getenv("GIT_COMMIT_SCHEDULE_IGNORE_POST_REWRITE") == "1":
        return 0
    if arguments and arguments[0] not in {"amend", "rebase"}:
        return 0
    state_module.mark_dirty_state()
    _warn("rewrite detected; run validate or reset-state before pushing")
    return 0
