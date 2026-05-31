# Dry-Run Orchestration Verification

## Section 1 — What This Tests

This dry-run exercises the outer loop logic of the backend-harness orchestrator deterministically using canned evaluator returns from `eval-results.fixture.json`. No real .NET build or test suite is required.

**What it proves:**

- **Disk-state persistence:** `plans/harness-state.json` is written and updated at each step, surviving any context compaction during the session.
- **Graduated re-evaluation strategy selection:** The orchestrator selects `"full"` on call 1 (`iterations[OrderService] == 0`), `"component-scoped"` on call 2 (`iterations[OrderService] == 1`), and `"full"` again on call 3 (`iterations[OrderService] == 1`).
- **Oscillation detection triggering before the 3-iteration cap:** The signature `xunit:OrderTests.Total_AppliesDiscount` appears at call 1, resolves at call 2, and reappears at call 3. The oscillation check runs before the cap check and stops the run immediately.
- **Correct `phase=escalated` final state:** The harness writes `escalation.reason = "oscillation"` and stops without dispatching another fix attempt.

## Section 2 — Setup

Pre-conditions:

- The backend-harness plugin is installed in your Claude Code environment (verify via `ls ~/.claude/plugins/backend-harness/` or equivalent).
- A target repository with a `plans/` directory and at least one `plans/*.md` plan file (any content; it just needs to exist so the harness has a plan to read).
- A `harness.config.json` in the target repository root. Copy from `templates/harness.config.json` in this repo as a starting point.

## Section 3 — How to Run the Dry-Run

This dry-run requires manual injection of canned evaluator results at each dispatch point. Steps:

1. Open a Claude Code session in your target repository.
2. Run `/harness-implement`.
3. The harness will proceed through the `brief` and `implement` phases normally, then enter the `evaluate` phase and dispatch the Backend Evaluator.
4. **Intercept the first evaluator dispatch:** instead of letting it run real commands, paste the result from `sequence[0]` in `eval-results.fixture.json` as the evaluator's response. Specifically, return `overall: "fail"` with OrderService failing on `xunit:OrderTests.Total_AppliesDiscount`.
5. The orchestrator will record this failure, increment `iterations[OrderService]` to 1, and dispatch the Fix Agent for OrderService.
6. After the Fix Agent completes, the orchestrator dispatches the Backend Evaluator again with strategy `"component-scoped"` (scope: OrderService only).
7. **Intercept the second evaluator dispatch:** paste the result from `sequence[1]`. Return `overall: "pass"` with OrderService passing. No fix is needed after this.
8. The orchestrator runs a full regression eval (graduated re-eval: after component-scoped pass → full check) and dispatches the Backend Evaluator a third time with strategy `"full"`.
9. **Intercept the third evaluator dispatch:** paste the result from `sequence[2]`. Return `overall: "fail"` with OrderService failing again on `xunit:OrderTests.Total_AppliesDiscount` (same signature as call 1).
11. The orchestrator should detect oscillation (same signature appeared, resolved, reappeared within the same `runId`) and stop immediately.

**Note:** This dry-run requires manual intervention at each evaluator dispatch to inject canned results. A future improvement could automate this via a mock evaluator config option in `harness.config.json`.

## Section 4 — Expected Outcome

After the third evaluator response is injected:

- The harness stops without dispatching another Fix Agent turn.
- The harness surfaces the oscillation to the user, identifying `xunit:OrderTests.Total_AppliesDiscount` and the OrderService/PaymentService coupling as the root cause.
- `plans/harness-state.json` in the target repository contains (at minimum):
  - `"phase": "escalated"`
  - `"escalation.reason": "oscillation"`
  - `"xunit:OrderTests.Total_AppliesDiscount"` in `escalation.signatures`
  - `"iterations": { "OrderService": 1 }`
  - `"evaluation.lastStrategy": "full"`

The full expected state is in `harness-state.fixture.json`.

## Section 5 — Assertion

Run this Python script from the target repository root to verify `plans/harness-state.json` against the fixture:

```python
import json

FIXTURE_PATH = '/path/to/backend-harness/test/dry-run/harness-state.fixture.json'
STATE_PATH = 'plans/harness-state.json'

exp = json.load(open(FIXTURE_PATH))
got = json.load(open(STATE_PATH))

assert got['phase'] == 'escalated', f"Expected phase=escalated, got {got['phase']}"
assert got['escalation']['reason'] == 'oscillation', f"Expected reason=oscillation, got {got['escalation']['reason']}"
for sig in exp['escalation']['signatures']:
    assert sig in got['escalation']['signatures'], f"Missing signature: {sig}"
assert got['iterations'] == exp['iterations'], f"Iteration mismatch: {got['iterations']} vs {exp['iterations']}"
assert got['evaluation']['lastStrategy'] == exp['evaluation']['lastStrategy'], f"Strategy mismatch: {got['evaluation']['lastStrategy']} vs {exp['evaluation']['lastStrategy']}"
print('dry-run PASS: oscillation detected, correct state persisted')
```

Replace `/path/to/backend-harness` with the absolute path to this repo on your machine.
