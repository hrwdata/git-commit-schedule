from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys

from . import git_ops


SCHEMA_VERSION = 1


@dataclass
class State:
    schema_version: int = SCHEMA_VERSION
    slot_cursor: str | None = None
    last_commit: str | None = None
    last_push_attempt: str | None = None
    last_push_success: str | None = None
    task_name: str | None = None
    state_dirty: bool = False


def state_dir() -> Path:
    return git_ops.git_dir() / "git-commit-schedule"


def state_path() -> Path:
    return state_dir() / "state.json"


def lock_path() -> Path:
    return state_dir() / "lock"


def scheduled_push_script_path() -> Path:
    return state_dir() / "run-scheduled-push.ps1"


def python_path_file() -> Path:
    return state_dir() / "python-executable.txt"


def ensure_state_dir() -> Path:
    path = state_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_runtime_python() -> Path:
    ensure_state_dir()
    path = python_path_file()
    path.write_text(Path(sys.executable).as_posix() + "\n", encoding="utf-8")
    return path


def load_state() -> State:
    path = state_path()
    if not path.exists():
        return State()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return State()
    return State(
        schema_version=payload.get("schema_version", SCHEMA_VERSION),
        slot_cursor=payload.get("slot_cursor"),
        last_commit=payload.get("last_commit"),
        last_push_attempt=payload.get("last_push_attempt"),
        last_push_success=payload.get("last_push_success"),
        task_name=payload.get("task_name"),
        state_dirty=bool(payload.get("state_dirty", False)),
    )


def save_state(state: State) -> None:
    ensure_state_dir()
    state_path().write_text(
        json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def update_state(**changes: object) -> State:
    state = load_state()
    for key, value in changes.items():
        if not hasattr(state, key):
            raise AttributeError(f"unknown state field: {key}")
        setattr(state, key, value)
    save_state(state)
    return state


def clear_dirty_state() -> State:
    return update_state(state_dirty=False)


def mark_dirty_state() -> State:
    return update_state(state_dirty=True)


def reset_state(*, preserve_task_name: bool = True) -> State:
    current = load_state()
    reset = State(task_name=current.task_name if preserve_task_name else None)
    save_state(reset)
    try:
        lock_path().unlink()
    except FileNotFoundError:
        pass
    return reset
