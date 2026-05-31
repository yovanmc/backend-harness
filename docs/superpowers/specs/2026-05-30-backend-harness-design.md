# Backend Harness — Design Spec

**Date:** 2026-05-30
**Status:** Approved (pending written review)

## Summary

A Claude Code skill that packages an autonomous backend SDLC pipeline with enforced
quality gates. It is a **production-hardening layer on top of superpowers'
`subagent-driven-development`**: superpowers owns the proven inner per-task loop
(implement → spec review → quality review in an isolated worktree); this skill adds
the outer production loop superpowers lacks — disk-state persistence for compaction
resilience, a conditional Context Brief, independent backend evaluation, graduated
re-evaluation, a tiered mutation-testing gate, oscillation detection, and a
3-iteration cap with human escalation.

Scope is **backend only**. There is no frontend/UI path and no Playwright branch.

### Goals

- **Genuinely reusable** — anyone can install and run it on their own backend project.
- **Faithful showcase** — preserves the engineering mechanisms of the original harness
  (the resume pattern), each present only where it earns its keep.
- **Locally testable** — installable via a local plugin marketplace and verifiable
  end-to-end against a committed sample .NET API.

### Non-goals

- Frontend/UI validation, Playwright, frontend unit tests.
- Shipping adapters for many stacks. One **reference stack (.NET)** ships working;
  other stacks are reached by editing declared commands (documented swap points).

## Relationship to superpowers (Approach A — wrapper orchestrator)

Two loops:

- **Outer loop (this skill):** the harness orchestrator. Owns Context Brief, state
  persistence, backend evaluation dispatch, graduated re-evaluation, mutation gate,
  oscillation detection, the 3-iteration cap, and escalation.
- **Inner loop (superpowers):** per implementation task, the orchestrator follows
  `subagent-driven-development` (implementer → spec-compliance review → code-quality
  review) in an isolated git worktree.

The skill **depends on the superpowers plugin** (declared in `plugin.json`) so the
inner loop stays current automatically as superpowers evolves. We do not reimplement
the inner loop.

## Agent model

| Agent | Owner | Role |
|---|---|---|
| **Orchestrator** | this skill | Drives the outer loop, persists state, selects re-eval strategy, detects oscillation, escalates. |
| **Implementer + 2 reviewers** | superpowers | Inner per-task loop. Implementer has no visibility into evaluation results (bias elimination preserved structurally). |
| **Backend Evaluator** | this skill | Independent context. Runs unit + integration + curl/HTTP semantic verification; reports failure signatures. |
| **Fix Agent** | this skill | Spawned conditionally on evaluation failure; targets specific failing components before re-evaluation. |

**Self-evaluation bias elimination** is structural, not a prompting guideline: the
implementer (superpowers inner loop) never sees evaluator output, and the Backend
Evaluator runs in a separate context.

## Repo & packaging structure

The GitHub repo doubles as a local Claude Code plugin marketplace.

```
backend-harness/                          # repo root = marketplace
├── .claude-plugin/
│   └── marketplace.json                  # for `claude plugin marketplace add .`
├── plugins/
│   └── backend-harness/
│       ├── .claude-plugin/
│       │   └── plugin.json                # manifest; declares dependency on superpowers
│       ├── skills/
│       │   └── backend-harness/
│       │       ├── SKILL.md               # orchestrator: the outer loop
│       │       ├── references/
│       │       │   ├── state-schema.md
│       │       │   ├── oscillation-detection.md
│       │       │   ├── graduated-reevaluation.md
│       │       │   ├── mutation-gate.md
│       │       │   └── stack-config.md
│       │       └── prompts/
│       │           ├── context-brief.md
│       │           ├── backend-evaluator.md
│       │           └── fix-agent.md
│       └── commands/
│           ├── harness-brainstorm.md       # /harness-brainstorm
│           └── harness-implement.md         # /harness-implement
├── sample/
│   └── BackendApi/                         # small real .NET API: src + xUnit + Stryker.NET
├── docs/
└── README.md                               # quickstart
```

- `harness.config.json` lives in the **target** project (not the plugin) and declares
  test/mutation/integration commands. Reference stack ships .NET defaults.
- `sample/BackendApi` is the e2e test target, intentionally seeded with weak spots so
  the gates demonstrably fire.

## State persistence

State lives under `plans/` in the target project (no `.beads/` convention).

- `plans/harness-state.json` — run state, written after **every** labeled step so a
  compaction or crash mid-run is fully resumable. The orchestrator reads it on entry
  and resumes at `phase` if a run is incomplete.
- `plans/context-brief.md` — the conditional Context Brief (when generated).
- `plans/<date>-<topic>-plan.md` — the spec/plan from `/harness-brainstorm`.

### `harness-state.json` schema

```json
{
  "runId": "uuid",
  "phase": "brief | implement | evaluate | fix | escalated | done",
  "createdAt": "iso8601",
  "updatedAt": "iso8601",
  "worktree": "/abs/path/to/worktree",
  "briefSkipped": false,
  "contextBriefPath": "plans/context-brief.md",
  "planPath": "plans/2026-05-30-topic-plan.md",
  "tasks": [
    { "id": "t1", "title": "...", "status": "pending|implementing|reviewing|evaluating|passed|failed", "commitSha": "..." }
  ],
  "evaluation": {
    "lastStrategy": "full | component-scoped",
    "components": { "PaymentService": { "status": "pass|fail", "lastRun": "iso8601" } }
  },
  "failureHistory": [
    { "iteration": 1, "signature": "xunit:PaymentTests.Refund_NegativeAmount", "component": "PaymentService" }
  ],
  "iterations": { "PaymentService": 2 },
  "escalation": null
}
```

- `failureHistory` is the oscillation substrate (a failure *signature* is a stable
  identity — test id / validation id).
- `iterations` enforces the 3-iteration cap per component.
- `evaluation.lastStrategy` drives graduated re-evaluation.
- `phase` is the resume entry point.

## Artifacts: spec vs. Context Brief

Two orthogonal artifacts, both passed to inner-loop subagents:

- **Spec/plan** (from `/harness-brainstorm`) — *what to build + acceptance criteria*.
  Load-bearing for Approach A: superpowers' spec-compliance reviewer checks code
  against it to catch over/under-building. Without it, that review stage is neutered.
- **Context Brief** (conditional) — *how this codebase works* (conventions, layout,
  integration points). Backward-looking codebase orientation only; **never restates
  the spec**.

**Conditional generation:** the brief is generated only when working in a non-trivial
existing codebase (brownfield), where it is generated once and reused across N task
dispatches (token efficiency) and persisted for resumability. For greenfield/trivial
work the spec suffices — the brief is skipped (`briefSkipped: true`).

## Orchestration loop & data flow

**`/harness-brainstorm`** → superpowers `brainstorming` → `writing-plans` → produces
`plans/<date>-<topic>-plan.md`. On completion, suggests `/harness-implement`.

**`/harness-implement`** runs the outer loop, persisting `harness-state.json` after
each step:

0. **Plan check** — no plan present? Point the user to `/harness-brainstorm` and stop.
1. **Resume check** — incomplete run in state file? Resume at `phase`.
2. **Worktree** — isolated worktree via superpowers `using-git-worktrees`.
3. **Brief gate (conditional)** — non-trivial existing codebase → generate a lean
   codebase-orientation brief at `plans/context-brief.md`. Greenfield/trivial → skip,
   record `briefSkipped: true`.
4. **Per-task inner loop** — for each task, run superpowers `subagent-driven-development`,
   feeding each subagent **spec text + brief (if present)**.
5. **Backend evaluation** — dispatch Backend Evaluator (fresh context) with strategy
   from `lastStrategy`:
   - Iteration 1 fail → **full** eval (all components)
   - Iteration 2 → **component-scoped** (only failing components)
   - Iteration 3 → **full** again (catch regressions component-scoped misses)
   Returns pass/fail **failure signatures**.
6. **Oscillation check** — a previously-resolved signature reappears in
   `failureHistory` → **stop**, surface the coupling relationship, `phase=escalated`.
   Takes precedence over the cap.
7. **Cap check** — any component hit 3 iterations → escalate to human.
8. **Fix** — otherwise dispatch the Fix Agent at the specific failing component,
   increment `iterations[component]`, loop to step 5.
9. **Mutation gate** — after functional tests pass, run the tiered Stryker gate.
   Gate failure re-enters the fix loop (counts against the cap). Placed after
   functional pass so mutation cost is not spent on functionally-broken code.
10. **Done** — all components pass tests + mutation gate → `phase=done` → hand to
    superpowers `finishing-a-development-branch`.

## Quality gates & stack config

Reference stack ships working .NET defaults in `harness.config.json` (target repo):

```json
{
  "stack": "dotnet",
  "commands": {
    "unit": "dotnet test --filter Category=Unit",
    "integration": "dotnet test --filter Category=Integration",
    "mutation": "dotnet stryker",
    "apiVerify": "path to curl-based smoke script"
  },
  "mutationThresholds": { "validators": 80, "services": 70, "controllers": 60 }
}
```

- **Tiered mutation thresholds** are config, not hardcoded. `mutation-gate.md` explains
  the rationale (validators = pure logic → highest bar; controllers = thin → lowest)
  and how the orchestrator maps files to tiers.
- **Swap points:** the orchestrator only ever calls the declared commands, never
  hardcoded tool names. `stack-config.md` documents replacing the `commands` block for
  another stack (e.g. Jest + Stryker-JS).
- **Backend Evaluator** runs `unit` + `integration` + `apiVerify`. The mutation gate
  runs separately at step 9.

## Error handling & escalation

- **Subagent statuses** (superpowers inner loop): `DONE` → proceed;
  `DONE_WITH_CONCERNS` → read, address if correctness/scope; `NEEDS_CONTEXT` → supply +
  re-dispatch; `BLOCKED` → assess (more context / more capable model / smaller task /
  escalate).
- **Evaluation failure** → Fix Agent, bounded by the 3-iteration cap per component.
- **Oscillation** → immediate stop + escalate; precedence over the cap. Surfaces the
  coupling relationship; an architectural-judgment problem, not a fixable bug.
- **Cap reached** (3 iterations, no oscillation) → escalate with failure history.
- **Tooling failure** (Stryker won't run, worktree conflict) → fail loud, persist
  state, escalate. Never silently skip a gate.
- **Escalation always persists state** (`phase=escalated`, `escalation` populated) so
  the human resumes with full context.

## Testing strategy

All local. Verification ladder:

1. **Install smoke** — `claude plugin marketplace add .`, install `backend-harness`,
   assert the skill loads and `/harness-brainstorm` + `/harness-implement` are
   discoverable.
2. **Dry-run orchestration** — run the outer loop against canned evaluator results
   (mocked pass/fail signatures) to deterministically exercise persistence, graduated
   re-eval, oscillation detection, and the cap *without* a real build.
3. **Full e2e on `sample/BackendApi`** — real .NET API with xUnit + Stryker.NET,
   intentionally seeded with (a) a failing unit test the fix loop must resolve, and
   (b) a weakly-tested service that trips the mutation gate. Run `/harness-implement`
   end-to-end; confirm the fix loop converges, the mutation gate fires then passes,
   state shows a clean `phase=done`, and the branch finishes via superpowers.

The seeded weak spots make the gates demonstrably fire — proving "works consistently"
rather than "happened to pass."

## Design decisions

| Decision | Why |
|---|---|
| Layer on superpowers (Approach A) | Add only the hardening layer; inner loop stays current automatically. |
| Backend only | Scoped, focused; removes FE/Playwright branch and UI evaluator. |
| State under `plans/`, written every step | Compaction resilience and resumability. |
| Spec is mandatory | Superpowers' spec-compliance review needs ground truth. |
| Context Brief conditional + narrow | Earns its place in brownfield only; never restates the spec; no wasted tokens greenfield. |
| Reference .NET stack, declared commands | Works out of the box; swappable without touching orchestration. |
| Tiered mutation thresholds (config) | Reflects real code-criticality differences. |
| Graduated re-evaluation | Balances eval cost vs. regression coverage. |
| Oscillation detection > cap | Distinguishes unfixable coupling from fixable bugs; escalates instead of burning budget. |
| 3-iteration cap | Point of diminishing returns / rising risk for autonomous fixing. |
| Two self-guiding commands | Workflow discoverability built into the UX. |
