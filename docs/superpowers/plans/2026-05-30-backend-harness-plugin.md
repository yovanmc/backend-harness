# Backend Harness Plugin Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the installable `backend-harness` Claude Code plugin — a production-hardening orchestration layer over superpowers' `subagent-driven-development` — verified via local marketplace install and a deterministic dry-run of the outer loop.

**Architecture:** A plugin (under `plugins/backend-harness/`) exposing two slash commands (`/harness-brainstorm`, `/harness-implement`) and one orchestrator skill (`backend-harness`). The skill's `SKILL.md` drives an outer loop (resume → worktree → conditional Context Brief → per-task inner loop via superpowers → backend evaluation → graduated re-eval → oscillation/cap checks → fix loop → tiered mutation gate → finish), persisting `plans/harness-state.json` after every step. Reference docs and prompt templates support the orchestrator. The mock fixture in Task 10 lets the loop logic be exercised without a real build.

**Tech Stack:** Claude Code plugin format (`marketplace.json`, `plugin.json`), Markdown skill/command/reference/prompt files, JSON state + config schemas, Bash for verification. Depends on the `superpowers` plugin at runtime.

**Scope note:** This is Plan 1 of 2. Plan 2 (`2026-05-30-backend-harness-sample-e2e.md`) adds the sample `.NET` API with seeded weak spots and the full end-to-end run. This plan is complete and verifiable on its own via the Task 9 install smoke and Task 10 dry-run.

---

## File Structure

Files created by this plan (all paths relative to repo root `backend-harness/`):

| File | Responsibility |
|---|---|
| `.claude-plugin/marketplace.json` | Registers the marketplace so `claude plugin marketplace add .` finds the plugin. |
| `plugins/backend-harness/.claude-plugin/plugin.json` | Plugin manifest; metadata + superpowers dependency note. |
| `plugins/backend-harness/skills/backend-harness/SKILL.md` | The orchestrator. Encodes the entire outer loop and when to defer to superpowers. |
| `.../skills/backend-harness/references/state-schema.md` | `plans/harness-state.json` schema + field semantics + resumability rationale. |
| `.../references/graduated-reevaluation.md` | Full → component-scoped → full strategy and how `lastStrategy` drives it. |
| `.../references/oscillation-detection.md` | Failure-signature identity, detection rule, escalation behavior. |
| `.../references/mutation-gate.md` | Tiered thresholds, file→tier mapping, when the gate runs. |
| `.../references/stack-config.md` | `harness.config.json` shape, .NET reference defaults, swap instructions. |
| `.../skills/backend-harness/prompts/context-brief.md` | Prompt the orchestrator uses to generate the conditional brief. |
| `.../prompts/backend-evaluator.md` | Prompt for the independent Backend Evaluator subagent. |
| `.../prompts/fix-agent.md` | Prompt for the conditional Fix Agent subagent. |
| `plugins/backend-harness/commands/harness-brainstorm.md` | `/harness-brainstorm` entry point. |
| `plugins/backend-harness/commands/harness-implement.md` | `/harness-implement` entry point. |
| `templates/harness.config.json` | Reference .NET config the user copies into their target repo. |
| `README.md` | Quickstart: install, configure, run, swap stacks. |
| `test/dry-run/harness-state.fixture.json` | Canned state used by the Task 10 dry-run. |
| `test/dry-run/eval-results.fixture.json` | Canned evaluator outputs (pass/fail signatures, incl. an oscillation sequence). |
| `test/dry-run/README.md` | How to run the dry-run verification. |

Each skill file has one responsibility; references are split so the orchestrator can load only what a given step needs.

---

## Task 1: Marketplace + plugin manifest

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Create: `plugins/backend-harness/.claude-plugin/plugin.json`

- [ ] **Step 1: Write `marketplace.json`**

Exact content:

```json
{
  "name": "backend-harness-marketplace",
  "owner": {
    "name": "Yovan Collins",
    "url": "https://github.com/yovancollins"
  },
  "plugins": [
    {
      "name": "backend-harness",
      "source": "./plugins/backend-harness",
      "description": "Autonomous backend SDLC harness: a production-hardening orchestration layer over superpowers' subagent-driven-development."
    }
  ]
}
```

- [ ] **Step 2: Write `plugin.json`**

Exact content:

```json
{
  "name": "backend-harness",
  "version": "0.1.0",
  "description": "Autonomous backend SDLC harness with disk-state persistence, graduated re-evaluation, tiered mutation gating, and oscillation detection. Layers on superpowers' subagent-driven-development.",
  "author": {
    "name": "Yovan Collins"
  },
  "keywords": ["sdlc", "orchestration", "subagents", "mutation-testing", "dotnet"]
}
```

- [ ] **Step 3: Verify JSON validity**

Run: `python3 -c "import json,sys; [json.load(open(p)) for p in sys.argv[1:]]; print('valid')" .claude-plugin/marketplace.json plugins/backend-harness/.claude-plugin/plugin.json`
Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/marketplace.json plugins/backend-harness/.claude-plugin/plugin.json
git commit -m "feat: add marketplace and plugin manifests"
```

> **Note on the superpowers dependency:** Claude Code plugin manifests do not yet have a hard dependency field. The dependency is enforced by documentation (README + SKILL.md preflight check in Task 7, Step 3) rather than the manifest. Do not invent a manifest field for it.

---

## Task 2: Stack config template + `stack-config.md` reference

**Files:**
- Create: `templates/harness.config.json`
- Create: `plugins/backend-harness/skills/backend-harness/references/stack-config.md`

- [ ] **Step 1: Write `templates/harness.config.json`**

Exact content:

```json
{
  "stack": "dotnet",
  "commands": {
    "unit": "dotnet test --filter Category=Unit",
    "integration": "dotnet test --filter Category=Integration",
    "mutation": "dotnet stryker",
    "apiVerify": "./scripts/api-smoke.sh"
  },
  "mutationThresholds": {
    "validators": 80,
    "services": 70,
    "controllers": 60
  },
  "fileTierGlobs": {
    "validators": ["**/Validators/**/*.cs", "**/*Validator.cs"],
    "services": ["**/Services/**/*.cs", "**/*Service.cs"],
    "controllers": ["**/Controllers/**/*.cs", "**/*Controller.cs"]
  }
}
```

- [ ] **Step 2: Write `stack-config.md`** with these required sections (complete content, no placeholders):
  1. **Purpose** — `harness.config.json` lives in the *target* repo, not the plugin; the orchestrator only ever calls the commands declared here, never hardcoded tool names.
  2. **Field reference** — a table documenting every field above: `stack`, `commands.{unit,integration,mutation,apiVerify}`, `mutationThresholds.{validators,services,controllers}`, `fileTierGlobs`. For each: type, what it does, example value.
  3. **Reference stack (.NET)** — state these are the shipped defaults and what each command assumes (xUnit `[Trait("Category", ...)]`, Stryker.NET installed as a dotnet tool, `apiVerify` is a curl script returning non-zero on failure).
  4. **Swapping stacks** — a worked example replacing the `commands` block for Node (`"unit": "npm test"`, `"mutation": "npx stryker run"`) and adjusting `fileTierGlobs` for `*.ts`. State that no orchestration code changes are needed — only this file.
  5. **Tier mapping** — point to `mutation-gate.md` for how `fileTierGlobs` maps changed files to thresholds.

- [ ] **Step 3: Verify config validity**

Run: `python3 -c "import json; json.load(open('templates/harness.config.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add templates/harness.config.json plugins/backend-harness/skills/backend-harness/references/stack-config.md
git commit -m "feat: add harness.config.json template and stack-config reference"
```

---

## Task 3: `state-schema.md` reference

**Files:**
- Create: `plugins/backend-harness/skills/backend-harness/references/state-schema.md`

- [ ] **Step 1: Write `state-schema.md`** with these required sections (complete content):
  1. **Why disk state** — written after every labeled step so a context-compaction or crash mid-run is fully resumable; the orchestrator reads it on entry and resumes at `phase`.
  2. **Location** — `plans/harness-state.json` in the target repo (no `.beads/`). Sibling artifacts: `plans/context-brief.md`, `plans/<date>-<topic>-plan.md`.
  3. **Full schema** — embed this exact JSON as the canonical example:

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
  4. **Field semantics** — a table for every field. Must explicitly state: `failureHistory` is the oscillation substrate (signature = stable identity such as a test id); `iterations` enforces the per-component 3-cap; `evaluation.lastStrategy` drives graduated re-eval; `phase` is the resume entry point; `escalation` is `null` until escalated, then an object `{reason, detail, signatures}`.
  5. **Write discipline** — after each step set `updatedAt` and persist atomically (write temp file, rename) to avoid corruption on interruption.

- [ ] **Step 2: Verify the embedded JSON example parses**

Run: `python3 -c "import re,json; t=open('plugins/backend-harness/skills/backend-harness/references/state-schema.md').read(); b=t.split('\`\`\`json')[1].split('\`\`\`')[0]; json.loads(b); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add plugins/backend-harness/skills/backend-harness/references/state-schema.md
git commit -m "feat: add state-schema reference"
```

---

## Task 4: Mechanism references (graduated re-eval, oscillation, mutation gate)

**Files:**
- Create: `.../references/graduated-reevaluation.md`
- Create: `.../references/oscillation-detection.md`
- Create: `.../references/mutation-gate.md`

- [ ] **Step 1: Write `graduated-reevaluation.md`** with required content:
  - The strategy: **Iteration 1 fail → full** eval (all components); **Iteration 2 → component-scoped** (only failing components, cheaper); **Iteration 3 → full** again (catch regressions component-scoped misses).
  - How it reads/writes state: strategy chosen from `iterations[component]`, recorded in `evaluation.lastStrategy`.
  - Rationale: full-every-time is expensive; scoped-every-time misses regressions; the graduated path is the middle.
  - A concrete 3-iteration walkthrough example with the `lastStrategy` value at each step.

- [ ] **Step 2: Write `oscillation-detection.md`** with required content:
  - Definition: Fix A breaks B, Fix B breaks A — system cycles without converging; a retry limit alone does not catch it because each iteration "made progress."
  - Detection rule: a failure `signature` that was previously present, then resolved, then **reappears** in `failureHistory` within the same `runId` = oscillation.
  - Behavior: **stop immediately**, set `phase=escalated`, populate `escalation` with the coupling relationship (which signatures/components cycle), do **not** consume remaining iterations. Precedence: oscillation check runs **before** the cap check.
  - Rationale: signals a coupling problem requiring human architectural judgment, not a fixable bug.
  - A concrete example sequence of `failureHistory` entries that trips detection.

- [ ] **Step 3: Write `mutation-gate.md`** with required content:
  - When it runs: **after** functional tests (unit+integration) pass, so mutation cost is not spent on functionally-broken code (outer-loop step 9).
  - Tiered thresholds table: validators 80%, services 70%, controllers 60%, with rationale (validators = pure logic → highest bar; controllers = thin → lowest).
  - File→tier mapping: uses `fileTierGlobs` from `harness.config.json`; a changed file matching a glob is held to that tier's threshold; files matching no glob default to the lowest configured threshold.
  - Gate failure path: re-enters the fix loop and **counts against the 3-iteration cap**.
  - Note thresholds are config-driven, never hardcoded in the orchestrator.

- [ ] **Step 4: Commit**

```bash
git add plugins/backend-harness/skills/backend-harness/references/graduated-reevaluation.md plugins/backend-harness/skills/backend-harness/references/oscillation-detection.md plugins/backend-harness/skills/backend-harness/references/mutation-gate.md
git commit -m "feat: add mechanism references (re-eval, oscillation, mutation gate)"
```

---

## Task 5: Subagent prompt templates

**Files:**
- Create: `.../prompts/context-brief.md`
- Create: `.../prompts/backend-evaluator.md`
- Create: `.../prompts/fix-agent.md`

- [ ] **Step 1: Write `context-brief.md`** — the prompt the orchestrator uses to generate the conditional brief. Required content:
  - Role line: "You are surveying an existing codebase to orient implementer subagents."
  - Hard constraint: **describe what exists, never what to build** — do not restate or infer the spec.
  - Output contract: write to `plans/context-brief.md`; sections = directory/layout map, key conventions (DI, validation, config, error handling), where tests live and how they run, integration points/external services, and notable gotchas. Keep it lean — orientation, not exhaustive documentation.
  - Stop condition: when the above sections are filled from actual file inspection; do not speculate.

- [ ] **Step 2: Write `backend-evaluator.md`** — prompt for the independent Backend Evaluator subagent. Required content:
  - Role: independent evaluator with **no visibility into implementer reasoning**; you receive only the worktree path, the config commands, and the evaluation scope (full or a component list).
  - Tasks: run `commands.unit`, `commands.integration`, then `commands.apiVerify`; for the given scope only when component-scoped.
  - Output contract (exact, machine-parseable): return a JSON block with `{ "overall": "pass|fail", "results": [ {"component": "...", "status": "pass|fail", "signatures": ["xunit:Class.Test", ...]} ] }`. A signature is a stable failing-test/validation identity.
  - Constraints: do not modify code; do not attempt fixes; report only.

- [ ] **Step 3: Write `fix-agent.md`** — prompt for the conditional Fix Agent. Required content:
  - Role: targeted fixer for **one named failing component**; you receive the component name, its failure signatures, the worktree path, and the relevant spec text.
  - Tasks: reproduce the failing signatures, fix the component, keep changes scoped to that component (do not refactor unrelated code), commit.
  - Output contract: report status (`DONE` | `DONE_WITH_CONCERNS` | `NEEDS_CONTEXT` | `BLOCKED`) and the commit SHA, mirroring superpowers subagent status conventions.
  - Constraint: you do not run mutation testing or declare the gate passed — the orchestrator re-evaluates.

- [ ] **Step 4: Commit**

```bash
git add plugins/backend-harness/skills/backend-harness/prompts/context-brief.md plugins/backend-harness/skills/backend-harness/prompts/backend-evaluator.md plugins/backend-harness/skills/backend-harness/prompts/fix-agent.md
git commit -m "feat: add subagent prompt templates"
```

---

## Task 6: Slash commands

**Files:**
- Create: `plugins/backend-harness/commands/harness-brainstorm.md`
- Create: `plugins/backend-harness/commands/harness-implement.md`

- [ ] **Step 1: Write `harness-brainstorm.md`**

Exact content:

```markdown
---
description: Scope a backend feature into a spec/plan, then suggest /harness-implement.
---

Invoke the `backend-harness` skill in BRAINSTORM mode.

Run superpowers `brainstorming` then superpowers `writing-plans` to produce a
plan at `plans/<date>-<topic>-plan.md`. This plan is the spec the harness builds
against.

When the plan is written and approved, tell the user:

> Plan ready at `<path>`. Run `/harness-implement` to build it autonomously.
```

- [ ] **Step 2: Write `harness-implement.md`**

Exact content:

```markdown
---
description: Autonomously implement the current plan with quality gates (backend harness outer loop).
---

Invoke the `backend-harness` skill in IMPLEMENT mode and run its outer loop
(SKILL.md): resume check → worktree → conditional Context Brief → per-task inner
loop (superpowers subagent-driven-development) → backend evaluation → graduated
re-evaluation → oscillation/cap checks → fix loop → tiered mutation gate → finish.

Persist `plans/harness-state.json` after every step. If no plan exists under
`plans/`, instruct the user to run `/harness-brainstorm` first and stop.
```

- [ ] **Step 3: Verify frontmatter parses**

Run: `python3 -c "import sys; [open(p).read().startswith('---') or sys.exit('missing frontmatter: '+p) for p in ['plugins/backend-harness/commands/harness-brainstorm.md','plugins/backend-harness/commands/harness-implement.md']]; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add plugins/backend-harness/commands/harness-brainstorm.md plugins/backend-harness/commands/harness-implement.md
git commit -m "feat: add /harness-brainstorm and /harness-implement commands"
```

---

## Task 7: The orchestrator `SKILL.md`

**Files:**
- Create: `plugins/backend-harness/skills/backend-harness/SKILL.md`

- [ ] **Step 1: Write the frontmatter and overview**

Frontmatter (exact):

```markdown
---
name: backend-harness
description: Use when autonomously implementing a backend feature plan with enforced quality gates - drives an outer loop (state persistence, backend evaluation, graduated re-evaluation, tiered mutation gating, oscillation detection, iteration cap) over superpowers subagent-driven-development.
---
```

Overview prose must state: this skill is the **outer loop**; superpowers `subagent-driven-development` is the **inner loop** (implement → spec review → quality review per task); the implementer never sees evaluator output (structural bias elimination); state is persisted to `plans/harness-state.json` after every step.

- [ ] **Step 2: Write the preflight section**
  - Check superpowers is installed (the inner loop and `using-git-worktrees`, `finishing-a-development-branch` depend on it). If not, instruct the user to install it and stop.
  - Check `harness.config.json` exists in the target repo; if missing, point to `templates/harness.config.json` and `references/stack-config.md` and stop.
  - Check a plan exists under `plans/`; if not, instruct `/harness-brainstorm` and stop.

- [ ] **Step 3: Write the outer-loop process** as an explicit numbered procedure mirroring the spec's "Orchestration loop & data flow" (steps 0–10). Each step must state what to do AND that state is persisted after it. Required steps, in order:
  0. Plan check (stop → `/harness-brainstorm` if absent).
  1. Resume check — read `plans/harness-state.json`; if `phase` is incomplete, resume there.
  2. Worktree — `superpowers:using-git-worktrees`; record `worktree`. Persist `phase=brief`.
  3. Brief gate (conditional) — if non-trivial existing codebase, dispatch a subagent with `prompts/context-brief.md` to write `plans/context-brief.md`; else set `briefSkipped=true`. Define "non-trivial existing codebase" concretely: target repo has pre-existing source files unrelated to this plan's new files (i.e., not greenfield/empty).
  4. Per-task inner loop — for each plan task, run `superpowers:subagent-driven-development`, passing **spec text + brief (if present)**. Persist task `status` + `commitSha` after each.
  5. Backend evaluation — dispatch `prompts/backend-evaluator.md` with strategy from `references/graduated-reevaluation.md`; parse the JSON result; persist `evaluation` + append `failureHistory`. Persist `phase=evaluate`.
  6. Oscillation check (`references/oscillation-detection.md`) — runs BEFORE cap check; on detection, persist `phase=escalated` + `escalation`, surface coupling, stop.
  7. Cap check — any `iterations[component] >= 3` → escalate, persist, stop.
  8. Fix — dispatch `prompts/fix-agent.md` for each failing component, increment `iterations[component]`, persist `phase=fix`, loop to step 5.
  9. Mutation gate (`references/mutation-gate.md`) — after functional pass, run `commands.mutation`, apply tiered thresholds; failure re-enters the fix loop (counts against cap).
  10. Done — all pass → `phase=done` → `superpowers:finishing-a-development-branch`.

- [ ] **Step 4: Write the references/prompts index** — a table linking each `references/*.md` and `prompts/*.md` to the step that uses it, so the orchestrator loads only what each step needs.

- [ ] **Step 5: Write the Red Flags section** — never skip the mutation gate; never let the implementer see evaluator output; never continue past oscillation; never exceed the cap silently; never call hardcoded tool names instead of `harness.config.json` commands; never run on main/master without consent (defer to superpowers worktree skill).

- [ ] **Step 6: Verify SKILL.md frontmatter and required anchors exist**

Run:
```bash
python3 - <<'PY'
t=open('plugins/backend-harness/skills/backend-harness/SKILL.md').read()
assert t.startswith('---'), 'missing frontmatter'
for kw in ['name: backend-harness','Preflight','Oscillation','mutation','Resume','Red Flags']:
    assert kw.lower() in t.lower(), 'missing: '+kw
print('ok')
PY
```
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add plugins/backend-harness/skills/backend-harness/SKILL.md
git commit -m "feat: add backend-harness orchestrator SKILL.md"
```

---

## Task 8: README quickstart

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`** with required sections:
  1. **What it is** — one paragraph: autonomous backend SDLC harness layered on superpowers; the mechanisms list.
  2. **Prerequisites** — superpowers plugin installed; a target repo with `harness.config.json`; the reference stack expects .NET + Stryker.NET.
  3. **Install (local marketplace)** — exact commands:
     ```bash
     claude plugin marketplace add /absolute/path/to/backend-harness
     claude plugin install backend-harness@backend-harness-marketplace
     ```
  4. **Configure** — copy `templates/harness.config.json` into the target repo; edit `commands` for your stack (link `references/stack-config.md`).
  5. **Use** — `/harness-brainstorm` to produce a plan, then `/harness-implement` to build it.
  6. **How it works** — short list mapping to the references (state persistence, graduated re-eval, oscillation detection, tiered mutation gate, 3-iteration cap).
  7. **Swapping stacks** — point to `references/stack-config.md`.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README quickstart"
```

---

## Task 9: Install smoke verification

**Files:**
- (No new files; verification of Tasks 1–8.)

- [ ] **Step 1: Validate every JSON and frontmatter file**

Run:
```bash
python3 - <<'PY'
import json,glob,sys
for p in glob.glob('**/*.json', recursive=True):
    if 'fixture' in p or p.startswith('docs/'): continue
    json.load(open(p))
for p in ['plugins/backend-harness/commands/harness-brainstorm.md',
          'plugins/backend-harness/commands/harness-implement.md',
          'plugins/backend-harness/skills/backend-harness/SKILL.md']:
    assert open(p).read().startswith('---'), 'no frontmatter: '+p
print('all valid')
PY
```
Expected: `all valid`

- [ ] **Step 2: Add the marketplace locally**

Run: `claude plugin marketplace add "$(pwd)"`
Expected: marketplace `backend-harness-marketplace` added; `backend-harness` listed.

- [ ] **Step 3: Install the plugin**

Run: `claude plugin install backend-harness@backend-harness-marketplace`
Expected: install succeeds.

- [ ] **Step 4: Assert skill + commands are discoverable**

In a Claude Code session with the plugin installed, confirm the `backend-harness` skill appears in the available-skills list and `/harness-brainstorm` + `/harness-implement` are listed as commands.
Expected: skill present; both commands present.

- [ ] **Step 5: Commit any fixes surfaced**

```bash
git add -A && git commit -m "fix: install smoke corrections" || echo "nothing to commit"
```

---

## Task 10: Dry-run orchestration verification

Exercises the outer-loop logic deterministically with canned evaluator results — no real build. This proves persistence, graduated re-eval, oscillation detection, and the cap.

**Files:**
- Create: `test/dry-run/harness-state.fixture.json`
- Create: `test/dry-run/eval-results.fixture.json`
- Create: `test/dry-run/README.md`

- [ ] **Step 1: Write `eval-results.fixture.json`** — a scripted sequence of evaluator returns designed to trip oscillation:

```json
{
  "sequence": [
    { "call": 1, "strategy": "full",
      "overall": "fail",
      "results": [
        {"component": "OrderService", "status": "fail", "signatures": ["xunit:OrderTests.Total_AppliesDiscount"]},
        {"component": "PaymentService", "status": "pass", "signatures": []}
      ]
    },
    { "call": 2, "strategy": "component-scoped",
      "overall": "fail",
      "results": [
        {"component": "OrderService", "status": "pass", "signatures": []},
        {"component": "PaymentService", "status": "fail", "signatures": ["xunit:PaymentTests.Refund_NegativeAmount"]}
      ]
    },
    { "call": 3, "strategy": "full",
      "overall": "fail",
      "results": [
        {"component": "OrderService", "status": "fail", "signatures": ["xunit:OrderTests.Total_AppliesDiscount"]},
        {"component": "PaymentService", "status": "pass", "signatures": []}
      ]
    }
  ]
}
```

Note: call 3 re-introduces `xunit:OrderTests.Total_AppliesDiscount` after it was resolved in call 2 → oscillation.

- [ ] **Step 2: Write `harness-state.fixture.json`** — the expected end-state after running the sequence, used as the assertion target:

```json
{
  "phase": "escalated",
  "evaluation": { "lastStrategy": "full" },
  "iterations": { "OrderService": 2, "PaymentService": 1 },
  "escalation": {
    "reason": "oscillation",
    "signatures": ["xunit:OrderTests.Total_AppliesDiscount"],
    "components": ["OrderService", "PaymentService"]
  }
}
```

- [ ] **Step 3: Write `test/dry-run/README.md`** — instructions: in a Claude Code session, invoke the `backend-harness` skill and tell it to run its outer loop in dry-run mode, consuming `eval-results.fixture.json` in place of dispatching a real Backend Evaluator. Then assert the produced `plans/harness-state.json` matches `harness-state.fixture.json` on the fields shown (phase, escalation.reason, escalation.signatures, iterations).

- [ ] **Step 4: Run the dry-run and assert**

Run the outer loop against the fixture (per `test/dry-run/README.md`), then:
```bash
python3 - <<'PY'
import json
exp=json.load(open('test/dry-run/harness-state.fixture.json'))
got=json.load(open('plans/harness-state.json'))
assert got['phase']=='escalated', got['phase']
assert got['escalation']['reason']=='oscillation', got['escalation']
assert 'xunit:OrderTests.Total_AppliesDiscount' in got['escalation']['signatures']
assert got['iterations']==exp['iterations'], got['iterations']
print('dry-run PASS: oscillation detected, cap not exhausted, state persisted')
PY
```
Expected: `dry-run PASS: ...` — proves the loop stopped on oscillation at call 3 (before any component hit the 3-cap), with state correctly persisted.

- [ ] **Step 5: Commit**

```bash
git add test/dry-run
git commit -m "test: add deterministic dry-run for outer-loop logic"
```

---

## Self-Review

**Spec coverage:**
- Layer on superpowers (Approach A) → Tasks 6, 7 (inner loop via subagent-driven-development; preflight checks superpowers). ✓
- Backend only → no FE tasks anywhere. ✓
- State under `plans/`, written every step → Tasks 3, 7 (step 3 persistence), 10. ✓
- Mandatory spec + conditional narrow brief → Tasks 5 (context-brief prompt), 7 (step 3, brief gate definition). ✓
- Reference .NET stack + declared commands + swap points → Tasks 2, 8. ✓
- Tiered mutation thresholds (config) → Tasks 2, 4 (mutation-gate.md). ✓
- Graduated re-evaluation → Tasks 4, 7. ✓
- Oscillation detection > cap → Tasks 4, 7 (ordering), 10 (proven). ✓
- 3-iteration cap → Tasks 3, 4, 7. ✓
- Two self-guiding commands → Task 6. ✓
- Packaging/marketplace → Task 1; install smoke → Task 9. ✓
- Dry-run testability → Task 10. ✓
- (Sample .NET app + full e2e → deferred to Plan 2, as scoped.) ✓

**Placeholder scan:** Prose-file tasks (2,3,4,5,7,8) specify exact required sections, rules, and embedded literal JSON rather than vague "add docs." Machine-precise files (manifests, config, commands, fixtures) have exact literal content. No "TBD/TODO/implement later." ✓

**Type consistency:** Field names (`phase`, `lastStrategy`, `failureHistory`, `iterations`, `escalation`, `briefSkipped`, `signatures`, `component`) and command names (`commands.unit/integration/mutation/apiVerify`, `mutationThresholds`, `fileTierGlobs`) are identical across Tasks 2, 3, 4, 7, 10. Evaluator output contract (`overall`/`results`/`signatures`) matches between Task 5 and the Task 10 fixtures. ✓
