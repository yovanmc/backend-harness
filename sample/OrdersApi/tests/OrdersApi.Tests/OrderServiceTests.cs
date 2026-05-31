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
