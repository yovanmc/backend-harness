# Backend Harness

[![CI](https://github.com/yovanmc/backend-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/yovanmc/backend-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Autonomous backend SDLC harness layered on superpowers' `subagent-driven-development`. The harness adds the production-hardening outer loop that superpowers' inner loop lacks. The outer loop enforces key quality mechanisms: disk-state persistence (compaction resilience), conditional Context Brief (codebase orientation for brownfield projects), independent backend evaluation (structural bias elimination), graduated re-evaluation (cost vs. regression coverage), tiered Stryker mutation gate (configurable thresholds by file type), oscillation detection (cyclic failure escalation), and 3-iteration cap with human escalation.

## What this is (and isn't)

This is a prompt-orchestration framework, not a traditional codebase: the core is a markdown state machine executed by LLM subagents, plus Python tooling that gates their output (diff-scoped mutation testing, oscillation detection, crash-safe state). Judge it as AI-developer-tooling design — the interesting decisions are in the orchestration, the failure handling, and the gating, not in code volume.

The repos on [my profile](https://github.com/yovanmc) were built with the workflow this harness productizes; each carries a "How this was built" section pointing back here.

## Prerequisites

- **superpowers plugin** — Required for the inner loop: `subagent-driven-development`, `using-git-worktrees`, `finishing-a-development-branch`
- **Target repository** with `harness.config.json` configured (see [Configure](#configure))
- **Subagent support enabled** — Required for independent context briefing, implementation, evaluation, and fix loops
- **For the reference stack (.NET):**
  - .NET SDK 8+
  - Stryker.NET installed as a dotnet tool: `dotnet tool install -g dotnet-stryker`
  - Tests using xUnit category traits: `[Trait("Category", "Unit")]` and `[Trait("Category", "Integration")]`

## Install For Claude Code

Register the marketplace and install the plugin:

```bash
# Register the marketplace
claude plugin marketplace add /absolute/path/to/backend-harness

# Install the plugin
claude plugin install backend-harness@backend-harness-marketplace
```

Replace `/absolute/path/to/backend-harness` with the absolute path where you cloned this repository.

## Install For Codex

This repo also ships Codex plugin metadata:

- `plugins/backend-harness/.codex-plugin/plugin.json`
- `.agents/plugins/marketplace.json`
- `plugins/backend-harness/skills/backend-harness/agents/openai.yaml`

Register the repo-local marketplace with Codex:

```bash
codex plugin marketplace add /absolute/path/to/backend-harness
```

Then install `backend-harness` from the `Backend Harness Local` marketplace in Codex.

## Configure

1. Copy `templates/harness.config.json` from the repo, or `plugins/backend-harness/skills/backend-harness/assets/templates/harness.config.json` from the installed skill, into the root of your target repository
2. Edit the `commands` block for your stack:
   - `unit`: command to run unit tests only
   - `integration`: command to run integration tests only
   - `mutation`: command to run mutation testing
   - `apiVerify`: command to run smoke/verification tests against live API
3. Adjust `mutationThresholds` if needed (defaults: validators 80%, services 70%, controllers 60%)
4. Adjust `fileTierGlobs` patterns to match your project's file structure
5. Refer to `plugins/backend-harness/skills/backend-harness/references/stack-config.md` for full field documentation and stack-swap examples (Node.js, Go, Python, etc.)
6. Add `plans/` to your `.gitignore` — this directory contains ephemeral run state (`harness-state.json`) that should not be committed.

`harness.config.json` contains commands that the agent will execute. Review those commands before running the harness in a target repository. The harness should stop rather than run destructive, suspicious, or unrelated commands.

## Use

Claude Code exposes two slash commands:

```
/harness-brainstorm   # Scope a feature into a spec/plan
/harness-implement    # Autonomously implement the plan with quality gates
```

Run `/harness-brainstorm` first to produce a plan file at `plans/<date>-<topic>-plan.md`. When the plan is approved, run `/harness-implement` to build it. The brainstorm command will suggest `/harness-implement` when ready.

Codex uses prompt-driven entrypoints instead:

```
Use backend-harness to brainstorm a backend feature plan.
Use backend-harness to implement the current plan with subagents and quality gates.
```

For Codex, mention subagents explicitly when you want the autonomous implementation loop. The harness depends on independent subagents to keep implementation and evaluation contexts separated.

## How It Works

1. **Brainstorm mode** → runs superpowers `brainstorming` + `writing-plans` → produces `plans/<date>-<topic>-plan.md`

2. **Implement mode** → outer loop:
   - Resume check (recover from session interruption)
   - Worktree creation (isolated branch via superpowers `using-git-worktrees`)
   - Conditional Context Brief (codebase orientation for non-trivial projects only)
   - Per-task implementation via superpowers `subagent-driven-development`
   - Backend evaluation (unit tests + integration tests + API smoke — commands declared in harness.config.json)
   - Graduated re-evaluation (full scope on early failures, component-scoped on iteration 2, 3-iteration cap)
   - Oscillation detection (escalates on cyclic failures between components)
   - Tiered Stryker mutation gate (validators 80%, services 70%, controllers 60% — configurable by tier)
   - Finish via superpowers `finishing-a-development-branch` (merge/PR/cleanup)

3. **State persistence** — `plans/harness-state.json` is written after every step. If the session is interrupted, rerun Implement mode to resume from the exact phase where it stopped.

4. **Structural bias elimination** — The implementer (inner loop) never sees evaluator output. The `backend-evaluator` subagent runs independently and reports only to the orchestrator. Evaluation feedback does not flow back into the implementer's context.

## Try it on the sample app

A ready-to-run brownfield .NET sample lives in [`sample/OrdersApi`](sample/OrdersApi). It is seeded with a real bug (caught by a failing xUnit test) and a thinly-tested service (low Stryker kill-rate) so you can watch the harness's fix loop and mutation gate fire end-to-end. See [`sample/README.md`](sample/README.md) for the walkthrough and expected convergence trace.

## Swapping Stacks

To adapt to a different stack (Node.js, Go, Python, etc.), edit only the `commands` block and `fileTierGlobs` in `harness.config.json` in your target repository. No orchestration code changes are needed. Refer to `plugins/backend-harness/skills/backend-harness/references/stack-config.md` for examples and field reference.
