namespace OrdersApi.Models;

public class Order
{
    public int Id { get; set; }
    public List<OrderItem> Items { get; set; } = new();

    /// <summary>Whole-number percentage, e.g. 10 means a 10% discount.</summary>
    public decimal DiscountPercent { get; set; }
}
