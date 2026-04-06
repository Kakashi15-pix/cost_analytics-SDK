# my-sdk

A production-ready Python SDK template with sync/async support, pluggable auth, retry logic, and FastAPI middleware.

---

## Installation

```bash
pip install my-sdk
```

For development:

```bash
git clone https://github.com/your-org/my-sdk.git
cd my-sdk
pip install -e ".[dev]"
```

---

## Quick Start

```python
from src import SDKClient, SDKConfig, credentials

client = SDKClient(SDKConfig(
    base_url="https://api.example.com",
    auth=credentials("your-api-key"),
))

users = client.users.list()
user  = client.users.get("u1")
new   = client.users.create({"name": "Alice", "email": "alice@example.com"})
```

---

## Authentication

Three auth strategies are supported:

```python
from src import credentials, jwt, oauth

# API key (x-api-key header)
auth=credentials("your-api-key")

# JWT bearer token
auth=jwt("eyJ...")

# OAuth access token
auth=oauth("access-token")
```

Pass any of these into `SDKConfig(auth=...)`.

---

## Async Support

Every resource method has an async counterpart prefixed with `a`:

```python
import asyncio
from src import SDKClient, SDKConfig

async def main():
    client = SDKClient(SDKConfig(base_url="https://api.example.com"))

    # Fetch users and products concurrently
    users, products = await asyncio.gather(
        client.users.alist(),
        client.products.alist(),
    )

asyncio.run(main())
```

| Sync | Async |
|------|-------|
| `list()` | `alist()` |
| `get(id)` | `aget(id)` |
| `create(data)` | `acreate(data)` |
| `update(id, data)` | `aupdate(id, data)` |
| `delete(id)` | `adelete(id)` |

---

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `base_url` | `str` | — | **Required.** Base URL of the API |
| `auth` | `SDKAuth` | `None` | Auth strategy |
| `timeout` | `float` | `10.0` | Request timeout in seconds |
| `retries` | `int` | `3` | Number of retry attempts on network failure |
| `logger` | `Logger` | stdlib logger | Custom logger instance |

```python
from src import SDKClient, SDKConfig

client = SDKClient(SDKConfig(
    base_url="https://api.example.com",
    timeout=30.0,
    retries=5,
))
```

---

## Error Handling

```python
from src import SDKClient, SDKConfig, SDKHttpError, SDKConfigError

try:
    user = client.users.get("missing-id")
except SDKHttpError as e:
    print(e.status)   # e.g. 404
    print(e.body)     # parsed response body
except SDKConfigError as e:
    print(f"Bad config: {e}")
```

| Exception | When |
|-----------|------|
| `SDKError` | Base class for all SDK errors |
| `SDKConfigError` | Invalid or missing configuration |
| `SDKHttpError` | Non-2xx HTTP response |

---

## Resources

All four resources share the same interface:

```python
client.users
client.products
client.orders
client.payments
```

Each exposes `list`, `get`, `create`, `update`, `delete` (and async variants).

---

## FastAPI Middleware

Drop-in middleware for FastAPI apps built on top of this SDK:

```python
from fastapi import FastAPI
from src.middleware.auth import APIKeyMiddleware
from src.middleware.rate_limit import RateLimitMiddleware

app = FastAPI()
app.add_middleware(APIKeyMiddleware, api_key="secret")
app.add_middleware(RateLimitMiddleware, max_per_second=20)
```

---

## Plugins

Extend the client with plugins:

```python
from src.plugins.base_plugin import SDKPlugin

class MyPlugin(SDKPlugin):
    @property
    def name(self) -> str:
        return "my-plugin"

    def setup(self, client) -> None:
        # hook into client on startup
        pass
```

---

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Lint
ruff check .

# Type check
mypy src
```

---

## Project Structure

```
src/
├── client.py          # SDKClient entry point
├── config.py          # Config normalisation
├── types.py           # Dataclasses and type aliases
├── errors.py          # Exception hierarchy
├── api/               # Resource modules (users, products, orders, payments)
├── auth/              # Auth strategies (credentials, jwt, oauth)
├── middleware/        # FastAPI middleware (auth, rate_limit, error_handler)
├── plugins/           # Plugin interface and examples
└── utils/             # http, cache, retry, logger, validation, helpers
```

---

## License

MIT
