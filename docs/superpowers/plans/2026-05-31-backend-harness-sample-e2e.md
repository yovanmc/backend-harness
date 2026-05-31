# Backend Harness Sample + E2E Implementation Plan (Plan 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small, real .NET 10 brownfield sample API (`sample/OrdersApi`) seeded with a genuine bug (caught by a real failing xUnit test) and a thinly-tested service (low Stryker mutation kill-rate), plus the demo feature plan and documentation that let a human run `/harness-implement` end-to-end and watch the harness converge to `phase=done` — proving the functional fix loop and the mutation gate fire against real tooling.

**Architecture:** An ASP.NET Core (.NET 10) Orders API with `OrderService` (seeded discount bug), `PaymentService` (thinly-tested `Charge`), and `OrdersController`. xUnit tests use `[Trait("Category", ...)]`. Stryker.NET provides real mutation testing. The repo ships a `harness.config.json` and a demo plan asking the harness to add refund support; running `/harness-implement` surfaces the seeded bug via full-suite evaluation (fix loop) and trips the mutation gate on the changed `PaymentService.cs` (second fix loop), then reaches `phase=done`.

**Tech Stack:** .NET 10 (`~/.dotnet/dotnet`, SDK 10.0.203), ASP.NET Core, xUnit, Stryker.NET (`dotnet-stryker`), Bash + curl for API smoke, WebApplicationFactory for integration tests.

**Prerequisite from Plan 1:** The `backend-harness` plugin (committed in this repo) is complete. This plan builds the validation fixture for it.

**Important execution notes:**
- Use the absolute dotnet path `~/.dotnet/dotnet` in all commands (it is not assumed to be on `PATH`).
- The final end-to-end harness run (Task 9) is a **manual, human-observed demonstration** — it depends on live subagent behavior and is not a deterministic automated assertion. Tasks 1–8 build and verify the sample deterministically; Task 9 documents and (optionally) performs the live run.

---

## File Structure

All paths relative to repo root `backend-harness/`. The sample lives entirely under `sample/OrdersApi/`.

| File | Responsibility |
|---|---|
| `sample/OrdersApi/OrdersApi.sln` | Solution referencing src + test projects |
| `sample/OrdersApi/src/OrdersApi/OrdersApi.csproj` | ASP.NET Core web project (.NET 10) |
| `sample/OrdersApi/src/OrdersApi/Program.cs` | Host: DI registration + MapControllers; `public partial class Program` for tests |
| `sample/OrdersApi/src/OrdersApi/Models/Order.cs` | `Order` model |
| `sample/OrdersApi/src/OrdersApi/Models/OrderItem.cs` | `OrderItem` model |
| `sample/OrdersApi/src/OrdersApi/Services/OrderService.cs` | `IOrderService` + `OrderService.CalculateTotal` — **seeded discount bug** |
| `sample/OrdersApi/src/OrdersApi/Services/PaymentService.cs` | `IPaymentService` + `PaymentService.Charge` — **thinly tested** |
| `sample/OrdersApi/src/OrdersApi/Controllers/OrdersController.cs` | `GET /orders/{id}/total` |
| `sample/OrdersApi/tests/OrdersApi.Tests/OrdersApi.Tests.csproj` | xUnit project referencing src |
| `sample/OrdersApi/tests/OrdersApi.Tests/OrderServiceTests.cs` | Unit tests incl. **seeded RED** `Total_AppliesDiscount` |
| `sample/OrdersApi/tests/OrdersApi.Tests/PaymentServiceTests.cs` | Happy-path-only test (mutation seed) |
| `sample/OrdersApi/tests/OrdersApi.Tests/OrdersApiIntegrationTests.cs` | Integration test via `WebApplicationFactory` |
| `sample/OrdersApi/stryker-config.json` | Stryker.NET config |
| `sample/OrdersApi/harness.config.json` | Harness commands + tiered thresholds for the sample |
| `sample/OrdersApi/scripts/api-smoke.sh` | curl HTTP semantic smoke for `apiVerify` |
| `sample/OrdersApi/.gitignore` | Ignore build output + runtime harness state |
| `sample/OrdersApi/plans/2026-05-31-add-refunds-plan.md` | The demo feature plan the harness implements |
| `sample/README.md` | Seeded conditions, e2e demonstration procedure, expected convergence trace |

---

## Task 1: Solution & project scaffolding

**Files:**
- Create: `sample/OrdersApi/src/OrdersApi/OrdersApi.csproj`
- Create: `sample/OrdersApi/tests/OrdersApi.Tests/OrdersApi.Tests.csproj`
- Create: `sample/OrdersApi/OrdersApi.sln`
- Create: `sample/OrdersApi/.gitignore`

- [ ] **Step 1: Create the web project file**

Create `sample/OrdersApi/src/OrdersApi/OrdersApi.csproj`:

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>

</Project>
```

- [ ] **Step 2: Create the test project file**

Create `sample/OrdersApi/tests/OrdersApi.Tests/OrdersApi.Tests.csproj`:

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.11.1" />
    <PackageReference Include="xunit" Version="2.9.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="10.0.0" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="../../src/OrdersApi/OrdersApi.csproj" />
  </ItemGroup>

</Project>
```

- [ ] **Step 3: Create the .gitignore**

Create `sample/OrdersApi/.gitignore`:

```gitignore
# Build output
bin/
obj/
# Stryker output
StrykerOutput/
# Harness runtime state (the demo plan itself IS committed; these are generated)
plans/harness-state.json
plans/context-brief.md
```

- [ ] **Step 4: Create the solution and add projects**

Run:
```bash
cd "sample/OrdersApi"
~/.dotnet/dotnet new sln --name OrdersApi --force
~/.dotnet/dotnet sln add src/OrdersApi/OrdersApi.csproj
~/.dotnet/dotnet sln add tests/OrdersApi.Tests/OrdersApi.Tests.csproj
```
Expected: "Project ... added to the solution." for both.

- [ ] **Step 5: Verify the (empty) solution builds**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet build
```
Expected: Build succeeded. (The web project needs at least a `Program.cs`; if the build fails because `Program.cs` is missing, that is expected — proceed to Task 2/5 which add it. If it fails for any other reason, fix before continuing.)

> Note: If Step 5 fails solely due to a missing entry point, that is acceptable at this stage; the build is fully green by Task 5. Do not add a placeholder Program.cs here — Task 5 owns it.

- [ ] **Step 6: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/OrdersApi.sln sample/OrdersApi/src/OrdersApi/OrdersApi.csproj sample/OrdersApi/tests/OrdersApi.Tests/OrdersApi.Tests.csproj sample/OrdersApi/.gitignore
git commit -m "feat(sample): scaffold OrdersApi solution and projects"
```

---

## Task 2: Domain models

**Files:**
- Create: `sample/OrdersApi/src/OrdersApi/Models/Order.cs`
- Create: `sample/OrdersApi/src/OrdersApi/Models/OrderItem.cs`

- [ ] **Step 1: Create `OrderItem.cs`**

```csharp
namespace OrdersApi.Models;

public class OrderItem
{
    public string Name { get; set; } = string.Empty;
    public decimal UnitPrice { get; set; }
    public int Quantity { get; set; }
}
```

- [ ] **Step 2: Create `Order.cs`**

```csharp
namespace OrdersApi.Models;

public class Order
{
    public int Id { get; set; }
    public List<OrderItem> Items { get; set; } = new();

    /// <summary>Whole-number percentage, e.g. 10 means a 10% discount.</summary>
    public decimal DiscountPercent { get; set; }
}
```

- [ ] **Step 3: Verify compilation**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet build src/OrdersApi/OrdersApi.csproj
```
Expected: Build succeeded (the web project may still warn/fail on missing entry point; the Models compile cleanly). If the only error is the missing entry point, proceed.

- [ ] **Step 4: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/src/OrdersApi/Models/
git commit -m "feat(sample): add Order and OrderItem models"
```

---

## Task 3: OrderService with seeded discount bug (functional fix-loop seed)

This task deliberately ships a **real bug**: the discount is *added* instead of *subtracted*. The unit test `Total_AppliesDiscount` asserts the correct behavior and will be **RED**. This is the seed the harness's Backend Evaluator catches at the functional-evaluation step, driving the fix loop on the `OrderService` component.

**Files:**
- Create: `sample/OrdersApi/src/OrdersApi/Services/OrderService.cs`
- Create: `sample/OrdersApi/tests/OrdersApi.Tests/OrderServiceTests.cs`

- [ ] **Step 1: Write the OrderService with the seeded bug**

Create `sample/OrdersApi/src/OrdersApi/Services/OrderService.cs`:

```csharp
using OrdersApi.Models;

namespace OrdersApi.Services;

public interface IOrderService
{
    decimal CalculateTotal(Order order);
}

public class OrderService : IOrderService
{
    public decimal CalculateTotal(Order order)
    {
        var subtotal = 0m;
        foreach (var item in order.Items)
        {
            subtotal += item.UnitPrice * item.Quantity;
        }

        var discount = subtotal * (order.DiscountPercent / 100m);

        // SEEDED BUG: a discount must REDUCE the total. This adds it instead.
        // The harness fix loop is expected to change this to `subtotal - discount`.
        return subtotal + discount;
    }
}
```

- [ ] **Step 2: Write the unit tests (one deliberately RED, others green)**

Create `sample/OrdersApi/tests/OrdersApi.Tests/OrderServiceTests.cs`:

```csharp
using OrdersApi.Models;
using OrdersApi.Services;
using Xunit;

namespace OrdersApi.Tests;

public class OrderServiceTests
{
    private static Order OrderWith(decimal unitPrice, int qty, decimal discountPercent) => new()
    {
        Id = 1,
        DiscountPercent = discountPercent,
        Items = new List<OrderItem>
        {
            new() { Name = "Widget", UnitPrice = unitPrice, Quantity = qty }
        }
    };

    [Trait("Category", "Unit")]
    [Fact]
    public void Total_NoItems_ReturnsZero()
    {
        var sut = new OrderService();
        var order = new Order { Id = 1, DiscountPercent = 10 };

        Assert.Equal(0m, sut.CalculateTotal(order));
    }

    [Trait("Category", "Unit")]
    [Fact]
    public void Total_NoDiscount_ReturnsSubtotal()
    {
        var sut = new OrderService();
        var order = OrderWith(unitPrice: 25m, qty: 2, discountPercent: 0);

        Assert.Equal(50m, sut.CalculateTotal(order));
    }

    [Trait("Category", "Unit")]
    [Fact]
    public void Total_AppliesDiscount()
    {
        // Subtotal 100, 10% discount => 90. The seeded bug returns 110.
        var sut = new OrderService();
        var order = OrderWith(unitPrice: 50m, qty: 2, discountPercent: 10);

        Assert.Equal(90m, sut.CalculateTotal(order));
    }
}
```

- [ ] **Step 3: Run the unit tests and confirm exactly the seeded test fails**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet test --filter "Category=Unit"
```
Expected: 2 passed, 1 failed. The failing test is `OrderServiceTests.Total_AppliesDiscount` with message asserting `Expected: 90` / `Actual: 110`. The other two pass. **This RED state is intentional — do not fix it.** It is the seed.

- [ ] **Step 4: Commit (with the bug intact)**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/src/OrdersApi/Services/OrderService.cs sample/OrdersApi/tests/OrdersApi.Tests/OrderServiceTests.cs
git commit -m "feat(sample): add OrderService with seeded discount bug and RED test"
```

---

## Task 4: PaymentService with thin tests (mutation-gate seed)

`PaymentService.Charge` has three branches (non-positive amount, amount exceeding order total, success). The committed test covers **only the happy path**, leaving the two guard branches and the boundary conditions untested. Stryker mutates this file (e.g. `<=` → `<`, `>` → `>=`, return-value swaps) and the surviving mutants push the kill-rate below the `services` tier threshold (70%). This is the seed the harness's mutation gate catches.

**Files:**
- Create: `sample/OrdersApi/src/OrdersApi/Services/PaymentService.cs`
- Create: `sample/OrdersApi/tests/OrdersApi.Tests/PaymentServiceTests.cs`

- [ ] **Step 1: Write PaymentService**

Create `sample/OrdersApi/src/OrdersApi/Services/PaymentService.cs`:

```csharp
using OrdersApi.Models;

namespace OrdersApi.Services;

public record PaymentResult(bool Success, string Message);

public interface IPaymentService
{
    PaymentResult Charge(Order order, decimal amount);
}

public class PaymentService : IPaymentService
{
    private readonly IOrderService _orderService;

    public PaymentService(IOrderService orderService)
    {
        _orderService = orderService;
    }

    public PaymentResult Charge(Order order, decimal amount)
    {
        if (amount <= 0)
        {
            return new PaymentResult(false, "Amount must be positive.");
        }

        var total = _orderService.CalculateTotal(order);
        if (amount > total)
        {
            return new PaymentResult(false, "Amount exceeds order total.");
        }

        return new PaymentResult(true, "Charged.");
    }
}
```

- [ ] **Step 2: Write the thin happy-path-only test**

Create `sample/OrdersApi/tests/OrdersApi.Tests/PaymentServiceTests.cs`:

```csharp
using OrdersApi.Models;
using OrdersApi.Services;
using Xunit;

namespace OrdersApi.Tests;

public class PaymentServiceTests
{
    private static Order OrderTotaling(decimal amount) => new()
    {
        Id = 1,
        DiscountPercent = 0,
        Items = new List<OrderItem>
        {
            new() { Name = "Widget", UnitPrice = amount, Quantity = 1 }
        }
    };

    // Thin coverage on purpose: only the success path is exercised.
    // The guard branches (amount <= 0, amount > total) are untested,
    // so Stryker mutants survive and the kill-rate falls below the
    // services-tier threshold (70%). The harness mutation gate is
    // expected to drive a fix iteration that adds the missing tests.
    [Trait("Category", "Unit")]
    [Fact]
    public void Charge_ValidAmount_Succeeds()
    {
        var sut = new PaymentService(new OrderService());
        var order = OrderTotaling(100m);

        var result = sut.Charge(order, 50m);

        Assert.True(result.Success);
    }
}
```

- [ ] **Step 3: Confirm the new test passes (and the OrderService seed is still RED)**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet test --filter "Category=Unit"
```
Expected: 3 passed, 1 failed. The only failure remains `OrderServiceTests.Total_AppliesDiscount`. `PaymentServiceTests.Charge_ValidAmount_Succeeds` passes (it uses a 0-discount order, so the OrderService bug does not affect it).

- [ ] **Step 4: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/src/OrdersApi/Services/PaymentService.cs sample/OrdersApi/tests/OrdersApi.Tests/PaymentServiceTests.cs
git commit -m "feat(sample): add PaymentService with intentionally thin tests"
```

---

## Task 5: Controller, host, and integration test

**Files:**
- Create: `sample/OrdersApi/src/OrdersApi/Controllers/OrdersController.cs`
- Create: `sample/OrdersApi/src/OrdersApi/Program.cs`
- Create: `sample/OrdersApi/tests/OrdersApi.Tests/OrdersApiIntegrationTests.cs`

- [ ] **Step 1: Write the controller**

Create `sample/OrdersApi/src/OrdersApi/Controllers/OrdersController.cs`:

```csharp
using Microsoft.AspNetCore.Mvc;
using OrdersApi.Models;
using OrdersApi.Services;

namespace OrdersApi.Controllers;

[ApiController]
[Route("orders")]
public class OrdersController : ControllerBase
{
    private readonly IOrderService _orderService;

    // In-memory seed data. Order 1 has no discount, so GET /orders/1/total
    // returns the correct subtotal even with the seeded discount bug — keeping
    // the integration suite green and localizing the bug to the unit test.
    private static readonly Dictionary<int, Order> Orders = new()
    {
        [1] = new Order
        {
            Id = 1,
            DiscountPercent = 0,
            Items = new List<OrderItem>
            {
                new() { Name = "Widget", UnitPrice = 25m, Quantity = 2 }
            }
        }
    };

    public OrdersController(IOrderService orderService)
    {
        _orderService = orderService;
    }

    [HttpGet("{id}/total")]
    public ActionResult<decimal> GetTotal(int id)
    {
        if (!Orders.TryGetValue(id, out var order))
        {
            return NotFound();
        }

        return Ok(_orderService.CalculateTotal(order));
    }
}
```

- [ ] **Step 2: Write Program.cs**

Create `sample/OrdersApi/src/OrdersApi/Program.cs`:

```csharp
using OrdersApi.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddSingleton<IOrderService, OrderService>();
builder.Services.AddSingleton<IPaymentService, PaymentService>();

var app = builder.Build();

app.MapControllers();

app.Run();

// Exposed so WebApplicationFactory<Program> can host the app in integration tests.
public partial class Program { }
```

- [ ] **Step 3: Write the integration test**

Create `sample/OrdersApi/tests/OrdersApi.Tests/OrdersApiIntegrationTests.cs`:

```csharp
using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace OrdersApi.Tests;

public class OrdersApiIntegrationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public OrdersApiIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    [Trait("Category", "Integration")]
    [Fact]
    public async Task GetTotal_KnownOrder_Returns200WithSubtotal()
    {
        var client = _factory.CreateClient();

        var response = await client.GetAsync("/orders/1/total");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Equal("50", body.Trim());
    }

    [Trait("Category", "Integration")]
    [Fact]
    public async Task GetTotal_UnknownOrder_Returns404()
    {
        var client = _factory.CreateClient();

        var response = await client.GetAsync("/orders/999/total");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }
}
```

- [ ] **Step 4: Build and run the full suite**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet build
~/.dotnet/dotnet test --filter "Category=Unit"
~/.dotnet/dotnet test --filter "Category=Integration"
```
Expected:
- Build succeeded.
- Unit: 3 passed, 1 failed (only `OrderServiceTests.Total_AppliesDiscount` red).
- Integration: 2 passed, 0 failed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/src/OrdersApi/Controllers/ sample/OrdersApi/src/OrdersApi/Program.cs sample/OrdersApi/tests/OrdersApi.Tests/OrdersApiIntegrationTests.cs
git commit -m "feat(sample): add OrdersController, host, and integration tests"
```

---

## Task 6: Stryker config, harness config, and API smoke script

**Files:**
- Create: `sample/OrdersApi/stryker-config.json`
- Create: `sample/OrdersApi/harness.config.json`
- Create: `sample/OrdersApi/scripts/api-smoke.sh`

- [ ] **Step 1: Write the Stryker config**

Create `sample/OrdersApi/stryker-config.json`:

```json
{
  "stryker-config": {
    "project": "OrdersApi.csproj",
    "solution": "OrdersApi.sln",
    "test-projects": ["tests/OrdersApi.Tests/OrdersApi.Tests.csproj"],
    "reporters": ["json", "progress"],
    "thresholds": { "high": 80, "low": 60, "break": 0 }
  }
}
```

> `"break": 0` means Stryker never fails on its own threshold — the **harness** reads the JSON report (`StrykerOutput/**/mutation-report.json`) and applies the tiered thresholds from `harness.config.json`. This keeps tier enforcement in the harness, not Stryker.

- [ ] **Step 2: Write the harness config**

Create `sample/OrdersApi/harness.config.json`:

```json
{
  "stack": "dotnet",
  "commands": {
    "unit": "~/.dotnet/dotnet test --filter Category=Unit",
    "integration": "~/.dotnet/dotnet test --filter Category=Integration",
    "mutation": "~/.dotnet/dotnet stryker",
    "apiVerify": "./scripts/api-smoke.sh"
  },
  "mutationThresholds": {
    "validators": 80,
    "services": 70,
    "controllers": 60
  },
  "fileTierGlobs": {
    "validators": ["**/Validators/**/*.cs", "**/*Validator.cs"],
    "services": ["**/Services/**/*.cs", "**/*Service.cs"],
    "controllers": ["**/Controllers/**/*.cs", "**/*Controller.cs"]
  }
}
```

> `dotnet stryker` requires the Stryker.NET tool. The sample README (Task 8) documents `~/.dotnet/dotnet tool install -g dotnet-stryker`. The `~` in commands assumes a shell that expands it; the harness runs these via a shell.

- [ ] **Step 3: Write the API smoke script**

Create `sample/OrdersApi/scripts/api-smoke.sh`:

```bash
#!/usr/bin/env bash
# HTTP semantic smoke test for the harness `apiVerify` step.
# Boots the API on an ephemeral port, verifies GET /orders/1/total returns
# 200 with the expected body, then shuts the app down. Exits non-zero on
# any failure so the harness treats it as a failing check.
set -euo pipefail

PORT=5199
BASE="http://127.0.0.1:${PORT}"
DOTNET="${DOTNET:-$HOME/.dotnet/dotnet}"

cd "$(dirname "$0")/.."

"$DOTNET" run --project src/OrdersApi/OrdersApi.csproj --urls "$BASE" >/tmp/ordersapi-smoke.log 2>&1 &
APP_PID=$!

cleanup() { kill "$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT

# Wait for the app to accept connections (max ~20s).
for _ in $(seq 1 40); do
  if curl -fsS "${BASE}/orders/1/total" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

STATUS=$(curl -s -o /tmp/ordersapi-body.txt -w "%{http_code}" "${BASE}/orders/1/total")
BODY=$(cat /tmp/ordersapi-body.txt)

if [ "$STATUS" != "200" ]; then
  echo "api-smoke FAIL: GET /orders/1/total returned HTTP $STATUS (expected 200)"
  exit 1
fi

if [ "$(echo "$BODY" | tr -d '[:space:]')" != "50" ]; then
  echo "api-smoke FAIL: body was '$BODY' (expected 50)"
  exit 1
fi

echo "api-smoke PASS: GET /orders/1/total -> 200, body=50"
```

- [ ] **Step 4: Make the script executable and run it**

Run from `sample/OrdersApi`:
```bash
chmod +x scripts/api-smoke.sh
./scripts/api-smoke.sh
```
Expected: `api-smoke PASS: GET /orders/1/total -> 200, body=50`. If the app fails to boot, inspect `/tmp/ordersapi-smoke.log`.

- [ ] **Step 5: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/stryker-config.json sample/OrdersApi/harness.config.json sample/OrdersApi/scripts/api-smoke.sh
git commit -m "feat(sample): add stryker config, harness config, and api smoke script"
```

---

## Task 7: The demo feature plan

This is the plan the **harness** consumes when a human runs `/harness-implement` inside `sample/OrdersApi`. It is written in the superpowers writing-plans format (the same format `/harness-brainstorm` produces). It asks the harness to add refund support, which requires modifying `PaymentService.cs` (making it a changed file so the mutation gate evaluates it) and depends on `OrderService.CalculateTotal` (so the full-suite evaluation surfaces the seeded bug).

**Files:**
- Create: `sample/OrdersApi/plans/2026-05-31-add-refunds-plan.md`

- [ ] **Step 1: Write the demo plan**

Create `sample/OrdersApi/plans/2026-05-31-add-refunds-plan.md`:

````markdown
# Add Refund Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add refund support to the Orders API: a `PaymentService.Refund` method and a `POST /orders/{id}/refund` endpoint.

**Architecture:** Extend the existing `PaymentService` (which already has `Charge`) with a `Refund` method enforcing refund rules, and expose it through a new controller action. Refund validation reuses `IOrderService.CalculateTotal` to determine the maximum refundable amount.

**Tech Stack:** .NET 10, ASP.NET Core, xUnit.

---

### Task 1: PaymentService.Refund

**Files:**
- Modify: `src/OrdersApi/Services/PaymentService.cs`
- Test: `tests/OrdersApi.Tests/PaymentServiceTests.cs`

Add a `Refund(Order order, decimal amount)` method to `IPaymentService` and `PaymentService` returning `PaymentResult`.

**Acceptance criteria:**
- A refund `amount` less than or equal to zero is rejected: `PaymentResult(false, "Refund amount must be positive.")`.
- A refund `amount` greater than the order total (`IOrderService.CalculateTotal`) is rejected: `PaymentResult(false, "Refund exceeds order total.")`.
- A valid refund (`0 < amount <= total`) returns `PaymentResult(true, "Refunded.")`.
- All three rules are covered by unit tests tagged `[Trait("Category", "Unit")]`, including boundary cases (`amount == total` is allowed; `amount` one cent over `total` is rejected).

### Task 2: Refund endpoint

**Files:**
- Modify: `src/OrdersApi/Controllers/OrdersController.cs`
- Test: `tests/OrdersApi.Tests/OrdersApiIntegrationTests.cs`

Add `POST /orders/{id}/refund` accepting a JSON body `{ "amount": <decimal> }`.

**Acceptance criteria:**
- Unknown order id returns 404.
- A rejected refund (per Task 1 rules) returns HTTP 422 with the rejection message.
- A successful refund returns HTTP 200.
- Covered by integration tests tagged `[Trait("Category", "Integration")]`.
````

- [ ] **Step 2: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/OrdersApi/plans/2026-05-31-add-refunds-plan.md
git commit -m "feat(sample): add demo refund feature plan for the harness to implement"
```

---

## Task 8: Sample README and root README link

**Files:**
- Create: `sample/README.md`
- Modify: `README.md` (root)

- [ ] **Step 1: Write `sample/README.md`**

Create `sample/README.md` with these required sections (complete content, no placeholders):

1. **Purpose** — This is the validation fixture for the `backend-harness` plugin: a small brownfield .NET 10 Orders API used to demonstrate the harness end-to-end against real tooling (xUnit + Stryker.NET).
2. **The two seeded conditions** — explain both precisely:
   - *Functional fix-loop seed:* `OrderService.CalculateTotal` adds the discount instead of subtracting it; the unit test `OrderServiceTests.Total_AppliesDiscount` is committed RED. The harness's Backend Evaluator catches this on the full unit run and dispatches the Fix Agent for the `OrderService` component.
   - *Mutation-gate seed:* `PaymentService` ships with happy-path-only tests, so Stryker's surviving mutants put the kill-rate below the `services` tier threshold (70%). When the demo feature modifies `PaymentService.cs`, the mutation gate evaluates the changed file and trips, driving a fix iteration that adds edge-case tests.
3. **Prerequisites** — `~/.dotnet/dotnet` (SDK 10), `~/.dotnet/dotnet tool install -g dotnet-stryker`, the `backend-harness` plugin installed, and superpowers installed.
4. **Verifying the seeds (deterministic, no harness)** — exact commands:
   - `~/.dotnet/dotnet test --filter Category=Unit` → 3 passed, 1 failed (`Total_AppliesDiscount`).
   - `~/.dotnet/dotnet test --filter Category=Integration` → all pass.
   - `~/.dotnet/dotnet stryker` (run inside `sample/OrdersApi`) → confirm `PaymentService.cs` kill-rate is below 70% in the report.
   - `./scripts/api-smoke.sh` → `api-smoke PASS`.
5. **Running the end-to-end demonstration** — step by step:
   - Open a Claude Code session with the working directory set to `sample/OrdersApi`.
   - Run `/harness-implement` (the demo plan at `plans/2026-05-31-add-refunds-plan.md` is already present).
   - Watch the harness: generate a Context Brief (brownfield), implement the refund feature via the inner loop, run the full evaluation.
6. **Expected convergence trace** — what a human should observe, in order:
   1. Context Brief generated (`plans/context-brief.md`).
   2. Inner loop implements `Refund` + endpoint and commits.
   3. First full evaluation **fails** — `OrderServiceTests.Total_AppliesDiscount` is RED → `OrderService` flagged as a failing component.
   4. Fix Agent fixes the discount bug (`subtotal - discount`); `iterations[OrderService]` becomes 1.
   5. Component-scoped re-eval of `OrderService` **passes**; per the force-full rule, the next evaluation is full.
   6. Full regression eval **passes** — all functional tests green.
   7. Mutation gate runs on the changed `PaymentService.cs`; kill-rate is below 70% → **gate trips**; `iterations[PaymentService]` becomes 1.
   8. Fix Agent adds edge-case tests for the untested branches; mutation gate re-runs and **passes** (≥ 70%).
   9. `plans/harness-state.json` reaches `"phase": "done"`; `superpowers:finishing-a-development-branch` runs.
7. **Success criteria** — the run is a success when: both gates demonstrably fired (one functional fix on `OrderService`, one mutation-driven fix on `PaymentService`), and the final state is `phase=done` with no escalation. Note that exact iteration counts depend on live subagent behavior; the *gates firing and convergence to done* is the acceptance bar, not a byte-exact state match.
8. **Note on determinism** — this is a live, human-observed run; subagent fix quality varies. If the harness escalates (e.g., oscillation or cap), that is also a valid observation of the harness's safety behavior — review `plans/harness-state.json`.

- [ ] **Step 2: Add a sample link to the root README**

In `README.md` (root), add a new section after the "How it works" section:

```markdown
## Try it on the sample app

A ready-to-run brownfield .NET sample lives in [`sample/OrdersApi`](sample/OrdersApi). It is seeded with a real bug (caught by a failing xUnit test) and a thinly-tested service (low Stryker kill-rate) so you can watch the harness's fix loop and mutation gate fire end-to-end. See [`sample/README.md`](sample/README.md) for the walkthrough and expected convergence trace.
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add sample/README.md README.md
git commit -m "docs(sample): document seeded conditions and e2e demonstration"
```

---

## Task 9: Deterministic seed verification (and optional live e2e)

This task proves the seeds are **real** without depending on any live harness run. It is the deterministic backstop for "works consistently." The live harness run is an optional, human-observed follow-up (the sample README documents it).

**Files:**
- (No new files — verification only. Commit only if corrections are needed.)

- [ ] **Step 1: Install Stryker.NET (if not already installed)**

Run:
```bash
~/.dotnet/dotnet tool install -g dotnet-stryker || ~/.dotnet/dotnet tool update -g dotnet-stryker
```
Expected: tool installed or already up to date. Ensure `~/.dotnet/tools` is on `PATH` for the `dotnet stryker` invocation, or invoke via `~/.dotnet/dotnet stryker`.

- [ ] **Step 2: Confirm the functional seed (one RED unit test)**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet test --filter "Category=Unit"
```
Expected: `Failed! - Failed: 1, Passed: 3` and the failing test is `OrderServiceTests.Total_AppliesDiscount`.

- [ ] **Step 3: Confirm integration tests pass**

Run from `sample/OrdersApi`:
```bash
~/.dotnet/dotnet test --filter "Category=Integration"
```
Expected: all integration tests pass.

- [ ] **Step 4: Confirm the mutation-gate seed (PaymentService below 70%)**

First, temporarily fix the discount bug locally so Stryker can run a green build (Stryker requires a passing test baseline). Use git stash discipline so the seeded bug is restored afterward:

```bash
cd "sample/OrdersApi"
# Apply a temporary local fix to get a green baseline for Stryker.
sed -i.bak 's/return subtotal + discount;/return subtotal - discount;/' src/OrdersApi/Services/OrderService.cs
~/.dotnet/dotnet test --filter "Category=Unit"   # expect all green now
~/.dotnet/dotnet stryker
# Inspect the report: confirm PaymentService.cs mutation score < 70%.
# Then RESTORE the seeded bug:
mv src/OrdersApi/Services/OrderService.cs.bak src/OrdersApi/Services/OrderService.cs
~/.dotnet/dotnet test --filter "Category=Unit"   # expect 1 failed again (seed restored)
```
Expected: Stryker completes; the JSON/HTML report shows `PaymentService.cs` with a mutation score **below 70%** (surviving mutants on the two untested guard branches). After restore, the unit suite is RED again on `Total_AppliesDiscount`.

> Rationale: Stryker needs a green baseline to establish which mutants are killed. The seeded functional bug would otherwise make the baseline red. This step proves the *mutation* seed in isolation, then restores the *functional* seed for the harness run.

- [ ] **Step 5: Confirm the API smoke check passes**

Run from `sample/OrdersApi`:
```bash
./scripts/api-smoke.sh
```
Expected: `api-smoke PASS: GET /orders/1/total -> 200, body=50`.

- [ ] **Step 6: Record results / commit any corrections**

If any step surfaced a fixable issue (e.g., wrong package version, csproj path), fix it and commit:
```bash
cd "/Users/yovan/Agent Zone/backend-harness"
git add -A && git commit -m "fix(sample): seed verification corrections" || echo "nothing to commit"
```

- [ ] **Step 7: (Optional, human-driven) Run the live end-to-end harness demonstration**

Following `sample/README.md` Section 5–6, open a Claude Code session in `sample/OrdersApi`, run `/harness-implement`, and observe the convergence trace. This is not an automated assertion — it is the manual proof that both gates fire against the live harness. Record the final `plans/harness-state.json` phase in your notes.

---

## Self-Review

**Spec coverage (against the design spec's testing strategy, item 3 "Full e2e on sample .NET app"):**
- Real .NET API with xUnit + Stryker.NET → Tasks 1–6. ✓
- Seeded failing unit test the fix loop must resolve → Task 3 (`OrderServiceTests.Total_AppliesDiscount` RED). ✓
- Weakly-tested service that trips the mutation gate → Task 4 (`PaymentService` thin tests). ✓
- `harness.config.json` with .NET commands + tiered thresholds → Task 6. ✓
- curl/HTTP semantic verification (`apiVerify`) → Task 6 (`api-smoke.sh`). ✓
- Brownfield → exercises conditional Context Brief → Tasks 1–5 ship pre-existing code; demo plan adds a feature (Task 7). ✓
- Run `/harness-implement` end-to-end; confirm fix loop converges, mutation gate fires then passes, `phase=done`, branch finished → Tasks 8 (documented trace) + 9 Step 7 (live run). ✓
- Deterministic proof the seeds are real (independent of live run) → Task 9 Steps 2–5. ✓

**Placeholder scan:** Every C# file, JSON config, and shell script is given in full. The demo plan (Task 7) and READMEs (Task 8) specify complete required content. No "TBD/TODO/handle edge cases." ✓

**Type consistency:** `IOrderService.CalculateTotal(Order)`, `IPaymentService.Charge(Order, decimal)`, `PaymentResult(bool Success, string Message)`, and `Order`/`OrderItem` property names (`Items`, `UnitPrice`, `Quantity`, `DiscountPercent`) are identical across Tasks 2–5, the integration test, and the demo plan (which adds `Refund(Order, decimal)` consistently). Trait categories (`Unit`, `Integration`) match the `harness.config.json` filters in Task 6. The `services` tier glob (`**/*Service.cs`) matches `OrderService.cs`/`PaymentService.cs`; the `controllers` glob matches `OrdersController.cs`. ✓

**Determinism caveat (explicit):** Tasks 1–9 Steps 1–6 are deterministic and verifiable. Task 9 Step 7 (live harness run) is explicitly marked human-observed and non-deterministic, consistent with the agreed "seeded real run" approach.
