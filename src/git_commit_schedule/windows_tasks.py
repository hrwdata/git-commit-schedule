from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import Config, format_hhmm
from .git_ops import repo_root
from .state import ensure_state_dir, scheduled_push_script_path


def require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows Task Scheduler support is only available on Windows")


def sanitize_task_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "repo"


def task_name_for_repo(root: Path | None = None) -> str:
    repo_name = sanitize_task_name((root or repo_root()).name)
    return f"git-commit-schedule-{repo_name}"


def render_scheduled_push_script(cfg: Config, *, python_executable: str | None = None) -> str:
    ensure_state_dir()
    root = repo_root()
    exe = python_executable or sys.executable
    root_text = root.as_posix()
    exe_text = Path(exe).as_posix()
    max_delay_seconds = int(
        (
            datetime.combine(datetime.today(), cfg.window_end)
            - datetime.combine(datetime.today(), cfg.window_start)
        ).total_seconds()
    )
    return (
        "$ErrorActionPreference = 'Stop'\n"
        f"$Repo = '{root_text}'\n"
        f"$Python = '{exe_text}'\n"
        f"$MaxDelaySeconds = {max_delay_seconds}\n"
        "Set-Location $Repo\n"
        "if ($MaxDelaySeconds -gt 0) {\n"
        "  $Delay = Get-Random -Minimum 0 -Maximum ($MaxDelaySeconds + 1)\n"
        "  Start-Sleep -Seconds $Delay\n"
        "}\n"
        "& $Python -m git_commit_schedule.cli push --scheduled\n"
    )


def write_scheduled_push_script(cfg: Config) -> Path:
    path = scheduled_push_script_path()
    path.write_text(render_scheduled_push_script(cfg), encoding="utf-8")
    return path


def register_task(task_name: str, script_path: Path, start_time: str) -> None:
    require_windows()
    command = [
        "schtasks.exe",
        "/Create",
        "/TN",
        task_name,
        "/SC",
        "DAILY",
        "/ST",
        start_time,
        "/TR",
        f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{script_path}"',
        "/F",
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "task registration failed"
        raise RuntimeError(detail)


def remove_task(task_name: str) -> None:
    require_windows()
    subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", task_name, "/F"],
        text=True,
        capture_output=True,
        check=False,
    )


def query_task(task_name: str) -> str | None:
    if sys.platform != "win32":
        return None
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", task_name],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def configure_auto_push(cfg: Config) -> tuple[str, Path]:
    require_windows()
    script_path = write_scheduled_push_script(cfg)
    task_name = task_name_for_repo()
    register_task(task_name, script_path, format_hhmm(cfg.window_start))
    return task_name, script_path
