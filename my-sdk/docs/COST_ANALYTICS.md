# LLM Cost Observability SDK

A signal-plus-pull model SDK for per-request cost analytics across LLM providers (Anthropic, OpenAI, and extensible to others). Client credentials never leave client infrastructure.

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage: Anthropic

```python
from anthropic import Anthropic
from pricing import wrap_anthropic_client, get_cost_aggregator

# Create client
client = Anthropic()

# Wrap to intercept costs
client = wrap_anthropic_client(client)

# Use normally - costs tracked automatically
response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello!"}],
)

# Get metrics
aggregator = get_cost_aggregator()
metrics = aggregator.get_aggregated_metrics()
print(f"Total cost: ${metrics.total_cost:.6f}")
```

### Basic Usage: OpenAI

```python
from openai import OpenAI
from pricing import wrap_openai_client, get_cost_aggregator

client = OpenAI()
client = wrap_openai_client(client)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}],
)

metrics = get_cost_aggregator().get_aggregated_metrics()
print(f"Total cost: ${metrics.total_cost:.6f}")
```

## Architecture

### Signal-Plus-Pull Model

- **Signal**: Client credentials stay on client, SDK intercepts API responses
- **Pull**: Pricing synced from upstream (LiteLLM) daily with fallback to bundled file
- **Zero external dependencies**: No cloud infrastructure required for basic tracking

### Core Components

#### 1. Pricing Manager (`pricing/manager.py`)
- Syncs pricing from [LiteLLM's upstream JSON](https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json)
- Daily hash-diff detection: only updates on changes
- Silent fallback to bundled `pricing.json` on network failure
- Tracks sync state and failures

#### 2. Cost Extractors (`pricing/extractors.py`)
Per-provider usage extraction:

**Anthropic** (`/v1/messages`):
- Fields: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- Cost formula: `(input_tokens * input_rate + output_tokens * output_rate) / 1_000_000`
- Cache pricing: creation ~25% premium on input_rate, read ~10% of input_rate

**OpenAI**:
- Fields: `prompt_tokens`, `completion_tokens`, `cached_prompt_tokens`
- Same cost formula with field name mapping

#### 3. Cost Aggregator (`pricing/aggregator.py`)
- Records per-request: cost, tokens (input/output/cache), model, provider, metadata
- Aggregates: total cost, requests, by model, by provider, time windows
- Exports to JSON for integration with billing systems

#### 4. Cost Interceptor (`pricing/interceptor.py`)
- Wraps client library calls (non-invasive, no request/response modification)
- Routes to appropriate provider extractor
- Records to aggregator
- Includes provider-specific interceptors for Anthropic/OpenAI

## Pricing Format

### Bundled Pricing (`src/pricing/pricing.json`)
```json
{
  "claude-3-opus-20240229": {
    "input_cost_per_1m_tokens": 15.0,
    "output_cost_per_1m_tokens": 75.0,
    "cache_creation_cost_per_1m_tokens": 18.75,
    "cache_read_cost_per_1m_tokens": 1.5
  }
}
```

### Upstream Sync
- Syncs daily (configurable via `PRICING_SYNC_INTERVAL_HOURS`)
- Compares hash before updating
- Logs silently on failure, continues with fallback
- State tracked in `pricing_sync.json`

## Usage Examples

### Get Aggregated Metrics
```python
from pricing import get_cost_aggregator

aggregator = get_cost_aggregator()
metrics = aggregator.get_aggregated_metrics()

print(f"Total cost: ${metrics.total_cost:.6f}")
print(f"Total requests: {metrics.total_requests}")
print(f"By model: {metrics.by_model}")
print(f"By provider: {metrics.by_provider}")
```

### Time-Window Metrics
```python
# Get costs from last hour
metrics_1h = aggregator.get_metrics_in_window(minutes=60)
print(f"Last hour: ${metrics_1h.total_cost:.6f}")
```

### Export Costs
```python
# Export all tracked requests
aggregator.export_requests("costs.json")
```

### Manual Cost Computation
```python
from pricing import AnthropicExtractor, get_pricing_manager

response = {
    "model": "claude-3-opus-20240229",
    "usage": {
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
}

extractor = AnthropicExtractor()
usage = extractor.extract_usage(response)

pricing_mgr = get_pricing_manager()
pricing = pricing_mgr.get_pricing("claude-3-opus-20240229")

cost = extractor.compute_cost(usage, pricing)
print(f"Cost: ${cost.total_cost:.6f}")
```

## Adding New LLM Providers

1. Create extractor in `pricing/extractors.py`:
```python
class MyProviderExtractor(CostExtractor):
    def extract_usage(self, response):
        # Map provider fields to standard format
        return {
            "input_tokens": ...,
            "output_tokens": ...,
            "cache_read_tokens": ...,
            "cache_creation_tokens": ...,
        }
    
    def extract_model(self, response):
        return response["model"]
    
    def compute_cost(self, usage, pricing):
        # Compute cost with provider-specific logic
        ...
```

2. Register in `EXTRACTORS` dict:
```python
EXTRACTORS = {
    "anthropic": AnthropicExtractor,
    "openai": OpenAIExtractor,
    "my-provider": MyProviderExtractor,  # Add here
}
```

3. Add pricing to bundled file or update LiteLLM upstream

4. Create interceptor (optional):
```python
class MyProviderInterceptor(CostInterceptor):
    def wrap_client(self, client):
        original_call = client.complete
        
        def wrapped(*args, **kwargs):
            response = original_call(*args, **kwargs)
            self.process_response(response, provider='my-provider')
            return response
        
        client.complete = wrapped
        return client
```

## Configuration

### Environment Variables
```bash
# Pricing sync interval (hours)
PRICING_SYNC_INTERVAL_HOURS=24

# Upstream pricing URL (override default)
LITELLM_PRICING_URL=https://...

# Disable pricing sync
DISABLE_PRICING_SYNC=false
```

### Pricing Manager
```python
from pricing import get_pricing_manager

manager = get_pricing_manager()

# Manual sync
manager.sync_from_upstream()

# Get pricing
pricing = manager.get_pricing("claude-3-opus-20240229")
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# With coverage
pytest --cov=src tests/

# Specific test file
pytest tests/unit/pricing/test_extractors.py -v
```

## Phase 2: Cloud Infrastructure Billing

Future support for:
- **AWS**: CUR (Cost & Usage Report) + Athena querying
- **GCP**: BigQuery export integration
- **Azure**: Cost Management API

Same signal-plus-pull architecture: client pulls from cloud provider APIs, costs computed locally.

## API Reference

### CostInterceptor
```python
class CostInterceptor:
    def __init__(self, auto_sync_pricing: bool = True)
    def process_response(self, response, provider, request_id=None, metadata=None) -> CostBreakdown
    def get_aggregated_metrics() -> AggregatedMetrics
    def get_metrics_in_window(minutes: int) -> AggregatedMetrics
    def export_costs(filepath: str) -> None
```

### CostBreakdown
```python
@dataclass
class CostBreakdown:
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    input_cost: float
    output_cost: float
    cache_creation_cost: float
    cache_read_cost: float
    total_cost: float
    model: str
    provider: str
    stop_reason: Optional[str]
    raw_usage: Dict[str, Any]
```

### AggregatedMetrics
```python
@dataclass
class AggregatedMetrics:
    total_cost: float
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    by_model: Dict[str, float]
    by_provider: Dict[str, float]
    cost_breakdown: Dict[str, float]
```

## License

MIT
