---
description: Autonomously implement the current plan with quality gates (backend harness outer loop).
---

Invoke the `backend-harness` skill in IMPLEMENT mode and run its outer loop
(SKILL.md): resume check → worktree → conditional Context Brief → per-task inner
loop (superpowers subagent-driven-development) → backend evaluation → graduated
re-evaluation → oscillation/cap checks → fix loop → tiered mutation gate → finish.

Persist `plans/harness-state.json` after every step. If no plan exists under
`plans/`, instruct the user to run `/harness-brainstorm` first and stop.
