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
