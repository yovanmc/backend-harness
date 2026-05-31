# Oscillation Detection

## Definition

Oscillation is a failure cycle where the system cannot converge: Fix A resolves one set of test failures but breaks another component, then Fix B resolves those failures but breaks the first component again. The system cycles without progress.

A naive retry counter alone does not catch oscillation — every iteration technically "made progress" on its target failure, so it will always appear to be running out the iterations legitimately. Oscillation detection recognizes the *pattern* of failure recurrence, not just the count of attempts.

## Detection Rule

A failure is identified by its **signature** — a stable, unique identifier for the failing test or validation (e.g., `xunit:OrderTests.Total_AppliesDiscount`). The signature abstracts away transient details and captures the semantic identity of the failure.

**Oscillation is detected when:**

A signature that was previously present in `failureHistory`, then resolved (absent in a subsequent evaluation within the same `runId`), then **reappears** in `failureHistory` again within the same `runId`.

```
failureHistory sequence within a single runId:
[
  { iteration: 1, signature: S, ... },  // S present at iteration 1
  { iteration: 2, signature: !=S, ... }, // S absent at iteration 2 (resolved)
  { iteration: 3, signature: S, ... }   // S reappears at iteration 3 → OSCILLATION
]
```

The oscillation check runs **before** the cap check in the outer loop. When detected, the system immediately stops and escalates.

## Behavior on Detection

When oscillation is detected at iteration N:

1. **Stop immediately** — do NOT consume remaining iterations, do NOT retry the Fix Agent again
2. Update `plans/harness-state.json`:
   ```json
   {
     "phase": "escalated",
     "escalation": {
       "reason": "oscillation",
       "detail": "OrderService <-> PaymentService coupling detected",
       "signatures": [
         "xunit:OrderTests.Total_AppliesDiscount",
         "xunit:PaymentTests.Refund_NegativeAmount"
       ]
     }
   }
   ```
   The `failureHistory` entries include iteration numbers for debugging — no separate `iteration` field is needed in `escalation`.
3. **Surface to user** — explicitly identify which signatures and components are cycling, so the human can see the architectural coupling

## Rationale

Oscillation signals a coupling problem between components. The failures are not independent bugs; they represent a structural conflict in how two or more components interact. No amount of autonomous bug-fixing will resolve a coupling problem — doing so requires human architectural judgment (e.g., rethinking the refund policy, re-layering responsibilities, or refactoring the contract between services).

Continuing to dispatch the Fix Agent in an oscillation scenario would waste tokens and make the problem worse, not better. This harness applies distributed systems thinking to the AI context: recognise the *class* of problem and escalate appropriately.

## Concrete Example

The following `failureHistory` sequence triggers oscillation detection:

```json
{
  "runId": "run-2026-05-31-001",
  "failureHistory": [
    {
      "iteration": 1,
      "signature": "xunit:OrderTests.Total_AppliesDiscount",
      "component": "OrderService",
      "testName": "OrderTests.Total_AppliesDiscount",
      "framework": "xunit"
    },
    {
      "iteration": 2,
      "signature": "xunit:PaymentTests.Refund_NegativeAmount",
      "component": "PaymentService",
      "testName": "PaymentTests.Refund_NegativeAmount",
      "framework": "xunit"
    },
    {
      "iteration": 3,
      "signature": "xunit:OrderTests.Total_AppliesDiscount",
      "component": "OrderService",
      "testName": "OrderTests.Total_AppliesDiscount",
      "framework": "xunit"
    }
  ]
}
```

**Timeline:**
- **Iteration 1:** `xunit:OrderTests.Total_AppliesDiscount` fails. Fix Agent patches `OrderService` discount logic.
- **Iteration 2:** Discount test now passes. But a new test fails: `xunit:PaymentTests.Refund_NegativeAmount` (the discount fix introduced invalid negative refunds). Fix Agent patches `PaymentService` refund validation.
- **Iteration 3:** Refund test now passes. Evaluation runs again and discovers `xunit:OrderTests.Total_AppliesDiscount` is failing *again* (the refund validation is too strict and breaks order totals). Oscillation detected.

**Root cause:** Discounts, refunds, and order totals are coupled. You cannot fix one without understanding all three; fixing in isolation will always break something else.

**Human action required:** Review the refund policy contract, possibly refactor the discount calculation to decouple from refund logic, or introduce a coordination test that validates discount + refund together.

## Implementation Notes

- Signature computation must be deterministic and stable across runs (use framework + test name)
- The oscillation check is O(n^2) in worst case (for each failure, check if it appeared earlier), but n is small (max 3 iterations, typically 1–2 failures per iteration), so performance is not a concern
- The `failureHistory` entries already carry iteration numbers; do not add a redundant `iteration` field to the `escalation` object
