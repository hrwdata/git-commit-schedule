# Behavior Boundaries

`git-commit-schedule` is designed around Git-supported metadata and local workflow controls.

## Controlled Locally

- Git author date
- Git committer date
- local hook behavior
- local push gating
- local Windows scheduled push execution

## Not Controlled by This Tool

- GitHub push event timestamps
- pull request creation timestamps
- review timestamps
- merge timestamps
- issue or comment timestamps
- GitHub-hosted workflow event timestamps beyond when the real trigger occurs

## Practical Model

- Use `git-commit-schedule commit` to create commits with scheduled metadata.
- Use `git-commit-schedule push` or the Windows scheduled task to create the real push event inside the approved window.
- Use `--create-pr` or `--workflow` only when you want those real GitHub events to occur.
- If the scheduled script starts after the approved window has already closed, it exits without pushing instead of forcing a late push.

## Safety Constraints

- The fallback `post-commit` hook does not rewrite merge commits by default.
- The fallback `post-commit` hook does not rewrite signed commits by default.
- The tool does not automatically rewrite already-pushed commits.
- Local hooks are advisory guardrails because Git exposes `--no-verify`.
