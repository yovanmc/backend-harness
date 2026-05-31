# Mutation Gate

> See `references/state-schema.md` for the canonical `harness-state.json` structure and field semantics.

## When It Runs

The mutation gate runs **after functional tests pass** — specifically at step 9 in the outer orchestration loop, once all unit tests and integration tests are green across all components. The gate does NOT run on functionally broken code.

This placement is critical: mutation testing is expensive (it synthesizes code variants and re-runs tests). Spending that cost on code that still has basic functional failures is wasteful. By gating mutations behind a functional-pass requirement, we avoid analyzing mutant quality for code that doesn't yet work.

## Tiered Thresholds

Different code tiers are held to different mutation score thresholds, reflecting the value and risk profile of each tier:

| Tier | Threshold | Rationale |
|------|-----------|-----------|
| Validators | 80% | Pure logic, no I/O, highest mutation kill rate, foundational to correctness |
| Services | 70% | Business logic with integration concerns, moderate complexity |
| Controllers | 60% | Thin routing layers, wire inputs to services, low mutation value |

**Thresholds are configuration-driven**, never hardcoded in the orchestrator. They come from `harness.config.json`:

```json
{
  "mutationThresholds": {
    "validators": 80,
    "services": 70,
    "controllers": 60
  }
}
```

This allows stack maintainers to adjust thresholds per project without modifying the harness core.

## File-to-Tier Mapping

The harness determines a file's tier using glob patterns defined in `harness.config.json`:

```json
{
  "fileTierGlobs": {
    "validators": ["**/Validators/**/*.cs", "**/*Validator.cs"],
    "services": ["**/Services/**/*.cs", "**/*Service.cs"],
    "controllers": ["**/Controllers/**/*.cs", "**/*Controller.cs"]
  }
}
```

### Matching Algorithm

1. For each changed file, check it against the glob patterns in order
2. Use the first tier whose glob matches the file
3. If no glob matches, default to the lowest configured threshold (60%)

### Concrete Example

Changed file: `src/Services/OrderService.cs`

1. Check `validators` globs: `**/Validators/**/*.cs` (no match), `**/*Validator.cs` (no match)
2. Check `services` globs: `**/Services/**/*.cs` (MATCH)
3. Tier assigned: `services`
4. Required threshold: 70%

If the mutation score for changes to `OrderService.cs` is 73%, the file passes the gate. If it's 68%, the gate fails.

Another example: Changed file: `src/Utilities/Helper.cs` (matches no glob)

1. Check all globs: no matches
2. Default tier: lowest threshold
3. Required threshold: 60%

## Gate Failure Path

When one or more changed files fail the mutation threshold:

1. **Re-enter the fix loop** — dispatch the Fix Agent targeting the mutation-weak component (the one that failed the gate)
2. **Count against the iteration cap** — a mutation failure consumes one of the 3 available fix iterations for that component
3. **If the cap is reached** — escalate to human: "3 iterations exhausted; mutation score still below threshold"

Example state after mutation gate failure on iteration 1:

```json
{
  "phase": "fix",
  "iterations": {
    "OrderService": 1
  },
  "evaluation": {
    "lastStrategy": "full"
  },
  "failureHistory": [
    {
      "iteration": 1,
      "signature": "mutation:src/Services/OrderService.cs#services:62%",
      "component": "OrderService"
    }
  ]
}
```

The Fix Agent will receive this context and understand that the code is functionally correct but under-tested. It will focus on test coverage for edge cases and corner logic paths that mutations might expose.

## Rationale

Mutation testing is a quality gate, not a functional gate. It validates that your tests are *good* — that they will catch real bugs if the code is subtly broken. By running mutations only on functionally-sound code, we ensure:

1. **Efficiency** — no wasted mutation analysis on code that doesn't work yet
2. **Quality focus** — forces developers to think about edge cases and corner behaviors
3. **Tier-appropriate rigor** — validators (pure logic) demand high test coverage, controllers (thin routing) can tolerate lower coverage

Thresholds are not arbitrary; they reflect the risk/reward of testing different code layers. A 60% threshold for controllers acknowledges that thin routing layers have less business value per line of code, whereas validators (pure logic) demand 80% because a single mutation in validation logic can slip a bad input through an entire system.
