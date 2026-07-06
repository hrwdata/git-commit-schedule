from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


ZERO_OID = "0" * 40


@dataclass
class GitCommandError(RuntimeError):
    args_run: list[str]
    returncode: int
    stderr: str
    stdout: str

    def __str__(self) -> str:
        detail = self.stderr.strip() or self.stdout.strip() or "git command failed"
        command = " ".join(self.args_run)
        return f"{detail} ({command})"


def run_git(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise GitCommandError(["git", *args], result.returncode, result.stderr, result.stdout)
    return result


def git_stdout(args: list[str], *, cwd: str | Path | None = None) -> str:
    return run_git(args, cwd=cwd).stdout.strip()


def ensure_git_repo() -> None:
    result = run_git(["rev-parse", "--is-inside-work-tree"], check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError("not inside a Git working tree")


def repo_root() -> Path:
    ensure_git_repo()
    return Path(git_stdout(["rev-parse", "--show-toplevel"])).resolve()


def git_dir() -> Path:
    ensure_git_repo()
    return Path(git_stdout(["rev-parse", "--git-dir"])).resolve()


def rev_parse(name: str) -> str:
    return git_stdout(["rev-parse", name])


def head_exists() -> bool:
    return run_git(["rev-parse", "--verify", "HEAD"], check=False).returncode == 0


def current_branch() -> str | None:
    result = run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    branch = result.stdout.strip()
    return branch or None


def upstream_ref() -> str | None:
    result = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], check=False)
    value = result.stdout.strip()
    return value or None


def branch_remote(branch: str) -> str | None:
    return git_config_get(f"branch.{branch}.remote")


def remote_exists(name: str) -> bool:
    return run_git(["remote", "get-url", name], check=False).returncode == 0


def resolve_push_target(remote: str | None, branch: str | None) -> tuple[str, str]:
    resolved_branch = branch or current_branch()
    if not resolved_branch:
        raise RuntimeError("cannot determine the current branch; specify --branch explicitly")
    resolved_remote = remote
    if not resolved_remote:
        upstream = upstream_ref()
        if upstream and "/" in upstream:
            resolved_remote = upstream.split("/", 1)[0]
        else:
            resolved_remote = branch_remote(resolved_branch) or "origin"
    if not remote_exists(resolved_remote):
        raise RuntimeError(
            f"remote '{resolved_remote}' does not exist; add a remote or pass --remote explicitly"
        )
    return resolved_remote, resolved_branch


def parent_count(rev: str = "HEAD") -> int:
    if not head_exists():
        return 0
    fields = git_stdout(["rev-list", "--parents", "-n", "1", rev]).split()
    return max(0, len(fields) - 1)


def is_merge_commit(rev: str = "HEAD") -> bool:
    return parent_count(rev) > 1


def is_commit_signed(rev: str = "HEAD") -> bool:
    if not head_exists():
        return False
    content = git_stdout(["cat-file", "-p", rev])
    return any(line.startswith("gpgsig ") for line in content.splitlines())


def head_is_published() -> bool:
    upstream = upstream_ref()
    if not upstream or not head_exists():
        return False
    result = run_git(["merge-base", "--is-ancestor", "HEAD", upstream], check=False)
    return result.returncode == 0


def unpublished_commits() -> list[str]:
    if not head_exists():
        return []
    upstream = upstream_ref()
    if upstream:
        output = git_stdout(["rev-list", f"{upstream}..HEAD"])
    else:
        output = git_stdout(["rev-list", "HEAD", "--not", "--remotes"])
    commits = [line.strip() for line in output.splitlines() if line.strip()]
    commits.reverse()
    return commits


def commits_for_push(local_oid: str, remote_oid: str) -> list[str]:
    if not local_oid or local_oid == ZERO_OID:
        return []
    if remote_oid and remote_oid != ZERO_OID:
        output = git_stdout(["rev-list", f"{remote_oid}..{local_oid}"])
    else:
        output = git_stdout(["rev-list", local_oid, "--not", "--remotes"])
    commits = [line.strip() for line in output.splitlines() if line.strip()]
    commits.reverse()
    return commits


def commit_metadata(rev: str) -> tuple[str, str, str]:
    output = git_stdout(["log", "-1", "--format=%H%x09%aI%x09%cI", rev])
    sha, author_iso, committer_iso = output.split("\t")
    return sha, author_iso, committer_iso


def git_config_get(key: str, *, local_only: bool = False) -> str | None:
    args = ["config"]
    if local_only:
        args.append("--local")
    args.extend(["--get", key])
    result = run_git(args, check=False)
    value = result.stdout.strip()
    return value or None


def git_config_set(key: str, value: str, *, local_only: bool = True) -> None:
    args = ["config"]
    if local_only:
        args.append("--local")
    args.extend([key, value])
    run_git(args)


def git_config_entries(pattern: str) -> list[str]:
    result = run_git(
        ["config", "--show-origin", "--show-scope", "--get-regexp", pattern],
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def working_tree_dirty() -> bool:
    result = run_git(["status", "--porcelain"], check=False)
    return bool(result.stdout.strip())

