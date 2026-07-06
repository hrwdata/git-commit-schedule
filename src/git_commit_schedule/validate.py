from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime

from .config import Config
from . import git_ops, state as state_module
from .slots import timestamp_within_window


@dataclass
class ValidationMessage:
    level: str
    message: str


@dataclass
class ValidationReport:
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(message.level != "error" for message in self.messages)

    def add(self, level: str, message: str) -> None:
        self.messages.append(ValidationMessage(level, message))


def _check_commit_record(
    report: ValidationReport,
    cfg: Config,
    sha: str,
    author_iso: str,
    committer_iso: str,
) -> tuple[datetime, datetime]:
    author_ok, author_local = timestamp_within_window(author_iso, cfg)
    committer_ok, committer_local = timestamp_within_window(committer_iso, cfg)
    if not author_ok:
        report.add(
            "error",
            f"{sha}: author date {author_local.isoformat()} is outside the approved window",
        )
    if not committer_ok:
        report.add(
            "error",
            f"{sha}: committer date {committer_local.isoformat()} is outside the approved window",
        )
    return author_local, committer_local


def validate_commit_revisions(cfg: Config, revisions: list[str]) -> ValidationReport:
    report = ValidationReport()
    if not revisions:
        report.add("info", "no unpublished commits to validate")
        return report

    previous_author: datetime | None = None
    previous_committer: datetime | None = None

    for rev in revisions:
        sha, author_iso, committer_iso = git_ops.commit_metadata(rev)
        author_local, committer_local = _check_commit_record(
            report, cfg, sha, author_iso, committer_iso
        )
        if previous_author and author_local < previous_author:
            report.add("error", f"{sha}: author dates are not monotone nondecreasing")
        if previous_committer and committer_local < previous_committer:
            report.add("error", f"{sha}: committer dates are not monotone nondecreasing")
        previous_author = author_local
        previous_committer = committer_local
    return report


def validate_push_updates(cfg: Config, updates: list[tuple[str, str, str, str]]) -> ValidationReport:
    report = ValidationReport()
    all_revisions: list[str] = []
    for local_ref, local_oid, _remote_ref, remote_oid in updates:
        if local_ref == "(delete)" or local_oid == git_ops.ZERO_OID:
            continue
        all_revisions.extend(git_ops.commits_for_push(local_oid, remote_oid))
    seen: set[str] = set()
    unique_revisions = [rev for rev in all_revisions if not (rev in seen or seen.add(rev))]
    nested = validate_commit_revisions(cfg, unique_revisions)
    report.messages.extend(nested.messages)
    return report


def run_local_validation(cfg: Config) -> ValidationReport:
    report = ValidationReport()
    hooks_path = git_ops.git_config_get("core.hooksPath")
    if hooks_path != ".githooks":
        report.add("error", "core.hooksPath is not set to .githooks")
    for hook_name in ("post-commit", "pre-push", "post-rewrite"):
        if not (git_ops.repo_root() / ".githooks" / hook_name).exists():
            report.add("error", f"missing hook file: .githooks/{hook_name}")

    revisions = git_ops.unpublished_commits()
    report.messages.extend(validate_commit_revisions(cfg, revisions).messages)

    current_state = state_module.load_state()
    if current_state.state_dirty and git_ops.head_is_published():
        report.add("error", "rewrite state is dirty and HEAD is already published")
    elif current_state.state_dirty:
        report.add("warning", "rewrite state is dirty; clearing after successful validation")

    if report.ok and current_state.state_dirty:
        state_module.clear_dirty_state()
        report.add("info", "rewrite state cleared")
    return report


def run_online_validation() -> ValidationReport:
    report = ValidationReport()
    result = subprocess.run(
        ["gh", "auth", "status", "--active", "--hostname", "github.com"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "gh auth status failed"
        report.add("error", f"GitHub CLI authentication check failed: {detail}")
    else:
        report.add("info", "GitHub CLI authentication is active for github.com")
    return report
