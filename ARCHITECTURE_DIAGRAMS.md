# System Architecture & Data Flow Diagrams

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER APPLICATION                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Python Code (LangChain, Direct API calls, etc.)             │  │
│  │                                                               │  │
│  │  client = Anthropic()                                        │  │
│  │  client = wrap_anthropic_client(client)  ◄─── SDK wraps     │  │
│  │                                                               │  │
│  │  response = client.messages.create(...)                      │  │
│  │  # Cost tracked automatically! ◄─── Signal from response    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         ║
         ║ API Call (no credentials exposed to SDK)
         ║
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│             LLM PROVIDER (Anthropic/OpenAI)                         │
│                                                                      │
│  API Response:                                                      │
│  {                                                                   │
│    "model": "claude-3-opus-20240229",                               │
│    "usage": {                                                       │
│      "input_tokens": 100,                                           │
│      "output_tokens": 50,                                           │
│      "cache_creation_input_tokens": 0,                              │
│      "cache_read_input_tokens": 0                                   │
│    }                                                                 │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
         ║
         ║ Intercepted by CostInterceptor
         ║
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              COST EXTRACTION (SIGNAL)                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ ProviderExtractor (Anthropic/OpenAI specific)              │   │
│  │  • Extract model                                            │   │
│  │  • Extract usage fields                                     │   │
│  │  • Map to standard format                                   │   │
│  │                                                              │   │
│  │  Output: {input: 100, output: 50, cache_read: 0, ...}     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         ║
         ║
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PRICING LOOKUP (PULL)                                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ PricingManager                                              │   │
│  │  • Check memory cache                                       │   │
│  │  • If missing: sync from LiteLLM (daily)                   │   │
│  │  • If sync fails: use bundled pricing                       │   │
│  │                                                              │   │
│  │  Output:                                                    │   │
│  │  {                                                          │   │
│  │    "input_cost_per_1m_tokens": 15.0,                       │   │
│  │    "output_cost_per_1m_tokens": 75.0,                      │   │
│  │    "cache_creation_cost_per_1m_tokens": 18.75,             │   │
│  │    "cache_read_cost_per_1m_tokens": 1.5                    │   │
│  │  }                                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         ║
         ║
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              COST COMPUTATION                                        │
│                                                                      │
│  CostBreakdown = extractor.compute_cost(usage, pricing)            │
│                                                                      │
│  input_cost = (100 * 15.0) / 1_000_000 = 0.0015                   │
│  output_cost = (50 * 75.0) / 1_000_000 = 0.00375                  │
│  total_cost = 0.00525                                              │
│                                                                      │
│  Result:                                                            │
│  {                                                                   │
│    "input_tokens": 100,                                             │
│    "output_tokens": 50,                                             │
│    "total_cost": 0.00525,                                           │
│    "model": "claude-3-opus-20240229",                               │
│    "provider": "anthropic"                                          │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
         ║
         ║
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              COST AGGREGATION & STORAGE                             │
│                                                                      │
│  CostAggregator.record_request()                                   │
│                                                                      │
│  In-Memory Requests List:                                          │
│  [                                                                   │
│    RequestCost(                                                      │
│      timestamp=2024-01-15T10:30:45,                                 │
│      request_id="req_abc123",                                       │
│      model="claude-3-opus-20240229",                                │
│      provider="anthropic",                                          │
│      total_cost=0.00525,                                            │
│      input_tokens=100,                                              │
│      output_tokens=50,                                              │
│      ...                                                             │
│    ),                                                               │
│    ...                                                              │
│  ]                                                                   │
│                                                                      │
│  Aggregated Metrics:                                                │
│  {                                                                   │
│    "total_cost": 0.12345,                                           │
│    "total_requests": 42,                                            │
│    "by_model": {"claude-3-opus...": 0.08, "gpt-4": 0.04},         │
│    "by_provider": {"anthropic": 0.08, "openai": 0.04}             │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
         ║
         ║
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              METRICS API (Local Query)                              │
│                                                                      │
│  metrics = aggregator.get_aggregated_metrics()                     │
│  metrics_1h = aggregator.get_metrics_in_window(minutes=60)         │
│  aggregator.export_requests("costs.json")                          │
│                                                                      │
│  ✓ All data available locally                                       │
│  ✓ No external calls needed                                         │
│  ✓ Instant queries                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Pricing Sync Flow

```
Daily (or on demand):

  PricingManager.sync_from_upstream()
           ║
           ║
           ▼
  Fetch: https://raw.githubusercontent.com/.../model_prices_and_context_window.json
           ║
           ├─── Success ───────────────────┐
           │                               │
           │                               ▼
           │                    Compute hash of response
           │                               ║
           │                    Compare with last_hash
           │                               ║
           │           ┌───────────────────┴────────────────┐
           │           │                                    │
           │     Changed (new hash)                  Unchanged
           │           │                                    │
           │           ▼                                    ▼
           │    Update pricing_data         Log "no changes"
           │    Save to cache              Continue with current data
           │    Update sync_state                     │
           │    Log success                          │
           │           │                             │
           │           └────────────┬────────────────┘
           │                        │
           │                        ▼
           │                  Return True
           │
           ├─── Network Error ─────────────────┐
           │    (timeout, DNS fail, etc)       │
           │                                   ▼
           │                    Use cached pricing (if available)
           │                    Use bundled pricing (fallback)
           │                    Increment sync_failures counter
           │                    Log warning (silent)
           │                    Save sync_state
           │                    Return False
           │                   │
           └───────────────────┴──────────────────────────────┐
                                                               │
                                                               ▼
                                                    Continue with metrics
                                                    All tracking still works!
```

## Request Flow Diagram

```
Step 1: Wrap Client
┌──────────────────────┐
│ client = Anthropic() │
└──────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ wrap_anthropic_client(client)    │
│                                  │
│ Saves original method:           │
│ original_create = client.messages.create
│                                  │
│ Replaces with wrapper:           │
│ client.messages.create = wrapped │
└──────────────────────────────────┘

Step 2: API Call
┌──────────────────────────────────┐
│ response = client.messages.create │
│     model="claude-3-...",        │
│     messages=[...]               │
└──────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Wrapper intercepts:              │
│                                  │
│ 1. Call original_create()        │
│ 2. Get response from API         │
│ 3. Extract cost from response    │
│ 4. Record to aggregator          │
│ 5. Return response unchanged     │
└──────────────────────────────────┘

Step 3: Cost Extraction
┌──────────────────────────────────┐
│ AnthropicExtractor.extract_usage │
│ (response)                       │
│                                  │
│ return {                         │
│   "input_tokens": 100,           │
│   "output_tokens": 50,           │
│   "cache_read_tokens": 0,        │
│   "cache_creation_tokens": 0     │
│ }                                │
└──────────────────────────────────┘

Step 4: Pricing Lookup
┌──────────────────────────────────┐
│ PricingManager.get_pricing       │
│ ("claude-3-opus-20240229")       │
│                                  │
│ return {                         │
│   "input_cost_per_1m_tokens": 15 │
│   "output_cost_per_1m_tokens": 75│
│ }                                │
└──────────────────────────────────┘

Step 5: Cost Computation
┌──────────────────────────────────┐
│ compute_cost(usage, pricing)     │
│                                  │
│ input_cost = 100 * 15 / 1M       │
│ output_cost = 50 * 75 / 1M       │
│ total_cost = 0.00525             │
│                                  │
│ return CostBreakdown(...)        │
└──────────────────────────────────┘

Step 6: Record & Aggregate
┌──────────────────────────────────┐
│ CostAggregator.record_request()  │
│                                  │
│ • Append to requests list        │
│ • Update metrics cache           │
│ • Log cost info                  │
└──────────────────────────────────┘

Step 7: User Gets Metrics
┌──────────────────────────────────┐
│ aggregator.get_aggregated_metrics│
│                                  │
│ return AggregatedMetrics(        │
│   total_cost=0.12345,            │
│   total_requests=42,             │
│   by_model={...},                │
│   by_provider={...}              │
│ )                                │
└──────────────────────────────────┘
```

## Module Dependencies

```
┌─────────────────────────────────────┐
│  src/sdk.py                         │
│  (CostAnalyticsSDK - entry point)   │
└─────────────────────────────────────┘
           │
    ┌──────┼──────┐
    │      │      │
    ▼      ▼      ▼
  manager interceptor aggregator
    │      │      │
    │      ├──────┼────┬────────────────┐
    │      │      │    │                │
    ▼      ▼      ▼    ▼                ▼
┌──────────────────────────────────────────────┐
│  src/pricing/manager.py                      │
│  - Pricing sync                              │
│  - Local cache                               │
│  - Fallback to bundled                       │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  src/pricing/extractors.py                   │
│  - AnthropicExtractor                        │
│  - OpenAIExtractor                           │
│  - CostBreakdown model                       │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  src/pricing/aggregator.py                   │
│  - CostAggregator                            │
│  - RequestCost model                         │
│  - AggregatedMetrics model                   │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  src/pricing/interceptor.py                  │
│  - CostInterceptor (base)                    │
│  - AnthropicInterceptor                      │
│  - OpenAIInterceptor                         │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  src/pricing/__init__.py                     │
│  - Exports all public classes                │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  src/pricing/pricing.json                    │
│  - Bundled pricing data                      │
│  - Model name → cost rates                   │
└──────────────────────────────────────────────┘
```

## Data Flow by Scenario

### Scenario 1: Anthropic Request with Cache

```
API Response:
{
  "id": "msg_123",
  "model": "claude-3-opus-20240229",
  "usage": {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 25,
    "cache_read_input_tokens": 0
  }
}
    │
    ▼
Extract Usage:
{
  "input_tokens": 100,
  "output_tokens": 50,
  "cache_creation_tokens": 25,
  "cache_read_tokens": 0
}
    │
    ▼
Get Pricing:
{
  "input_cost_per_1m_tokens": 15.0,
  "output_cost_per_1m_tokens": 75.0,
  "cache_creation_cost_per_1m_tokens": 18.75,
  "cache_read_cost_per_1m_tokens": 1.5
}
    │
    ▼
Compute Cost:
input_cost = (100 * 15.0) / 1M = 0.0015
output_cost = (50 * 75.0) / 1M = 0.00375
cache_creation_cost = (25 * 18.75) / 1M = 0.00046875
total_cost = 0.00571875
    │
    ▼
Record:
RequestCost(
  timestamp=now,
  request_id="req_xyz",
  model="claude-3-opus-20240229",
  provider="anthropic",
  total_cost=0.00571875,
  input_tokens=100,
  output_tokens=50,
  cache_creation_tokens=25,
  cache_read_tokens=0
)
```

### Scenario 2: OpenAI Request with Cached Tokens

```
API Response:
{
  "id": "chatcmpl_123",
  "model": "gpt-4-turbo",
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "cached_prompt_tokens": 20
  }
}
    │
    ▼
Extract Usage:
{
  "input_tokens": 100,              ← from prompt_tokens
  "output_tokens": 50,              ← from completion_tokens
  "cache_read_tokens": 20,          ← from cached_prompt_tokens
  "cache_creation_tokens": 0        ← OpenAI doesn't report this
}
    │
    ▼
Get Pricing:
{
  "input_cost_per_1m_tokens": 10.0,
  "output_cost_per_1m_tokens": 30.0,
  "cache_read_cost_per_1m_tokens": 5.0  ← 50% discount
}
    │
    ▼
Compute Cost:
input_cost = (100 * 10.0) / 1M = 0.001
output_cost = (50 * 30.0) / 1M = 0.0015
cache_read_cost = (20 * 5.0) / 1M = 0.0001
total_cost = 0.0026
    │
    ▼
Record:
RequestCost(
  timestamp=now,
  request_id="req_abc",
  model="gpt-4-turbo",
  provider="openai",
  total_cost=0.0026,
  input_tokens=100,
  output_tokens=50,
  cache_read_tokens=20,
  cache_creation_tokens=0
)
```

## Aggregation Flow

```
Multiple Requests Recorded:

req1: model=claude-3-opus, cost=0.005
req2: model=claude-3-sonnet, cost=0.002
req3: model=gpt-4, cost=0.010
req4: model=claude-3-opus, cost=0.004
    │
    │
    ▼
Compute Aggregated Metrics:

total_cost = 0.005 + 0.002 + 0.010 + 0.004 = 0.021
total_requests = 4
total_input_tokens = (sum of all input_tokens)
total_output_tokens = (sum of all output_tokens)

by_model:
  "claude-3-opus": 0.005 + 0.004 = 0.009
  "claude-3-sonnet": 0.002
  "gpt-4": 0.010

by_provider:
  "anthropic": 0.005 + 0.002 + 0.004 = 0.011
  "openai": 0.010

cost_breakdown:
  "input": 0.008
  "output": 0.012
  "cache_read": 0.001
    │
    ▼
Return AggregatedMetrics {
  total_cost: 0.021,
  total_requests: 4,
  by_model: {...},
  by_provider: {...},
  cost_breakdown: {...}
}
```

## Error Recovery Paths

```
Error: Pricing sync fails

    sync_from_upstream()
         │
         ├─ Fetch fails
         │      │
         │      ▼
         │   Check cache exists?
         │      │
         │      ├─ Yes → Use cache
         │      │          Return True (silent)
         │      │
         │      └─ No → Check bundled file
         │                │
         │                ├─ Exists → Use bundled
         │                │           Return False (warn)
         │                │
         │                └─ Missing → Empty pricing
         │                            Return False (error)
         │
         └─ All processing continues with current pricing
            Costs still tracked!
            Metrics still available!


Error: Extraction fails

    extractor.extract_usage(response)
         │
         ├─ No usage field
         │      │
         │      ▼
         │    Log warning
         │    Return None
         │
         └─ Cost not recorded
              Tracking continues for next request
              Metrics still available
```

---

These diagrams illustrate:
1. **Non-invasive interception**: Response unmodified, cost extracted separately
2. **Three-tier pricing**: Upstream → cache → bundled → error handling
3. **Per-request accuracy**: Each request tracked individually
4. **Aggregation pipeline**: Requests flow into metrics computation
5. **Graceful degradation**: Failures don't break application or tracking
