# Quick Reference Guide

## Installation

```bash
cd my-sdk
pip install -e .
```

## Basic Anthropic Usage

```python
from anthropic import Anthropic
from pricing import wrap_anthropic_client, get_cost_aggregator

# Create and wrap
client = Anthropic()
client = wrap_anthropic_client(client)

# Use normally
response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello!"}]
)

# Get metrics
agg = get_cost_aggregator()
metrics = agg.get_aggregated_metrics()
print(f"Cost: ${metrics.total_cost:.6f}")
```

## Basic OpenAI Usage

```python
from openai import OpenAI
from pricing import wrap_openai_client, get_cost_aggregator

client = OpenAI()
client = wrap_openai_client(client)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)

metrics = get_cost_aggregator().get_aggregated_metrics()
print(f"Cost: ${metrics.total_cost:.6f}")
```

## Get Metrics

```python
from pricing import get_cost_aggregator

agg = get_cost_aggregator()

# All time
metrics = agg.get_aggregated_metrics()

# Last hour
metrics_1h = agg.get_metrics_in_window(minutes=60)

# Last 24 hours
metrics_24h = agg.get_metrics_in_window(minutes=1440)

# Specific model
by_model = metrics.by_model  # {"claude-3-opus...": 0.05, ...}

# Specific provider
by_provider = metrics.by_provider  # {"anthropic": 0.05, ...}

# Total cost
total = metrics.total_cost  # float

# Token counts
input_tokens = metrics.total_input_tokens
output_tokens = metrics.total_output_tokens
cache_tokens = metrics.total_cache_read_tokens
```

## Export & Archive

```python
from pricing import get_cost_aggregator
import json

agg = get_cost_aggregator()

# Export all requests
agg.export_requests("costs.json")

# Clear after export
agg.clear()

# Manual JSON export
requests = agg.get_requests_in_window(minutes=1440)
with open("yesterday.json", "w") as f:
    json.dump([r.to_dict() for r in requests], f, indent=2, default=str)
```

## Manual Cost Processing

```python
from pricing import CostInterceptor

interceptor = CostInterceptor()

# Anthropic response
response = {...}
cost = interceptor.process_response(
    response,
    provider='anthropic',
    request_id='req_123',
    metadata={'user': 'alice'}
)

print(f"Input: {cost.input_tokens} tokens = ${cost.input_cost:.6f}")
print(f"Output: {cost.output_tokens} tokens = ${cost.output_cost:.6f}")
print(f"Total: ${cost.total_cost:.6f}")
```

## Pricing Management

```python
from pricing import get_pricing_manager

mgr = get_pricing_manager()

# Get pricing for model
pricing = mgr.get_pricing("claude-3-opus-20240229")
print(f"Input: ${pricing['input_cost_per_1m_tokens']}/1M tokens")
print(f"Output: ${pricing['output_cost_per_1m_tokens']}/1M tokens")

# Manual sync
success = mgr.sync_from_upstream()
if success:
    print("✓ Pricing synced")
else:
    print("✗ Sync failed, using fallback")

# Check sync state
print(f"Last sync: {mgr.sync_state['last_sync']}")
print(f"Failures: {mgr.sync_state['sync_failures']}")
```

## Unified SDK Client

```python
from src.sdk import CostAnalyticsSDK

sdk = CostAnalyticsSDK(auto_sync_pricing=True)

# Wrap clients
client = sdk.wrap_anthropic_client(Anthropic())

# Use normally
response = client.messages.create(...)

# Get metrics
metrics = sdk.get_metrics()
print(f"Total: ${metrics['total_cost']:.6f}")

# Export
sdk.export_metrics("costs.json")

# Clear
sdk.clear_metrics()
```

## Debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now you'll see:
# - Pricing sync messages
# - Cost extraction details
# - Aggregation info
# - Any errors

# Check specific issues
from pricing import get_pricing_manager, AnthropicExtractor

mgr = get_pricing_manager()
ext = AnthropicExtractor()

# Is pricing loaded?
print(len(mgr.pricing_data))  # Should be > 0

# Can extract model?
response = {...}
model = ext.extract_model(response)
print(f"Model: {model}")

# Can extract usage?
usage = ext.extract_usage(response)
print(f"Usage: {usage}")

# Can compute cost?
pricing = mgr.get_pricing(model)
if pricing:
    cost = ext.compute_cost(usage, pricing)
    print(f"Cost: ${cost.total_cost:.6f}")
```

## Testing

```bash
# All tests
make test

# Unit tests
make test-unit

# Integration tests
make test-integration

# Specific test
pytest tests/unit/pricing/test_extractors.py -v

# With output
pytest -s tests/

# Coverage
pytest --cov=src tests/
```

## Common Issues

### Missing pricing for model
```python
from pricing import get_pricing_manager

mgr = get_pricing_manager()

# Check if model exists
pricing = mgr.get_pricing("my-model")
if not pricing:
    print("Pricing not found")
    print("Available:", list(mgr.pricing_data.keys())[:5])

# Try manual sync
mgr.sync_from_upstream()
```

### Sync failing
```python
from pricing import get_pricing_manager

mgr = get_pricing_manager()

print("Sync state:", mgr.sync_state)
print("Failures:", mgr.sync_state.get("sync_failures", 0))

# Will still work with bundled pricing
pricing = mgr.get_pricing("claude-3-opus-20240229")
```

### Cost seems wrong
```python
# Verify manually
model = "claude-3-opus-20240229"
usage = {"input_tokens": 1000, "output_tokens": 500, ...}

from pricing import AnthropicExtractor, get_pricing_manager

ext = AnthropicExtractor()
mgr = get_pricing_manager()

pricing = mgr.get_pricing(model)
cost = ext.compute_cost(usage, pricing)

print(f"Computed: ${cost.total_cost:.6f}")

# Compare with provider's dashboard
```

## Configuration

```bash
# Future env vars (not yet implemented)
export PRICING_SYNC_INTERVAL_HOURS=24
export DISABLE_PRICING_SYNC=false
```

## File Locations

```
Key files:
  src/pricing/pricing.json          - Bundled pricing
  src/pricing/pricing_cache.json    - Synced pricing cache
  src/pricing/pricing_sync.json     - Sync state

Generated during runtime:
  pricing_cache.json                - Local cache
  pricing_sync.json                 - Sync state
  costs.json                        - Exported costs
```

## Providers Supported

✅ **Anthropic**
- Model detection ✓
- Usage extraction ✓
- Cache tokens ✓
- Client wrapper ✓

✅ **OpenAI**
- Model detection ✓
- Usage extraction ✓
- Cache tokens ✓
- Client wrapper ✓

🔜 **Others**
- AWS Bedrock
- Ollama
- vLLM
- etc. (add via extension pattern)

## Cost Formula Quick Reference

```
Total Cost = (
    input_tokens × input_rate +
    output_tokens × output_rate +
    cache_read_tokens × cache_read_rate +
    cache_creation_tokens × cache_creation_rate
) / 1,000,000

Cache Rates (if not in pricing):
  cache_read_rate = input_rate × 0.1 (90% discount)
  cache_creation_rate = input_rate × 1.25 (25% premium)
```

## Metrics Available

```python
metrics = get_cost_aggregator().get_aggregated_metrics()

# Total
metrics.total_cost                      # float
metrics.total_requests                  # int
metrics.total_input_tokens              # int
metrics.total_output_tokens             # int
metrics.total_cache_read_tokens         # int
metrics.total_cache_creation_tokens     # int

# By dimension
metrics.by_model                        # dict
metrics.by_provider                     # dict
metrics.cost_breakdown                  # dict
```

## Next Steps

1. See `docs/COST_ANALYTICS.md` for detailed usage
2. See `examples/` for runnable examples
3. See `docs/ARCHITECTURE.md` for design details
4. See `IMPLEMENTATION_SUMMARY.md` for overview

---

**Quick command reference**:
```bash
make help              # Show all make targets
make test              # Run tests
make lint              # Run linters
make format            # Format code
make install-dev       # Install dev dependencies
```
