# Watcher events and resume

A watcher stays silent until it exits with one line:

- `ROTATE agent=… fill=…`: rotate that worker. Moot when the worker already completed: workers often peak past the limit on their final turn.
- `SELF fill=…`: pause.
- `ERROR …`: it cannot measure. Re-arm it once. On a second `ERROR`, tell the user in one line and go on.

## Rotation

Handoff → kill → respawn:

1. SendMessage the worker: "Pause the task at the next clean point: commit finished work, write a handoff to `<handoffs>/<ticket>-<role>-<n>.md` (done, in flight, next step, open questions, file pointers), and reply with its path only."
2. On its reply, TaskStop it if it is still running.
3. Spawn the **successor** with the predecessor's brief plus "Continue from the handoff at `<path>`." Arm its watcher.

## Pause

Spawn nothing new, bring the log current, and tell the user "Orchestrator at <fill> ≥ <SELF_LIMIT>. Log: <path>. In flight: <workers>." Then end your turn and wait for the user's instruction. Notifications that arrive meanwhile get one log line each and no action. Re-arm the self watcher only at a new limit the user names.

## Resume

On `resume <log>`: arm the self watcher, then take `BASE` and the rest from the log. For each worker the log shows in flight, run `fill-watch.py --now <agentId>`. If its `age` is small, the worker still runs: re-arm its watcher. Otherwise, rotate it: a quiet worker may sit in a long tool call, and rotation leaves a handoff either way. Continue at the log's `Next:`.
