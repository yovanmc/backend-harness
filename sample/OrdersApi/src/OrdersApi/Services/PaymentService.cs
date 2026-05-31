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
