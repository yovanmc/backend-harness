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
