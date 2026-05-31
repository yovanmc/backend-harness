# Graduated Re-Evaluation Strategy

> See `references/state-schema.md` for the canonical `harness-state.json` structure and field semantics.

## Overview

The graduated re-evaluation strategy balances cost and coverage when the Fix Agent iterates to address test failures. Rather than fully evaluating every iteration (expensive) or narrowly evaluating only failing components every time (risks missing regressions), this approach graduates the scope based on iteration count:

- **Iteration 0 (first failure)** → full evaluation (catch all fallout)
- **Iteration 1** → component-scoped evaluation (cheaper, faster)
- **Iteration 2** → full evaluation again (catch regressions, final safety net)

## State Tracking

The strategy selection is driven by the `iterations[component]` counter in `plans/harness-state.json`:

```json
{
  "phase": "fix",
  "iterations": {
    "OrderService": 2
  },
  "evaluation": {
    "lastStrategy": "component-scoped"
  }
}
```

After each evaluation runs, the chosen strategy is recorded in `evaluation.lastStrategy` with one of two values:
- `"full"` — all components evaluated
- `"component-scoped"` — only the currently-fixing component evaluated

## Strategy Selection Logic

**Special Case — Force Full After Component-Scoped Pass**

Before applying the per-component rule, check this condition first:

```
if evaluation.lastStrategy == "component-scoped" AND last overall result == "pass":
  strategy = "full"
  scope = "full"
  # Skip the per-component rule below — this overrides it.
```

This ensures a regression sweep after a narrow-scoped clean pass. A component-scoped evaluation only checks the components in its scope — it cannot see regressions in components that were excluded. If that narrow pass returns `overall: "pass"`, the next evaluation must be full to catch any breakage that was out of scope.

**Per-Component Rule**

```
if iterations[component] == 0:
  strategy = "full"
else if iterations[component] == 1:
  strategy = "component-scoped"
else if iterations[component] == 2:
  strategy = "full"
else:
  # Cap reached; do not evaluate, escalate
```

## Rationale

**Full evaluation every iteration** is too expensive. A single change can affect tests across multiple components; running the full suite every time for every iteration burns resources.

**Component-scoped evaluation every iteration** is too risky. Fixing component A to pass its tests may break tests in component B. Narrowing the scope every time means you won't see B's breakage until a later full run — or it goes unnoticed entirely if you cap at iteration 2.

**Graduated approach** is the optimal middle:
- Iteration 0 (first failure) full run captures the immediate fallout from the first fix attempt
- Iteration 1 component-scoped run is cheaper; if component A still has issues, we fix them without re-running the entire suite
- Iteration 2 full run catches any regressions that component-scoped evaluation missed (e.g., the fix to A broke something in B that wasn't visible in iteration 1's narrow scope)

## Concrete 3-Iteration Walkthrough

Scenario: The `OrderService` component is failing the test `xunit:OrderTests.Total_AppliesDiscount` (discount logic broken).

**Iteration 0: Full Evaluation (First Failure)**
- Fix Agent patches `src/Services/OrderService.cs` to apply discount logic correctly
- Evaluation runs: unit tests, integration tests on all components
- Result: the discount test passes, but a new failure emerges in `PaymentService` (e.g., negative refund validation)
- `iterations[OrderService]` = 0 (at this call)
- `evaluation.lastStrategy` = `"full"`
- Phase: `fix`, loop repeats

**Iteration 1: Component-Scoped Evaluation**
- Fix Agent now targets the `PaymentService` issue
- Patches `src/Services/PaymentService.cs` to reject negative refunds
- Evaluation runs: unit tests and integration tests for `PaymentService` only (cheaper)
- Result: `PaymentService` tests pass, all `PaymentService`-scoped tests green
- `iterations[OrderService]` = 1 (at this call; incremented after call 0)
- `evaluation.lastStrategy` = `"component-scoped"`
- **Note:** The iteration counter tracks the per-component fix attempts across all evaluations in the run, not just the current iteration's target component.
- Phase: still `fix`, loop repeats

**Iteration 2: Full Evaluation (Final Safety Net)**
- Fix Agent re-evaluates to ensure no regressions; runs a full eval
- All unit and integration tests across all components
- Result: All tests pass
- `iterations[OrderService]` = 2 (at this call; incremented after call 1)
- `evaluation.lastStrategy` = `"full"`
- Phase: transitions to `evaluate` (move to mutation gate), exit the loop

**Why call 3 is full even though `iterations[OrderService]` is still 1:**
The Special Case rule applies here. After iteration 1's component-scoped evaluation returned `overall: "pass"`, `evaluation.lastStrategy` is `"component-scoped"` and the last overall result was `"pass"`. This triggers the force-full override before the per-component rule is even consulted — the next evaluation must be full to sweep for regressions in the components that were excluded from scope.

## When the Cap is Reached

If after 3 full iterations the component is still failing, the orchestrator escalates:

```json
{
  "phase": "escalated",
  "escalation": {
    "reason": "cap_exceeded",
    "detail": "3 fix iterations exhausted; component still failing",
    "signatures": ["xunit:OrderTests.Total_AppliesDiscount"]
  }
}
```

The Fix Agent does not run again; the issue is surface to the human for architectural review.
