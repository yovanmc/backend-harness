# Backend Harness

Autonomous backend SDLC harness layered on superpowers' `subagent-driven-development`. The harness adds the production-hardening outer loop that superpowers' inner loop lacks. The outer loop enforces key quality mechanisms: disk-state persistence (compaction resilience), conditional Context Brief (codebase orientation for brownfield projects), independent backend evaluation (structural bias elimination), graduated re-evaluation (cost vs. regression coverage), tiered Stryker mutation gate (configurable thresholds by file type), oscillation detection (cyclic failure escalation), and 3-iteration cap with human escalation.

## Prerequisites

- **superpowers plugin** — Required for the inner loop: `subagent-driven-development`, `using-git-worktrees`, `finishing-a-development-branch`
- **Target repository** with `harness.config.json` configured (see [Configure](#configure))
- **For the reference stack (.NET):**
  - .NET SDK 8+
  - Stryker.NET installed as a dotnet tool: `dotnet tool install -g dotnet-stryker`
  - Tests using xUnit category traits: `[Trait("Category", "Unit")]` and `[Trait("Category", "Integration")]`

## Install (Local Marketplace)

Register the marketplace and install the plugin:

```bash
# Register the marketplace
claude plugin marketplace add /absolute/path/to/backend-harness

# Install the plugin
claude plugin install backend-harness@backend-harness-marketplace
```

Replace `/absolute/path/to/backend-harness` with the absolute path where you cloned this repository.

## Configure

1. Copy `templates/harness.config.json` from the plugin repo into the root of your target repository
2. Edit the `commands` block for your stack:
   - `unit`: command to run unit tests only
   - `integration`: command to run integration tests only
   - `mutation`: command to run mutation testing
   - `apiVerify`: command to run smoke/verification tests against live API
3. Adjust `mutationThresholds` if needed (defaults: validators 80%, services 70%, controllers 60%)
4. Adjust `fileTierGlobs` patterns to match your project's file structure
5. Refer to `plugins/backend-harness/skills/backend-harness/references/stack-config.md` for full field documentation and stack-swap examples (Node.js, Go, Python, etc.)

## Use

Two commands, in order:

```
/harness-brainstorm   # Scope a feature into a spec/plan
/harness-implement    # Autonomously implement the plan with quality gates
```

Run `/harness-brainstorm` first to produce a plan file at `plans/<date>-<topic>-plan.md`. When the plan is approved, run `/harness-implement` to build it. The brainstorm command will suggest `/harness-implement` when ready.

## How It Works

1. **`/harness-brainstorm`** → runs superpowers `brainstorming` + `writing-plans` → produces `plans/<date>-<topic>-plan.md`

2. **`/harness-implement`** → outer loop:
   - Resume check (recover from session interruption)
   - Worktree creation (isolated branch via superpowers `using-git-worktrees`)
   - Conditional Context Brief (codebase orientation for non-trivial projects only)
   - Per-task implementation via superpowers `subagent-driven-development`
   - Backend evaluation (unit tests + integration tests + API smoke — commands declared in harness.config.json)
   - Graduated re-evaluation (full scope on early failures, component-scoped on iteration 2, 3-iteration cap)
   - Oscillation detection (escalates on cyclic failures between components)
   - Tiered Stryker mutation gate (validators 80%, services 70%, controllers 60% — configurable by tier)
   - Finish via superpowers `finishing-a-development-branch` (merge/PR/cleanup)

3. **State persistence** — `plans/harness-state.json` is written after every step. If the session is interrupted, rerun `/harness-implement` to resume from the exact phase where it stopped.

4. **Structural bias elimination** — The implementer (inner loop) never sees evaluator output. The `backend-evaluator` subagent runs independently and reports only to the orchestrator. Evaluation feedback does not flow back into the implementer's context.

## Swapping Stacks

To adapt to a different stack (Node.js, Go, Python, etc.), edit only the `commands` block and `fileTierGlobs` in `harness.config.json` in your target repository. No orchestration code changes are needed. Refer to `plugins/backend-harness/skills/backend-harness/references/stack-config.md` for examples and field reference.
