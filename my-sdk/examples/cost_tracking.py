"""
Example: Basic cost tracking with Anthropic.
Demonstrates minimal setup to track LLM costs per request.
"""

from anthropic import Anthropic
from pricing import (
    wrap_anthropic_client,
    get_cost_aggregator,
    get_pricing_manager,
)


def example_basic_anthropic():
    """Basic Anthropic cost tracking."""
    
    # Initialize client
    client = Anthropic()
    
    # Wrap client to intercept costs
    client = wrap_anthropic_client(client)
    
    # Make API call - cost is automatically tracked
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=100,
        messages=[
            {"role": "user", "content": "Hello, Claude! What's your name?"}
        ],
    )
    
    print(f"Response: {response.content[0].text}")
    
    # Get aggregated metrics
    aggregator = get_cost_aggregator()
    metrics = aggregator.get_aggregated_metrics()
    
    print(f"\nCost Metrics:")
    print(f"  Total Cost: ${metrics.total_cost:.6f}")
    print(f"  Total Requests: {metrics.total_requests}")
    print(f"  Input Tokens: {metrics.total_input_tokens}")
    print(f"  Output Tokens: {metrics.total_output_tokens}")
    print(f"  By Model: {metrics.by_model}")


def example_pricing_sync():
    """Demonstrate pricing sync from upstream."""
    
    pricing_mgr = get_pricing_manager()
    
    print("Syncing pricing from LiteLLM upstream...")
    success = pricing_mgr.sync_from_upstream()
    
    if success:
        print("✓ Pricing sync successful")
    else:
        print("✗ Sync failed, using fallback pricing")
    
    # Get pricing for a model
    pricing = pricing_mgr.get_pricing("claude-3-sonnet-20240229")
    if pricing:
        print(f"\nPricing for claude-3-sonnet:")
        print(f"  Input: ${pricing.get('input_cost_per_1m_tokens')}/1M tokens")
        print(f"  Output: ${pricing.get('output_cost_per_1m_tokens')}/1M tokens")


def example_manual_cost_computation():
    """Manually compute cost for a response."""
    
    from pricing import AnthropicExtractor, get_pricing_manager
    
    # Mock Anthropic response
    response = {
        "id": "msg_1234",
        "model": "claude-3-opus-20240229",
        "usage": {
            "input_tokens": 150,
            "output_tokens": 50,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "stop_reason": "end_turn",
    }
    
    # Extract usage
    extractor = AnthropicExtractor()
    usage = extractor.extract_usage(response)
    
    # Get pricing
    pricing_mgr = get_pricing_manager()
    pricing = pricing_mgr.get_pricing("claude-3-opus-20240229")
    
    # Compute cost
    if usage and pricing:
        cost_breakdown = extractor.compute_cost(usage, pricing)
        
        print("Cost Breakdown:")
        print(f"  Input: ${cost_breakdown.input_cost:.6f} ({usage['input_tokens']} tokens)")
        print(f"  Output: ${cost_breakdown.output_cost:.6f} ({usage['output_tokens']} tokens)")
        print(f"  Total: ${cost_breakdown.total_cost:.6f}")


def example_export_costs():
    """Export recorded costs to JSON."""
    
    # After making some requests...
    aggregator = get_cost_aggregator()
    
    # Export all requests
    aggregator.export_requests("costs.json")
    print("Exported costs to costs.json")
    
    # Get metrics for last hour
    metrics_1h = aggregator.get_metrics_in_window(minutes=60)
    print(f"Costs in last hour: ${metrics_1h.total_cost:.6f}")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Cost Observability Examples")
    print("=" * 60)
    
    print("\n1. Pricing Sync from Upstream")
    print("-" * 60)
    example_pricing_sync()
    
    print("\n2. Manual Cost Computation")
    print("-" * 60)
    example_manual_cost_computation()
    
    # Uncomment to run with real Anthropic API (requires ANTHROPIC_API_KEY):
    # print("\n3. Basic Anthropic Cost Tracking")
    # print("-" * 60)
    # example_basic_anthropic()
