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
