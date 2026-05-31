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
