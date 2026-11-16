---
name: orchestrate
description: Implement a ticket as a thin orchestrator. Workers at or above a model floor do the work; outside fill watchers rotate them and pause the orchestrator at its own limit.
disable-model-invocation: true
argument-hint: "<ticket path> | resume <orchestrator log> [MIN_MODEL=opus] [WORKER_LIMIT=200000] [SELF_LIMIT=200000]"
---

# Orchestrate

You are the **orchestrator** of one ticket; **workers** do all the work. You stay thin: you write briefs, read short reports, decide, and keep the **log** current. Code, diffs, and test output reach you only as worker reports.

Args: `MIN_MODEL` is the lowest model tier a worker may run on (default `opus`); `WORKER_LIMIT` and `SELF_LIMIT` are limits on **fill**, the tokens in an agent's context (default `200000` each).

Every file this skill writes lives in `<handoffs>` = `.scratch/<slug>/handoffs/`, where `<slug>` is the feature's kebab-case name, and starts with the ticket id.

## 1. Preflight

1. Record `BASE=$(git rev-parse HEAD)`: the review's fixed point.
2. Create the log at `<handoffs>/<ticket>-orchestrator.md`.
3. Arm the self watcher (see Watchers).

On `resume <log>`, read [references/watchers.md](references/watchers.md) instead.

## 2. Spawning workers

Each worker takes one role: **planner**, **plan reviewer**, **prototyper**, **implementer**, or **fixer**. Every spawn:

- runs in the background, with `model` at `MIN_MODEL` or a stronger tier, matched to the task's difficulty;
- gets a **brief**: the task, **context pointers** (paths to the ticket, plan, and handoff; commit SHAs), and the report shape "Reply in ≤150 words: commits landed, what is open, file pointers". A brief points; it never restates what a pointer holds;
- gets a worker watcher, armed right after the spawn.

Briefs, messages to workers, and handoffs carry the task alone. Fill, limits, and watchers stay your private bookkeeping, measured from outside, so each worker spends its whole attention on the task.

## 3. Plan

Spawn a planner when the ticket leaves design choices open. It writes `<handoffs>/<ticket>-plan.md` and reports its open questions. When the ticket already names its seams, the ticket is the plan.

Then spawn the **plan reviewer**, on every ticket, before any implementer. Its brief is **blind**: the ticket path, the plan path, and "Review per `<this skill's base dir>/references/plan-review.md` into `<handoffs>/<ticket>-plan-review.md`." It never carries the planner's report or your own reading of the plan.

Settle the planner's open questions and the review's items in one pass:

- **break**: a planner folds the plan change. If the ticket was the plan, the planner writes the plan file; record its path in the log as the plan path;
- **prototype**: a prototyper (the `prototype` skill, `isolation: "worktree"`) answers it;
- **owner**, plus any question a prototype cannot answer: ask the user in one message while prototypers run, each as options with your recommendation;
- **note**: fold it or pass it, with a one-line reason in the log.

A planner folds every answer into the plan, keeping each acceptance criterion's test on its real path, so implementers get one settled plan. Then SendMessage the plan reviewer, and re-arm its watcher: "Run the closing check on `<plan path>`." Take what it still holds open to the user. A planner folds each ruling that changes the plan; log each item the user waives, with the reason. There is no second closing check.

Done when the closing check leaves no item open, or each remaining item is folded or waived per the user's ruling.

## 4. Implement

Brief each implementer: "Build test-first with the `tdd` skill at the plan's seams; a slice with no seam in the plan builds straight to a green full suite. Typecheck and run single test files often, the full suite once at the end. Commit to the current branch." Parallel implementers need disjoint files.

Done when every implementer reports its commits and a full suite run after the last commit is green.

## 5. Review

Load `code-review` with the Skill tool and run it from `BASE`. Sort every finding into **fix**, **owner** (needs the user), or **pass**, each with a one-line reason. Spawn one fixer for the fix list.

Done when the fixer reports its commits and a green full suite.

## 6. Close

Report to the user: commits, owner items, and passed findings with reasons. Mark the log closed, TaskStop the self watcher, remove prototyper worktrees, then move the ticket's files to `<handoffs>/.archived/`.

## Watchers

A **worker watcher** rotates its worker at `WORKER_LIMIT`: the worker writes a **handoff** and a successor continues from it. The **self watcher** pauses you at `SELF_LIMIT`. Arm each with Bash `run_in_background`:

    python3 <this skill's base dir>/scripts/fill-watch.py <agentId> <WORKER_LIMIT>   # worker watcher
    python3 <this skill's base dir>/scripts/fill-watch.py self <SELF_LIMIT>          # self watcher

When a worker's completion notification arrives, TaskStop its watcher. When a watcher exits with a line, read [references/watchers.md](references/watchers.md) and act on it.

## The log

Update it at every **boundary** (spawn, report, rotation, decision). It holds what a fresh orchestrator needs to resume after `/clear`: the ticket path, `BASE`, the plan and plan-review paths, each review item's disposition, the args, each worker's agentId, brief, status, and handoff path, the code review's fix/owner/pass list with reasons, and `Next:`.
