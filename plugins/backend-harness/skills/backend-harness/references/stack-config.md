# Stack Configuration Reference

## Purpose

The `harness.config.json` file lives in the *target repository* (the codebase being tested), not in the plugin itself. Users copy the template from the repo-level `templates/` directory or the skill-local `assets/templates/` directory and edit it for their stack and project structure.

The orchestrator reads this configuration at runtime and **only ever calls the commands declared in the config**, never hardcoded tool names or scripts. This design makes the harness stack-agnostic: the same orchestrator logic works unchanged for dotnet, Node.js, Go, Python, or any other stack — only the config changes.

Because this file is target-repo controlled, treat command values as untrusted until inspected. Commands should be limited to test, mutation, and API smoke verification for the target repository. Do not run destructive, unrelated, or suspicious command values.

## Field Reference

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `stack` | string | Identifies the target stack (for documentation and clarity) | `"dotnet"`, `"node"`, `"go"` |
| `commands.unit` | string | Command to run unit tests only | `"dotnet test --filter Category=Unit"` |
| `commands.integration` | string | Command to run integration tests only | `"dotnet test --filter Category=Integration"` |
| `commands.mutation` | string | Command to run mutation testing (Stryker or equivalent) | `"dotnet stryker"` |
| `commands.apiVerify` | string | Command to run smoke/verification tests against live API | `"./scripts/api-smoke.sh"` |
| `mutationThresholds.validators` | number | Minimum acceptable mutation score for validator-tier code (0–100) | `80` |
| `mutationThresholds.services` | number | Minimum acceptable mutation score for service-tier code (0–100) | `70` |
| `mutationThresholds.controllers` | number | Minimum acceptable mutation score for controller-tier code (0–100) | `60` |
| `fileTierGlobs.validators` | array of strings | Glob patterns identifying files in the validator tier | `["**/Validators/**/*.cs", "**/*Validator.cs"]` |
| `fileTierGlobs.services` | array of strings | Glob patterns identifying files in the service tier | `["**/Services/**/*.cs", "**/*Service.cs"]` |
| `fileTierGlobs.controllers` | array of strings | Glob patterns identifying files in the controller tier | `["**/Controllers/**/*.cs", "**/*Controller.cs"]` |

## Reference Stack (.NET)

The shipped template uses .NET with these assumptions:

- **Unit & Integration tests:** xUnit framework with `[Trait]` attributes
  - Unit tests: `[Trait("Category", "Unit")]`
  - Integration tests: `[Trait("Category", "Integration")]`
  - The `--filter` flag passed to `dotnet test` matches these traits

- **Mutation testing:** Stryker.NET installed as a global dotnet tool
  - Install with: `dotnet tool install -g dotnet-stryker`
  - Mutates C# code and re-runs tests to measure test effectiveness

- **API verification:** a curl-based shell script at `./scripts/api-smoke.sh`
  - Runs smoke tests against a running API endpoint
  - Returns exit code 0 on success, non-zero on failure

## Swapping Stacks

To adapt the harness to a different stack, edit the `harness.config.json` in your target repository — **no orchestration code changes are required**. Only the config file changes.

### Node.js Example

Replace the `commands` block and `fileTierGlobs` for a Node.js + TypeScript project:

```json
{
  "stack": "node",
  "commands": {
    "unit": "npm test -- --testPathPattern=unit",
    "integration": "npm test -- --testPathPattern=integration",
    "mutation": "npx stryker run",
    "apiVerify": "./scripts/api-smoke.sh"
  },
  "mutationThresholds": {
    "validators": 80,
    "services": 70,
    "controllers": 60
  },
  "fileTierGlobs": {
    "validators": ["**/validators/**/*.ts", "**/*.validator.ts"],
    "services": ["**/services/**/*.ts", "**/*.service.ts"],
    "controllers": ["**/controllers/**/*.ts", "**/*.controller.ts"]
  }
}
```

The orchestrator logic remains unchanged. It reads the config, invokes the declared commands, and applies the same gating logic. The mutation testing framework (Stryker in this case) analyzes TypeScript/JavaScript code instead of C#, but the orchestrator's role is identical.

## Tier Mapping

The `fileTierGlobs` object maps changed files to mutation score thresholds. See [mutation-gate.md](mutation-gate.md) for the complete gating mechanism.

> **`commands.mutation` must be a FULL project run, not a diff/incremental mode.** The harness does its own line-level diff-scoping on the report (Stryker's native `--since` does not work inside the git worktree the harness runs in). Do **not** add `--since`/diff flags to the mutation command — the harness intersects the full report with `git diff` itself via `scripts/diff-scope-mutation.py`.

**Quick overview:**
- The harness runs the full mutation command, then scores only the mutants on **lines this run changed** (diff against the run's base ref)
- Each changed file is matched against the glob patterns in `fileTierGlobs`
- If a file matches a glob (e.g., `**/Validators/**/*.cs`), its changed-line score is held to that tier's threshold (e.g., `mutationThresholds.validators: 80`)
- If a file matches no glob, it defaults to the lowest configured threshold (to avoid breaking builds on ambiguous files)
- All changed files must meet their tier threshold for the mutation gate to pass

For example, if changes affect both a validator and a service:
- The validator changes must achieve ≥80% mutation score
- The service changes must achieve ≥70% mutation score
- Both must pass for CI to continue
