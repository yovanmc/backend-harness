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
