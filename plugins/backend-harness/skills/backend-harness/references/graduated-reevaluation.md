# Graduated Re-Evaluation Strategy

> See `references/state-schema.md` for the canonical `harness-state.json` structure and field semantics.

## Overview

The graduated re-evaluation strategy balances cost and coverage when the Fix Agent iterates to address test failures. Rather than fully evaluating every iteration (expensive) or narrowly evaluating only failing components every time (risks missing regressions), this approach graduates the scope based on iteration count:

- **Iteration 1 fail** → full evaluation (catch all fallout)
- **Iteration 2** → component-scoped evaluation (cheaper, faster)
- **Iteration 3** → full evaluation again (catch regressions, final safety net)

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

```
if iterations[component] == 1:
  strategy = "full"
else if iterations[component] == 2:
  strategy = "component-scoped"
else if iterations[component] == 3:
  strategy = "full"
else:
  # Cap reached; do not evaluate, escalate
```

## Rationale

**Full evaluation every iteration** is too expensive. A single change can affect tests across multiple components; running the full suite every time for every iteration burns resources.

**Component-scoped evaluation every iteration** is too risky. Fixing component A to pass its tests may break tests in component B. Narrowing the scope every time means you won't see B's breakage until a later full run — or it goes unnoticed entirely if you cap at iteration 2.

**Graduated approach** is the optimal middle:
- Iteration 1 full run captures the immediate fallout from the first fix attempt
- Iteration 2 component-scoped run is cheaper; if component A still has issues, we fix them without re-running the entire suite
- Iteration 3 full run catches any regressions that component-scoped evaluation missed (e.g., the fix to A broke something in B that wasn't visible in iteration 2's narrow scope)

## Concrete 3-Iteration Walkthrough

Scenario: The `OrderService` component is failing the test `xunit:OrderTests.Total_AppliesDiscount` (discount logic broken).

**Iteration 1: Full Evaluation**
- Fix Agent patches `src/Services/OrderService.cs` to apply discount logic correctly
- Evaluation runs: unit tests, integration tests on all components
- Result: the discount test passes, but a new failure emerges in `PaymentService` (e.g., negative refund validation)
- `iterations[OrderService]` = 1
- `evaluation.lastStrategy` = `"full"`
- Phase: `fix`, loop repeats

**Iteration 2: Component-Scoped Evaluation**
- Fix Agent now targets the `PaymentService` issue
- Patches `src/Services/PaymentService.cs` to reject negative refunds
- Evaluation runs: unit tests and integration tests for `PaymentService` only (cheaper)
- Result: `PaymentService` tests pass, all `PaymentService`-scoped tests green
- `iterations[OrderService]` = 2
- `evaluation.lastStrategy` = `"component-scoped"`
- **Note:** The iteration counter tracks the per-component fix attempts across all evaluations in the run, not just the current iteration's target component.
- Phase: still `fix`, loop repeats

**Iteration 3: Full Evaluation (Final Safety Net)**
- Fix Agent re-evaluates to ensure no regressions; runs a full eval
- All unit and integration tests across all components
- Result: All tests pass
- `iterations[OrderService]` = 3
- `evaluation.lastStrategy` = `"full"`
- Phase: transitions to `evaluate` (move to mutation gate), exit the loop

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
