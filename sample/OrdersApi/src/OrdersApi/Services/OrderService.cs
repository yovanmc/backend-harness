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
