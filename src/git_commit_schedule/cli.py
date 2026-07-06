from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime

from . import __version__, git_ops, hooks, state as state_module, validate, windows_tasks
from .config import config_provenance_lines, ensure_local_defaults, load_effective_config, write_repo_config
from .slots import format_git_date, next_slot, now_in_window


def cmd_setup(_args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    hooks.install_repo_hooks()
    ensure_local_defaults()
    state_module.ensure_state_dir()
    if not state_module.state_path().exists():
        state_module.save_state(state_module.State())
    print("git-commit-schedule setup complete")
    print("hooksPath: .githooks")
    cfg = load_effective_config()
    print(f"default timezone: {cfg.timezone}")
    print(f"default window: {cfg.window_start.strftime('%H:%M')} - {cfg.window_end.strftime('%H:%M')}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    ensure_local_defaults()
    hooks.install_repo_hooks()
    write_repo_config(enabled=True, auto_push=bool(args.auto_push), enforce_push=True)
    cfg = load_effective_config()
    print("git-commit-schedule enabled")
    if args.auto_push:
        task_name, script_path = windows_tasks.configure_auto_push(cfg)
        state_module.update_state(task_name=task_name)
        print(f"scheduled task: {task_name}")
        print(f"scheduled script: {script_path}")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    write_repo_config(enabled=False, auto_push=False)
    print("git-commit-schedule disabled")
    if args.remove_task:
        current_state = state_module.load_state()
        if current_state.task_name:
            windows_tasks.remove_task(current_state.task_name)
            state_module.update_state(task_name=None)
            print(f"removed scheduled task: {current_state.task_name}")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    cfg = load_effective_config()
    current_state = state_module.load_state()
    preview = next_slot(cfg, current_state)
    print(f"version: {__version__}")
    print(f"enabled: {cfg.enabled}")
    print(f"timezone: {cfg.timezone}")
    print(f"window: {cfg.window_start.strftime('%H:%M')} - {cfg.window_end.strftime('%H:%M')}")
    print(f"gap: {cfg.min_gap_minutes}-{cfg.max_gap_minutes} minutes")
    print(f"dirty_working_tree: {git_ops.working_tree_dirty()}")
    print(f"state_dirty: {current_state.state_dirty}")
    print(f"next_slot: {preview.isoformat()}")
    print(f"state_file: {state_module.state_path()}")
    print("config_provenance:")
    for line in config_provenance_lines() or ["(no git-commit-schedule config entries found)"]:
        print(f"  {line}")
    if current_state.task_name:
        task_status = windows_tasks.query_task(current_state.task_name)
        print(f"scheduled_task: {current_state.task_name}")
        print(f"task_registered: {bool(task_status)}")
    return 0


def _normalize_commit_args(values: list[str]) -> list[str]:
    if values and values[0] == "--":
        return values[1:]
    return values


def cmd_commit(args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    cfg = load_effective_config()
    if not cfg.enabled:
        raise RuntimeError("git-commit-schedule is disabled; run enable first")
    current_state = state_module.load_state()
    slot = next_slot(cfg, current_state)
    date_string = format_git_date(slot)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_DATE": date_string,
            "GIT_COMMITTER_DATE": date_string,
            "GIT_COMMIT_SCHEDULE_WRAPPER": "1",
        }
    )
    commit_args = _normalize_commit_args(args.commit_args)
    git_ops.run_git(["commit", *commit_args], env=env)
    state_module.update_state(
        slot_cursor=slot.isoformat(),
        last_commit=git_ops.rev_parse("HEAD"),
        state_dirty=False,
    )
    print(f"created commit with scheduled metadata at {date_string}")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    cfg = load_effective_config()
    if args.scheduled and not cfg.enabled:
        print("git-commit-schedule is disabled; scheduled push skipped")
        return 0
    if cfg.enforce_push and os.getenv("GIT_COMMIT_SCHEDULE_BYPASS") != "1" and not now_in_window(cfg):
        if args.scheduled:
            print("scheduled push skipped because the approved window has closed")
            return 0
        raise RuntimeError("push blocked outside the approved window")

    remote, branch = git_ops.resolve_push_target(args.remote, args.branch)
    now = datetime.now().astimezone()
    state_module.update_state(last_push_attempt=now.isoformat())
    git_ops.run_git(["push", remote, branch])
    state_module.update_state(last_push_success=datetime.now().astimezone().isoformat())
    print(f"pushed {branch} to {remote}")

    if args.create_pr:
        result = subprocess.run(
            ["gh", "pr", "create", "--fill"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "gh pr create failed"
            raise RuntimeError(detail)
        print("created pull request")

    if args.workflow:
        result = subprocess.run(
            ["gh", "workflow", "run", args.workflow, "--ref", branch],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "gh workflow run failed"
            raise RuntimeError(detail)
        print(f"dispatched workflow: {args.workflow}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    cfg = load_effective_config()
    report = validate.run_local_validation(cfg)
    if args.online:
        online_report = validate.run_online_validation()
        report.messages.extend(online_report.messages)
    for message in report.messages:
        print(f"{message.level}: {message.message}")
    return 0 if report.ok else 1


def cmd_reset_state(_args: argparse.Namespace) -> int:
    git_ops.ensure_git_repo()
    state_module.reset_state()
    print(f"state reset: {state_module.state_path()}")
    return 0


def _run_internal_command(argv: list[str]) -> int | None:
    if not argv:
        return None
    command = argv[0]
    if command == "_hook-post-commit":
        return hooks.handle_post_commit()
    if command == "_hook-pre-push":
        return hooks.handle_pre_push(sys.stdin.read().splitlines())
    if command == "_hook-post-rewrite":
        return hooks.handle_post_rewrite(argv[1:])
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="git-commit-schedule")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="install hooks and initialize local state")
    setup_parser.set_defaults(func=cmd_setup)

    enable_parser = subparsers.add_parser("enable", help="enable repo-local scheduling")
    enable_parser.add_argument("--auto-push", action="store_true", help="register a Windows scheduled push task")
    enable_parser.set_defaults(func=cmd_enable)

    disable_parser = subparsers.add_parser("disable", help="disable repo-local scheduling")
    disable_parser.add_argument("--remove-task", action="store_true", help="remove the Windows scheduled task if present")
    disable_parser.set_defaults(func=cmd_disable)

    status_parser = subparsers.add_parser("status", help="show current status and config provenance")
    status_parser.set_defaults(func=cmd_status)

    for name in ("commit", "schedule"):
        commit_parser = subparsers.add_parser(name, help="create a commit with scheduled metadata")
        commit_parser.add_argument("commit_args", nargs=argparse.REMAINDER)
        commit_parser.set_defaults(func=cmd_commit)

    push_parser = subparsers.add_parser("push", help="push within the approved window")
    push_parser.add_argument("--remote", help="remote to push to")
    push_parser.add_argument("--branch", help="branch to push")
    push_parser.add_argument("--create-pr", action="store_true", help="create a pull request after a successful push")
    push_parser.add_argument("--workflow", help="dispatch a workflow after a successful push")
    push_parser.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)
    push_parser.set_defaults(func=cmd_push)

    validate_parser = subparsers.add_parser("validate", help="validate local configuration and unpublished commits")
    validate_parser.add_argument("--online", action="store_true", help="also validate GitHub CLI authentication")
    validate_parser.set_defaults(func=cmd_validate)

    reset_parser = subparsers.add_parser("reset-state", help="reset local scheduling state")
    reset_parser.set_defaults(func=cmd_reset_state)
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    internal_result = _run_internal_command(args_list)
    if internal_result is not None:
        return internal_result

    parser = build_parser()
    args = parser.parse_args(args_list)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("git-commit-schedule: interrupted", file=sys.stderr)
        return 130
    except (
        git_ops.GitCommandError,
        RuntimeError,
        subprocess.SubprocessError,
        OSError,
        ValueError,
    ) as exc:
        print(f"git-commit-schedule: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
