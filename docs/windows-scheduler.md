# Windows Scheduler

`git-commit-schedule` uses Windows Task Scheduler for opt-in scheduled pushes.

## What `enable --auto-push` Does

- creates `.git/git-commit-schedule/run-scheduled-push.ps1`
- registers a daily scheduled task at the configured window start time
- stores the generated task name in `.git/git-commit-schedule/state.json`

## Scheduled Script Behavior

The generated script:

1. changes to the repository root;
2. computes a randomized delay within the configured window;
3. sleeps for that delay;
4. invokes `git-commit-schedule push --scheduled`;
5. exits without pushing if the script starts after the configured window has already closed.

## Operational Notes

- Scheduled pushes are local-machine actions. The machine must be available and authenticated for the push to succeed.
- If the task remains installed after `disable`, the tool still refuses to push when the repo-level feature is disabled.
- Remove the task explicitly with `git-commit-schedule disable --remove-task` when you no longer want scheduled execution.
