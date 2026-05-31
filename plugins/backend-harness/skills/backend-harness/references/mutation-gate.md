# Mutation Gate

> See `references/state-schema.md` for the canonical `harness-state.json` structure and field semantics.

## When It Runs

The mutation gate runs **after functional tests pass** — specifically at step 9 in the outer orchestration loop, once all unit tests and integration tests are green across all components. The gate does NOT run on functionally broken code.

This placement is critical: mutation testing is expensive (it synthesizes code variants and re-runs tests). Spending that cost on code that still has basic functional failures is wasteful. By gating mutations behind a functional-pass requirement, we avoid analyzing mutant quality for code that doesn't yet work.

## Diff-Scoping: the gate scores CHANGED LINES only

The gate judges the quality of **the work this run produced** — not pre-existing test debt the run never touched. It scores only the mutants that fall on **lines changed in this run** (the diff against the run's base ref). A mutant on an unchanged line is ignored.

**Why line-level, not whole-file:** a whole-file mutation score is an average across every mutant in the file. Well-tested new code can dilute an untested neighbour in the same file — a file can clear its threshold while a freshly-added method is completely untested. Conversely, penalising a file for pre-existing untested code the run never modified is wrong: the harness should be accountable for what it wrote, not for inherited debt. Scoring only changed lines fixes both.

**Why the harness does this itself (not Stryker `--since`):** Stryker.NET's native `--since` diff mode relies on libgit2 diff resolution that **does not work inside a git worktree** (it reports "0 files changed" / "No branch or tag or commit found"). The harness *always* runs in a worktree (outer-loop Step 2), so `--since` is unusable here. Instead the harness runs a **full** `dotnet stryker` (which works in worktrees) and re-scopes the report itself using `git diff` (which works fine in worktrees).

### The helper: `scripts/diff-scope-mutation.py`

The harness invokes the committed helper rather than parsing diffs ad hoc, so the gate is deterministic and unit-tested (`scripts/test_diff_scope_mutation.py`).

```
diff-scope-mutation.py \
  --report   <StrykerOutput/**/reports/mutation-report.json> \
  --base     <git ref the worktree forked from, e.g. main> \
  --config   <harness.config.json> \
  --repo-root <absolute git repo root of the worktree>
```

What it does:
1. Runs `git -C <repo-root> diff --unified=0 <base>` and parses the hunks into `{file: {changed new-side line numbers}}`.
2. For each file in the Stryker report, keeps only mutants whose `location.start.line` is a changed line.
3. Computes a **diff-scoped** per-file score = `killed / (killed + survived + noCoverage)` over those mutants.
4. Maps each changed file to its tier (see below) and compares against the threshold.

Output (stdout JSON) and exit code:
- `{"gate": "pass"|"fail", "files": [{path, tier, threshold, score, killed, survived, noCoverage, changedMutants, verdict}], "failing": [...]}`
- Exit `0` = gate passes (or nothing to gate), `1` = gate fails, `2` = usage/IO error.

Files whose changed lines carry no mutable code (e.g. a comment- or signature-only change) are **not gated** — there is nothing to measure.

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
  "mutationThresholds": { "validators": 80, "services": 70, "controllers": 60 }
}
```

## File-to-Tier Mapping

A changed file's tier is determined by glob patterns in `harness.config.json`:

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

1. For each **changed file that has mutants on its changed lines**, check it against the glob patterns in validators → services → controllers order.
2. Use the first tier whose glob matches.
3. If no glob matches, default to the lowest configured threshold (60% in the reference stack).

### Concrete Example (line-scoped)

A run adds a new `Refund` method to `src/Services/PaymentService.cs` and leaves the pre-existing `Charge` happy-path coverage untouched.

- Stryker (full run) reports, say, 25 mutants across `PaymentService.cs`: the `Refund` lines are well-killed; the old `Charge` guard lines have survivors.
- The gate keeps only mutants on the **changed** lines (the `Refund` additions). Those are well-tested → diff-scoped score ~100% → **pass**.
- The untested `Charge` guards are on **unchanged** lines → ignored. They are pre-existing debt this run did not touch; the gate does not penalise the run for them.

The mirror case: if the run's *own* new lines are undertested (e.g. it adds a method with an unguarded branch and no test), those mutants survive on changed lines → diff-scoped score low → **gate fails**, and the fix loop is entered.

## Gate Failure Path

When one or more changed files fail their tier threshold:

1. **Re-enter the fix loop** — dispatch the Fix Agent targeting the mutation-weak component (the file that failed), with context: "functionally correct but the changed lines are under-tested; add tests for the uncovered branches."
2. **Count against the iteration cap** — a mutation failure consumes one of the 3 available fix iterations for that component.
3. **If the cap is reached** — escalate to human with `reason: "cap_exceeded"`.

Example state after a mutation gate failure on the first iteration:

```json
{
  "phase": "fix",
  "iterations": { "PaymentService": 1 },
  "evaluation": { "lastStrategy": "full" },
  "failureHistory": [
    { "iteration": 1, "signature": "mutation:src/Services/PaymentService.cs#services:0%", "component": "PaymentService" }
  ]
}
```

## Rationale

Mutation testing is a quality gate, not a functional gate. It validates that the tests are *good* — that they would catch real bugs if the code were subtly broken. Scoping to changed lines makes the gate accountable to the run's own work:

1. **Efficiency** — mutation analysis only on functionally-sound code.
2. **Fair attribution** — the run is judged on what it changed, not inherited debt.
3. **No dilution** — well-tested new code cannot mask an untested change in the same file.
4. **Tier-appropriate rigor** — validators (pure logic) demand 80%; controllers (thin routing) tolerate 60%.
