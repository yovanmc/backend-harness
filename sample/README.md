# OrdersApi — Backend Harness Validation Fixture

## Purpose

This is the end-to-end validation fixture for the [`backend-harness`](../) Claude Code plugin: a small, real **brownfield .NET 10 Orders API** used to demonstrate the harness against real tooling — xUnit for tests and [Stryker.NET](https://stryker-mutator.io/docs/stryker-net/introduction/) for mutation testing.

It is deliberately seeded so that running `/harness-implement` against it makes the harness's two core quality gates **visibly fire**: the functional fix loop and the tiered mutation gate.

## The two seeded conditions

**1. Functional fix-loop seed (`OrderService`)**

`OrderService.CalculateTotal` contains a real bug: it *adds* the discount instead of subtracting it (`subtotal + discount` rather than `subtotal - discount`). The unit test `OrderServiceTests.Total_AppliesDiscount` is committed **RED** (expects 90 for a 100 subtotal at 10% off; the bug returns 110).

When the harness runs its full unit evaluation, the Backend Evaluator catches this failing test and dispatches the Fix Agent for the `OrderService` component.

**2. Mutation-gate seed (`PaymentService`)**

`PaymentService` ships with **happy-path-only tests**. `PaymentService.Charge` has three branches (non-positive amount, amount exceeding order total, success) but only the success path is exercised. A *whole-file* Stryker run scores `PaymentService.cs` **below the `services` tier threshold (70%)** — you can confirm this directly (see "Verifying the seeds" below: ~46%).

**Important — the gate is diff-scoped (line-level).** The harness's mutation gate scores only the mutants on the lines **this run changed**, not the whole file (see [`mutation-gate.md`](../plugins/backend-harness/skills/backend-harness/references/mutation-gate.md) for why). So on the refund-feature run, the gate measures the harness's *new* `Refund` code — which the inner loop tests well — and **passes**. The pre-existing thin `Charge` coverage sits on **unchanged** lines and is correctly out of scope: it's inherited debt the run never touched.

The gate *trips* when the harness under-tests **its own changed lines** — e.g. if it added a guard branch with no test. That behavior is proven deterministically by the gate's unit tests (`plugins/backend-harness/skills/backend-harness/scripts/test_diff_scope_mutation.py`), which cover both the "undertested change fails" and "well-tested change passes despite untested neighbours" cases. The whole-file 46% figure here is the *standalone* mutation measurement, not what the diff-scoped gate sees during the feature run.

## Prerequisites

- .NET SDK 10, with `dotnet` on your `PATH` (if your SDK is in a non-standard location, see [Troubleshooting](#troubleshooting-dotnet-not-on-path) below)
- Stryker.NET: `dotnet tool install -g dotnet-stryker`
- The [`backend-harness`](../) plugin installed (see the root README)
- The `superpowers` plugin installed (the harness's inner loop depends on it)

## Verifying the seeds (deterministic, no harness)

You can confirm the seeds are real before involving the harness. Run from `sample/OrdersApi`:

```bash
# Functional seed: exactly one RED unit test
dotnet test --filter Category=Unit
# Expected: 3 passed, 1 failed — the failure is OrderServiceTests.Total_AppliesDiscount

# Integration tests are green
dotnet test --filter Category=Integration
# Expected: all pass

# Mutation seed: PaymentService.cs below the 70% services threshold
# (Stryker needs a green baseline — see "Confirming the mutation seed" below)
dotnet stryker
# Expected: report shows PaymentService.cs mutation score < 70%

# API smoke check
./scripts/api-smoke.sh
# Expected: api-smoke PASS: GET /orders/1/total -> 200, body=50
```

> **Confirming the mutation seed in isolation:** Stryker requires a passing test baseline to determine which mutants are killed, but the functional seed keeps the unit suite RED. To measure the mutation seed cleanly, temporarily apply the discount fix, run Stryker, then restore the seeded bug:
> ```bash
> sed -i.bak 's/return subtotal + discount;/return subtotal - discount;/' src/OrdersApi/Services/OrderService.cs
> dotnet test --filter Category=Unit   # now all green
> dotnet stryker                        # PaymentService.cs < 70%
> mv src/OrdersApi/Services/OrderService.cs.bak src/OrdersApi/Services/OrderService.cs
> dotnet build src/OrdersApi/OrdersApi.csproj   # force recompile so the restored bug is rebuilt
> dotnet test --filter Category=Unit   # RED again — seed restored
> ```

## Running the end-to-end demonstration

1. Open a Claude Code session with the working directory set to `sample/OrdersApi`.
2. Run `/harness-implement`. The demo plan at `plans/2026-05-31-add-refunds-plan.md` (add refund support) is already present, so the harness goes straight into its outer loop.
3. Watch the harness generate a Context Brief (this is a brownfield repo), implement the refund feature via the inner loop (superpowers `subagent-driven-development`), then run the full evaluation.

## Expected convergence trace

A human observing the run should see, in order:

1. **Context Brief generated** (`plans/context-brief.md`) — the repo is non-trivial/brownfield.
2. **Inner loop implements** `Refund` + the `POST /orders/{id}/refund` endpoint and commits.
3. **First full evaluation fails** — `OrderServiceTests.Total_AppliesDiscount` is RED → `OrderService` flagged as a failing component.
4. **Fix Agent fixes the discount bug** (`subtotal - discount`); `iterations[OrderService]` becomes 1.
5. **Component-scoped re-eval of `OrderService` passes** — all functional tests (unit + integration + api-smoke) green.
6. **Mutation gate runs (diff-scoped).** The harness runs a full `dotnet stryker`, then `scripts/diff-scope-mutation.py` re-scopes the report to only the lines this run changed. The new `Refund` code (the harness's own work) is well-tested → its changed-line score clears 70% → **gate passes**. The pre-existing thin `Charge` coverage is on *unchanged* lines and is correctly out of scope.
7. **`plans/harness-state.json` reaches `"phase": "done"`**; `superpowers:finishing-a-development-branch` runs.

## Success criteria

The run is a success when:
- The **functional fix loop fired** — the independent evaluator caught the seeded `OrderService` bug (with no shared context with the implementer), the Fix Agent corrected it, and re-evaluation went green; and
- The **diff-scoped mutation gate passed** — the harness's own changed lines (the `Refund` feature) are adequately tested; and
- The final state is `phase=done` with no escalation.

Exact iteration counts depend on live subagent behavior; the acceptance bar is *the functional fix loop converging and the diff-scoped gate ruling on the run's own changes*, not a byte-exact state match.

**On seeing the gate trip:** the mutation gate trips when the harness under-tests **its own changed lines** (not on pre-existing debt). That behavior is proven deterministically by the gate's unit tests (`plugins/backend-harness/skills/backend-harness/scripts/test_diff_scope_mutation.py`) — run `python3 -m unittest` in the `scripts/` directory.

## Troubleshooting: dotnet not on PATH

All commands here (and the harness's `harness.config.json`) assume `dotnet` resolves on your `PATH`. If your SDK is installed in a non-standard location (e.g. `~/.dotnet` rather than `/usr/local/share/dotnet`), commands may fail — and Stryker.NET (a `net8.0` tool that shells out to a bare `dotnet`) will report *"You must install .NET to run this application"* or *"start process 'dotnet' ... No such file or directory"*. Put the SDK and its tools on `PATH` and point `DOTNET_ROOT` at it:

```bash
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$HOME/.dotnet:$HOME/.dotnet/tools:$PATH"
```

This is only needed for non-standard SDK locations; a default install resolves automatically.

## Note on determinism

This is a live, human-observed run, and subagent fix quality varies. If the harness escalates instead (e.g. oscillation detection or the 3-iteration cap), that is **also a valid observation** — it demonstrates the harness's safety behavior. Review `plans/harness-state.json` to see what happened and why.
