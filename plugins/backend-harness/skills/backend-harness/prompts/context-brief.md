# Context Brief Generation Prompt

**Role:** You are surveying an existing codebase to orient implementer subagents. Your output is a codebase-orientation brief, not a spec — you describe what exists, never what to build.

## Hard Constraint

**Describe what EXISTS. Do NOT restate or infer from the spec. Do NOT describe what should be built.** This brief is purely orientation for developers who are new to the codebase. The spec/plan is provided separately.

## Your Task

You will inspect the actual codebase and write `plans/context-brief.md` in the target repository (the path is provided as input).

### What to Inspect

1. **Directory and layout structure** — where source code lives, where tests live, where infrastructure/deployment configs are, where documentation is
2. **Key conventions** — how services/components are registered (DI pattern), how validation is done, how errors are handled, how configuration is bound
3. **Test layout and conventions** — where unit tests live, how they are organized, test runner framework, naming conventions (e.g., `[Trait("Category", "Unit")]`), how integration tests differ from unit tests
4. **Integration points and external services** — what databases, message queues, external APIs, or other services the codebase already integrates with; how these are configured
5. **Notable gotchas** — things that would surprise a developer new to this repo; non-obvious patterns, tricky dependencies, known architectural quirks, setup steps required to run tests locally

### What to Write

Create a document `plans/context-brief.md` with these sections (in order):

#### Section 1: Directory & Layout Map
- Overview of the repo structure (src, tests, infrastructure, config, build outputs)
- Where the main application code lives
- Where tests are organized (unit, integration, etc.)
- Where infrastructure/deployment code is (if present)
- Any significant subdirectories that have their own responsibilities

#### Section 2: Key Conventions
- **DI/Registration Pattern:** How services and dependencies are registered (e.g., `Startup.cs`, `IServiceCollection`, constructor injection)
- **Validation Approach:** How input validation is done (attributes, custom validators, FluentValidation, etc.)
- **Error Handling Style:** How errors are caught, logged, and propagated; exception hierarchy if custom exceptions exist
- **Configuration Binding:** How environment and `appsettings.json` values are bound to strongly-typed config objects

#### Section 3: Test Layout & Conventions
- **Directory location:** Where unit tests live (e.g., `*.Tests/`, `tests/unit/`)
- **How tests are run:** Command to run all tests (e.g., `dotnet test`)
- **Naming conventions:** Pattern for test class names, test method names; any test category/trait attributes used
- **Framework:** What test framework is used (xUnit, NUnit, MSTest, etc.)
- **Integration tests:** If present, how they differ from unit tests; do they require live services, databases, etc.?

#### Section 4: Integration Points & External Services
- List any external services the codebase already integrates with (databases, message brokers, third-party APIs, caches, etc.)
- For each, note: what it is, how it's configured (env var, config section), what the codebase uses it for
- If no external services are observed, write "None observed."

#### Section 5: Notable Gotchas
- Non-obvious patterns or architectural decisions
- Tricky dependencies between components
- Setup steps required to run tests locally (e.g., Docker containers, database migrations)
- Known quirks or workarounds in the codebase
- If none, write "None observed."

### Stop Condition

Stop inspecting and write the brief when you have covered all five sections above from **actual file inspection**. Do not speculate or infer. If a section has nothing notable in the codebase, write "None observed." Do not skip sections.

### Output Contract

- Write the brief to `plans/context-brief.md` in the target repository
- Return with status **DONE** and confirm the path where the file was written
- Include a one-line summary of the codebase type (e.g., "ASP.NET Core REST API with Entity Framework", "Node.js Express microservice")

---

## Input You Will Receive

The orchestrator will provide:
- **`worktree`** — absolute path to the target repository (the worktree directory)
- **`spec`** — the implementation spec/plan (for reference only; do not describe what should be built)

Use these to navigate and understand the codebase.
