---
name: backend-harness
description: Use when autonomously implementing a backend feature plan with enforced quality gates — drives an outer loop (state persistence, backend evaluation, graduated re-evaluation, tiered mutation gating, oscillation detection, iteration cap) over superpowers subagent-driven-development.
---

## Overview

This skill is the **outer loop** of the backend-harness orchestration pipeline.

`superpowers:subagent-driven-development` is the **inner loop** — it handles the implement → spec review → quality review cycle for each task in an isolated worktree. This skill drives that inner loop from the outside: managing state, evaluating results, detecting failure patterns, gating on mutation quality, and escalating when autonomous progress is no longer possible.

**Structural bias elimination:** The implementer (inner loop) **never sees evaluator output**. The `prompts/backend-evaluator.md` subagent runs independently and reports to the orchestrator only. Evaluation feedback never flows back into the implementer's context — this prevents the evaluator's framing from biasing subsequent fix attempts.

**Compaction resilience:** State is persisted to `plans/harness-state.json` after **every step**. On context compaction or session restart, the orchestrator reads this file, inspects the `phase` field, and resumes from exactly where it left off. Never hold critical run state in memory only.

See `references/state-schema.md` for the canonical state schema — all field names, phase values, task statuses, escalation shape, and write discipline are defined there.

---

## Preflight

Run these three checks before entering the loop. Stop immediately with the stated message if any check fails.

### a) Superpowers dependency check

The `superpowers` plugin is required. This skill invokes `superpowers:subagent-driven-development`, `superpowers:using-git-worktrees`, and `superpowers:finishing-a-development-branch`. Without it, the inner loop cannot run.

Check that the superpowers plugin is installed. If it is not:

> "superpowers plugin is required. Install it first, then re-run /harness-implement."

### b) Config check

The `harness.config.json` must exist in the current working directory (the target repository root). It declares the commands the orchestrator will call — unit tests, integration tests, mutation testing, and API verification. The orchestrator will not proceed without it.

If `harness.config.json` is absent:

> "No harness.config.json found. Copy templates/harness.config.json from the plugin into your repo and edit it for your stack. See references/stack-config.md."

### c) Plan check

At least one `plans/*.md` file must exist in the current working directory. The plan drives the entire run.

If no plan file is found under `plans/`:

> "No plan found under plans/. Run /harness-brainstorm first to create a spec/plan, then re-run /harness-implement."

---

## Outer Loop Procedure

### Step 1: Resume Check

Read `plans/harness-state.json` if it exists.

- If `phase` is `escalated`: tell the user — "Previous run ended in escalation: [escalation.reason]. Review plans/harness-state.json for details. To restart, delete plans/harness-state.json." — and **stop**.
- If `phase` is `done`: the run is already complete. Tell the user and stop.
- If `phase` is `implement`, `evaluate`, or `fix`: resume at that phase — skip all prior steps.
  - `phase=fix` → resume at **Step 5** (Backend Evaluation) — the fix was already applied; re-evaluate.
- If `phase` is `brief`: Step 2 (worktree) did not yet complete. Resume from **Step 2**, not Step 3.
- If no state file exists: start fresh. Generate a new `runId` (UUID v4), set `phase=brief`, set `createdAt` and `updatedAt` to the current ISO 8601 timestamp, initialise `tasks`, `failureHistory`, `iterations`, `escalation`, and `planPath` per `references/state-schema.md`. Set `planPath` to `"plans/<matched-plan-filename>.md"` using the plan file located during the Preflight plan check. Persist.

State reference: `references/state-schema.md` — Section 3 (Full Schema) and Section 5 (Write Discipline).

Persist after this step: `phase=brief` (if fresh start) or the resumed phase value.

### Step 2: Worktree

Invoke `superpowers:using-git-worktrees` to create an isolated git worktree for this run. All implementation and evaluation work happens in this worktree — the main branch is never touched.

Record the absolute path returned by the worktree creation in `state.worktree`.

Persist: `state.worktree` updated, **`phase=implement`**. Setting `phase=implement` here (rather than leaving it as `brief`) ensures that if the session is interrupted after the worktree is created, Step 1's resume logic jumps directly to Step 3 — not back into Step 2 again.

### Step 3: Brief Gate (Conditional)

Determine whether the target repository is a **non-trivial existing codebase**. A codebase is non-trivial when it has pre-existing source files beyond what the plan will create — i.e., it is NOT a greenfield or empty repo. Concrete signal: if source directories (`src/`, `lib/`, `app/`, or equivalent) exist and contain files unrelated to the current plan, the codebase is non-trivial.

**If non-trivial:**
- Dispatch a subagent using `prompts/context-brief.md`. Provide: `worktree` (absolute path) and `spec` (the plan file contents, for reference only).
- The subagent will write `plans/context-brief.md` and return `Status: DONE` with a one-line summary.
- Set `state.briefSkipped=false` and `state.contextBriefPath="plans/context-brief.md"`.

**If trivial / greenfield:**
- Set `state.briefSkipped=true`. Do not generate a brief.

Persist: `phase=implement`.

### Step 4: Per-Task Inner Loop

For each task in the plan file:

1. Extract the full task text (spec, acceptance criteria, component name) from the plan file.
2. Set `state.tasks[].status=implementing`. Persist.
3. Dispatch `superpowers:subagent-driven-development` with:
   - Full spec text for this task
   - Context brief contents if `state.briefSkipped=false` (read from `state.contextBriefPath`)
   - The worktree path
4. Handle the subagent's return status:
   - `DONE` → proceed to next task
   - `DONE_WITH_CONCERNS` → log the concerns to the orchestrator's output (tell the user). Do **not** persist them to state — `state.tasks[].title` is the task name and must not be overwritten. Concerns do not block progress — proceed to the next task.
   - `NEEDS_CONTEXT` → provide the requested context and re-dispatch
   - `BLOCKED` → assess the blocking reason; if resolvable, resolve and re-dispatch; if not, escalate: set `state.phase=escalated`, `state.escalation = { "reason": "blocked", "detail": "<blocking reason>", "signatures": [] }`, persist, and tell the user
5. After each task completes: set `state.tasks[].status=passed` and record `state.tasks[].commitSha` from the subagent's commit. Persist.

Persist: `phase=evaluate` after all tasks complete.

### Step 5: Backend Evaluation

Load the evaluation strategy by reading `references/graduated-reevaluation.md`.

Determine the strategy **per failing component** (not via a single max across all components). The failing components are those in `state.evaluation.components` with `status == "fail"` from the prior evaluation, or all components on the first run (when `state.iterations` is empty).

For each failing component, apply the per-component rule from `references/graduated-reevaluation.md`:

```
for each failing component C:
  if state.iterations[C] == 0:
    → C requires "full" scope  (first failure, no fixes dispatched yet)
  else if state.iterations[C] == 1:
    → C can be "component-scoped"  (one fix dispatched; narrow re-check)
  else if state.iterations[C] == 2:
    → C requires "full" scope  (regression safety net)
  else if state.iterations[C] >= 3:
    → will be caught by the cap check (Step 7); skip here

If ANY failing component requires "full" scope:
  strategy = "full"
  scope = "all"
Else if ALL previously-failing components have iterations[C] == 1:
  strategy = "component-scoped"
  scope = [list of failing component names]
```

Dispatch `prompts/backend-evaluator.md` with:
- `worktree` — absolute worktree path from `state.worktree`
- `config` — the parsed `harness.config.json` (commands: unit, integration, apiVerify)
- `strategy` — `"full"` or `"component-scoped"`
- `scope` — `"all"` when strategy is `"full"`, or the array of failing component names when strategy is `"component-scoped"`

Parse the evaluator's JSON response (field: `results[]`).

**If the response contains an `error` field and empty `results`:** this is a tooling failure, not a test failure.
- Set `state.phase = "escalated"`
- Set `state.escalation = { "reason": "blocked", "detail": "Evaluator tooling error: <error field value>", "signatures": [] }`
- Persist, then tell the user — "Evaluation command failed: [error]. Fix the tooling issue and re-run /harness-implement." — and **stop**.

For each entry in `results` where `status == "fail"`:
- Append entries to `state.failureHistory`: `{ iteration: state.iterations[component] ?? 0, signature: sig, component: component }` for each signature in `results[].signatures`
- Update `state.evaluation.components[component] = { status: "fail", lastRun: <now ISO 8601> }`

For each entry in `results` where `status == "pass"`:
- Update `state.evaluation.components[component] = { status: "pass", lastRun: <now ISO 8601> }`

Set `state.evaluation.lastStrategy = strategy`.

If `overall == "pass"`: proceed to **Step 9** (Mutation Gate).

If `overall == "fail"`: set `state.phase=fix`. Proceed to **Step 6** (Oscillation Check).

Persist after evaluation.

### Step 6: Oscillation Check

**This step runs before the cap check (Step 7).**

Per `references/oscillation-detection.md`: for each failure signature in this iteration's `results`, check the `state.failureHistory` for the current `runId`:

1. Was this signature present at some prior iteration N? (present in `failureHistory` with that signature)
2. Was it absent in an intermediate iteration N+1? (no `failureHistory` entry with that signature at iteration N+1)
3. Does it reappear now at iteration N+2 or later?

If all three conditions hold for any signature: **oscillation detected**.

On oscillation detection:
- Set `state.phase=escalated`
- Set `state.escalation = { "reason": "oscillation", "detail": "<which components cycle, e.g. OrderService <-> PaymentService>", "signatures": ["<sig1>", "<sig2>", ...] }`
- Persist (write to temp file, then rename — see `references/state-schema.md` Section 5)
- Tell the user:

> "Oscillation detected — [components] are cycling. This is a coupling problem, not a fixable bug. Review plans/harness-state.json for the failure history. Human architectural judgment required."

**STOP.**

### Step 7: Cap Check

For each component that has failing tests in the current evaluation results:

Check: `state.iterations[component] >= 3`

If the cap is reached for any component:
- Set `state.phase=escalated`
- Set `state.escalation = { "reason": "cap_exceeded", "detail": "<component> reached 3 fix iterations without passing", "signatures": [<all failing signatures for that component>] }`
- Persist
- Tell the user:

> "3-iteration cap reached for [component]. Further autonomous attempts are likely to compound the problem. Review plans/harness-state.json and fix manually."

**STOP.**

### Step 8: Fix

For each failing component that has not hit the 3-iteration cap:

1. Increment `state.iterations[component]` (initialise to 1 if not yet set). Persist.
2. Dispatch `prompts/fix-agent.md` with:
   - `worktree` — absolute path from `state.worktree`
   - `component` — the component name
   - `signatures` — the array of failing signatures for this component from the current evaluation results
   - `spec` — the relevant section of the plan text describing this component's expected behaviour
   - `commands` — unit and integration test commands from `harness.config.json`
3. Parse the fix agent's JSON response:
   - `DONE` → record `commitSha` in state; continue to next failing component
   - `DONE_WITH_CONCERNS` → record `commitSha` and the `concerns` text; continue
   - `NEEDS_CONTEXT` → provide the requested context and re-dispatch once; if still `NEEDS_CONTEXT`, treat as `BLOCKED`
   - `BLOCKED` → set `state.phase=escalated`, `state.escalation = { "reason": "blocked", "detail": concerns, "signatures": [signatures] }`, persist, tell the user
4. If `regressionCheck == "FAIL"`: note the regressions — they will appear in the next evaluation's results and will be caught by the oscillation check if they cycle.

After all failing components have been dispatched to the fix agent:

Set `state.phase=fix`. Persist.

**Loop back to Step 5** (re-evaluate).

### Step 9: Mutation Gate

This step runs once all components report `status == "pass"` in the functional evaluation (unit + integration + apiVerify). The mutation gate validates test quality — it checks that the tests are capable of catching real bugs.

Per `references/mutation-gate.md`:

1. Run `state.commands.mutation` — read this value from `harness.config.json` field `commands.mutation`. Never hardcode the mutation command.
2. For each changed file in the worktree, determine its tier:
   - Match against `harness.config.json` `fileTierGlobs` patterns in order (validators → services → controllers)
   - Use the first matching tier; if no glob matches, default to the lowest configured threshold
3. Apply thresholds from `harness.config.json` `mutationThresholds`:
   - `validators` tier: requires `mutationThresholds.validators`%
   - `services` tier: requires `mutationThresholds.services`%
   - `controllers` tier: requires `mutationThresholds.controllers`%
4. If all changed files meet their tier threshold: the gate **passes** — proceed to **Step 10**.
5. If any changed file is below its tier threshold: the gate **fails**.
   - Treat the failing file's component as a failing component
   - Increment `state.iterations[component]` — mutation failures count against the 3-iteration cap
   - **Cap check:** if `state.iterations[component] >= 3`:
     - Set `state.phase = "escalated"`
     - Set `state.escalation = { "reason": "cap_exceeded", "detail": "<component> reached 3-iteration cap on mutation gate", "signatures": [<failing tier signatures>] }`
     - Persist, tell the user, and **STOP**
   - If cap not yet reached: dispatch `prompts/fix-agent.md` for that component with context: "Component is functionally correct but mutation score is [X]% against required [Y]%. Improve test coverage for edge cases and corner logic paths."
   - Set `state.phase=fix` and loop back to **Step 5** (re-evaluate functional tests, then re-run mutation gate if functional tests still pass)

Persist after mutation gate result: `phase=fix` (looping back to Step 5 after dispatching fix agent), `phase=escalated` (cap reached or tooling error), or `phase=done` (if all tiers pass, proceeding to Step 10).

### Step 10: Done

All functional tests pass (unit + integration + apiVerify) AND the mutation gate passes.

- Set `state.phase=done`. Set `state.updatedAt` to the current ISO 8601 timestamp. Persist.
- Invoke `superpowers:finishing-a-development-branch` to handle merge, PR creation, or cleanup as appropriate.

---

## References / Prompts Index

| Step | File | Purpose |
|---|---|---|
| Preflight b | `templates/harness.config.json` / `references/stack-config.md` | Config validation and command declarations |
| Step 3 | `prompts/context-brief.md` | Context Brief generation for non-trivial codebases |
| Step 4 | superpowers `subagent-driven-development` | Inner per-task implement → review → quality loop |
| Step 5 | `prompts/backend-evaluator.md`, `references/graduated-reevaluation.md` | Functional evaluation and strategy selection |
| Step 6 | `references/oscillation-detection.md` | Oscillation detection across `failureHistory` |
| Step 7 | `references/state-schema.md` | Cap check via `iterations` field |
| Step 8 | `prompts/fix-agent.md` | Targeted fix dispatch per failing component |
| Step 9 | `references/mutation-gate.md` | Tiered mutation score gating |
| Step 10 | superpowers `finishing-a-development-branch` | Branch completion, PR, or merge |

---

## Red Flags

Never do these:

- **Never skip the mutation gate.** Functional pass is not enough — the mutation gate is mandatory.
- **Never let the implementer (inner loop) see evaluator output.** The `backend-evaluator` reports to the orchestrator only; feedback must not flow into `subagent-driven-development` context.
- **Never continue past oscillation.** When oscillation is detected, stop and escalate. Do not consume remaining iterations.
- **Never exceed the 3-iteration cap silently.** If `state.iterations[component] >= 3`, escalate with `reason: "cap_exceeded"` — do not dispatch the fix agent again.
- **Never call hardcoded tool names or test commands.** Always use the commands declared in `harness.config.json` (`commands.unit`, `commands.integration`, `commands.mutation`, `commands.apiVerify`).
- **Never run on main/master without worktree isolation.** All work happens in the isolated worktree created in Step 2. Defer to `superpowers:using-git-worktrees`.
- **Never write `harness-state.json` directly.** Always write to `plans/harness-state.tmp.json` first, then atomically rename: `mv plans/harness-state.tmp.json plans/harness-state.json`. See `references/state-schema.md` Section 5.
- **Never start a fresh run if an incomplete run exists.** Always perform the resume check (Step 1) first. If a state file exists with a non-terminal phase, resume — do not overwrite.
