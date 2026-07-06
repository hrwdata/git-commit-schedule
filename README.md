# git-commit-schedule

`git-commit-schedule` is a repo-local Git workflow tool for two things: assigning commit metadata inside a configured local-time window, and gating or scheduling pushes so real GitHub-facing actions happen only when you actually run them.

It stores repository settings in `.git/config`, keeps runtime state under `.git/git-commit-schedule/`, and uses repo-local hooks installed through `core.hooksPath=.githooks`.

## Install

```powershell
python -m pip install -e .[dev]
```

If your environment ships an older `pip`, upgrade it first:

```powershell
python -m pip install --upgrade pip
```

## Quick Start

```powershell
git-commit-schedule setup
git-commit-schedule enable
git-commit-schedule status
git-commit-schedule commit -- -m "Initial scheduled commit" --allow-empty
git-commit-schedule validate
```

Default configuration:

- time zone: `America/Chicago`
- window: `17:30` to `21:30`
- stagger gap: `17` to `41` minutes

## Commands

- `git-commit-schedule setup`
- `git-commit-schedule enable [--auto-push]`
- `git-commit-schedule disable [--remove-task]`
- `git-commit-schedule status`
- `git-commit-schedule commit [git commit args...]`
- `git-commit-schedule schedule [git commit args...]`
- `git-commit-schedule push [--remote R] [--branch B] [--create-pr] [--workflow NAME]`
- `git-commit-schedule validate [--online]`
- `git-commit-schedule reset-state`

## Repo-Local Configuration

Configuration lives under the Git config section `[git-commit-schedule]`.

- `enabled`
- `timezone`
- `windowStart`
- `windowEnd`
- `minGapMinutes`
- `maxGapMinutes`
- `fallbackHook`
- `enforcePush`
- `autoPush`
- `allowMergeRewrite`
- `allowSignedRewrite`

Use `git-commit-schedule status` or `git-commit-schedule validate` to print effective values and provenance.

## Hooks

`setup` installs three repo-local hooks:

- `post-commit`: fallback for plain `git commit`
- `pre-push`: blocks pushes outside the configured window
- `post-rewrite`: marks rewrite state dirty after amend or rebase

`setup` also records the Python interpreter used by repo-local hooks under `.git/git-commit-schedule/`.

These hooks are local guardrails. They can be bypassed with Git's `--no-verify` options.

`pre-push` also accepts `GIT_COMMIT_SCHEDULE_BYPASS=1` for an explicit local override.

## Windows Scheduled Push

`git-commit-schedule enable --auto-push` registers a daily Task Scheduler job at the configured window start time.

The generated task:

- waits a randomized delay inside the remaining window;
- re-checks local time before pushing;
- runs `git-commit-schedule push --scheduled`;
- exits without pushing if the scheduled script starts after the configured window has closed.

More detail: [docs/windows-scheduler.md](docs/windows-scheduler.md)

## GitHub Integration

GitHub integration is opt-in and only triggers real actions after a successful push:

- `--create-pr` runs `gh pr create --fill`
- `--workflow NAME` runs `gh workflow run NAME --ref <branch>`
- `validate --online` checks `gh auth status --active --hostname github.com`

## Limits

- Commit author and committer dates are set locally by Git.
- Push timing depends on when `git push` actually runs, whether manually or from the generated scheduled script.
- Pull request timing depends on when `gh pr create` runs.
- Workflow timing depends on when a real trigger or `gh workflow run` occurs.
- The tool does not alter GitHub server-side push, pull request, review, merge, issue, or workflow event timestamps after the fact.
- The tool does not auto-force-push rewritten history.

## Validation

Recommended local validation:

```powershell
python -m pip install -e .[dev]
python -m pytest
git-commit-schedule setup
git-commit-schedule enable
git log -n 20 --pretty=fuller --date=iso-local
git-commit-schedule validate --online
```

## Known Limits

- merge commits are not rewritten by the fallback hook unless explicitly enabled;
- signed commits are not rewritten by the fallback hook unless explicitly enabled;
- rebases and amends mark local rewrite state dirty until validation or reset;
- Task Scheduler behavior after sleep/wake depends on host configuration;
- scheduling here means commit metadata scheduling plus optional real push scheduling, not delayed local patch queues.

## Documentation

- [docs/behavior-boundaries.md](docs/behavior-boundaries.md)
- [docs/windows-scheduler.md](docs/windows-scheduler.md)
