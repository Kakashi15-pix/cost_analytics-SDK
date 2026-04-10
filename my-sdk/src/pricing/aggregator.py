"""
Cost aggregation and analytics engine.
Tracks per-request costs and provides aggregated metrics.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestCost:
    """Single API request cost record."""
    timestamp: datetime
    request_id: str
    model: str
    provider: str
    total_cost: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    stop_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "model": self.model,
            "provider": self.provider,
            "total_cost": self.total_cost,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "stop_reason": self.stop_reason,
            "metadata": self.metadata,
        }


@dataclass
class AggregatedMetrics:
    """Aggregated cost metrics."""
    total_cost: float = 0.0
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    by_model: Dict[str, float] = field(default_factory=dict)
    by_provider: Dict[str, float] = field(default_factory=dict)
    cost_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_cost": self.total_cost,
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cache_read_tokens": self.total_cache_read_tokens,
            "total_cache_creation_tokens": self.total_cache_creation_tokens,
            "by_model": self.by_model,
            "by_provider": self.by_provider,
            "cost_breakdown": self.cost_breakdown,
        }


class CostAggregator:
    """Aggregates and tracks API call costs."""

    def __init__(self):
        self.requests: List[RequestCost] = []
        self._lock = None  # Thread safety placeholder

    def record_request(
        self,
        request_id: str,
        model: str,
        provider: str,
        total_cost: float,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        stop_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single API request cost."""
        request_cost = RequestCost(
            timestamp=datetime.utcnow(),
            request_id=request_id,
            model=model,
            provider=provider,
            total_cost=total_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
            stop_reason=stop_reason,
            metadata=metadata or {},
        )
        self.requests.append(request_cost)
        logger.debug(
            f"Recorded cost for {model}: ${total_cost:.6f} "
            f"({input_tokens} input, {output_tokens} output tokens)"
        )

    def get_aggregated_metrics(self) -> AggregatedMetrics:
        """Get aggregated metrics across all recorded requests."""
        metrics = AggregatedMetrics()

        for request in self.requests:
            metrics.total_cost += request.total_cost
            metrics.total_requests += 1
            metrics.total_input_tokens += request.input_tokens
            metrics.total_output_tokens += request.output_tokens
            metrics.total_cache_read_tokens += request.cache_read_tokens
            metrics.total_cache_creation_tokens += request.cache_creation_tokens

            # By model
            if request.model not in metrics.by_model:
                metrics.by_model[request.model] = 0.0
            metrics.by_model[request.model] += request.total_cost

            # By provider
            if request.provider not in metrics.by_provider:
                metrics.by_provider[request.provider] = 0.0
            metrics.by_provider[request.provider] += request.total_cost

        # Cost breakdown
        metrics.cost_breakdown = {
            "input": sum(
                (r.input_tokens * 0.5 / 1_000_000)  # Rough estimate
                for r in self.requests
            ),
            "output": sum(
                (r.output_tokens * 1.5 / 1_000_000)  # Rough estimate
                for r in self.requests
            ),
            "cache_read": sum(
                (r.cache_read_tokens * 0.05 / 1_000_000)  # Rough estimate
                for r in self.requests
            ),
            "cache_creation": sum(
                (r.cache_creation_tokens * 0.625 / 1_000_000)  # Rough estimate
                for r in self.requests
            ),
        }

        return metrics

    def get_requests_in_window(
        self, minutes: int = 60
    ) -> List[RequestCost]:
        """Get requests from last N minutes."""
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [r for r in self.requests if r.timestamp >= cutoff]

    def get_metrics_in_window(self, minutes: int = 60) -> AggregatedMetrics:
        """Get aggregated metrics for requests in last N minutes."""
        requests_in_window = self.get_requests_in_window(minutes)
        metrics = AggregatedMetrics()

        for request in requests_in_window:
            metrics.total_cost += request.total_cost
            metrics.total_requests += 1
            metrics.total_input_tokens += request.input_tokens
            metrics.total_output_tokens += request.output_tokens
            metrics.total_cache_read_tokens += request.cache_read_tokens
            metrics.total_cache_creation_tokens += request.cache_creation_tokens

            if request.model not in metrics.by_model:
                metrics.by_model[request.model] = 0.0
            metrics.by_model[request.model] += request.total_cost

            if request.provider not in metrics.by_provider:
                metrics.by_provider[request.provider] = 0.0
            metrics.by_provider[request.provider] += request.total_cost

        return metrics

    def export_requests(self, filepath: str) -> None:
        """Export all recorded requests to JSON."""
        try:
            with open(filepath, "w") as f:
                json.dump(
                    [r.to_dict() for r in self.requests],
                    f,
                    indent=2,
                    default=str,
                )
            logger.info(f"Exported {len(self.requests)} requests to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export requests: {e}")

    def clear(self) -> None:
        """Clear all recorded requests."""
        self.requests.clear()
        logger.info("Cleared all recorded requests")


# Global aggregator instance
_aggregator = None


def get_cost_aggregator() -> CostAggregator:
    """Get or create global cost aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = CostAggregator()
    return _aggregator
