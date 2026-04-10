"""
Advanced example: Production-ready cost tracking with observability.
Demonstrates best practices for cost monitoring in production systems.
"""

import logging
import json
from datetime import datetime
from typing import Optional
from dataclasses import asdict

from pricing import (
    CostInterceptor,
    get_cost_aggregator,
    get_pricing_manager,
    AggregatedMetrics,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CostObserver:
    """Production-ready cost observer with alerts and reporting."""

    def __init__(
        self,
        cost_threshold_usd: float = 1.0,
        alert_threshold_pct: float = 150.0,
    ):
        """
        Args:
            cost_threshold_usd: Alert if single request exceeds this cost
            alert_threshold_pct: Alert if cost_per_request increases by this %
        """
        self.interceptor = CostInterceptor(auto_sync_pricing=True)
        self.aggregator = get_cost_aggregator()
        self.pricing_manager = get_pricing_manager()
        
        self.cost_threshold = cost_threshold_usd
        self.alert_threshold_pct = alert_threshold_pct
        
        self.baseline_cost_per_model = {}

    def process_response(
        self,
        response: dict,
        provider: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Process API response with cost tracking and alerts.
        
        Args:
            response: API response from provider
            provider: Provider name ('anthropic', 'openai', etc.)
            request_id: Optional request tracking ID
            metadata: Optional request metadata
        
        Returns:
            Cost details dict or None if extraction failed
        """
        cost_breakdown = self.interceptor.process_response(
            response,
            provider=provider,
            request_id=request_id,
            metadata=metadata,
        )
        
        if not cost_breakdown:
            return None

        # Check for anomalies
        self._check_cost_anomalies(cost_breakdown)

        return asdict(cost_breakdown)

    def _check_cost_anomalies(self, cost_breakdown) -> None:
        """Check for cost anomalies and log alerts."""
        # High single-request cost
        if cost_breakdown.total_cost > self.cost_threshold:
            logger.warning(
                f"HIGH_COST_ALERT: Request {cost_breakdown.model} cost "
                f"${cost_breakdown.total_cost:.6f} (threshold: ${self.cost_threshold})"
            )

        # Cost increase for model
        model = cost_breakdown.model
        cost_per_token = (
            cost_breakdown.total_cost / 
            (cost_breakdown.input_tokens + cost_breakdown.output_tokens + 1)
        )
        
        if model in self.baseline_cost_per_model:
            baseline = self.baseline_cost_per_model[model]
            increase_pct = ((cost_per_token - baseline) / baseline) * 100
            
            if increase_pct > self.alert_threshold_pct:
                logger.warning(
                    f"COST_INCREASE_ALERT: {model} cost per token increased "
                    f"{increase_pct:.1f}% (${baseline:.9f} → ${cost_per_token:.9f})"
                )
        else:
            self.baseline_cost_per_model[model] = cost_per_token

    def get_daily_report(self) -> dict:
        """Generate daily cost report."""
        metrics = self.aggregator.get_aggregated_metrics()
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "period": "daily",
            "summary": {
                "total_cost": round(metrics.total_cost, 6),
                "total_requests": metrics.total_requests,
                "avg_cost_per_request": round(
                    metrics.total_cost / max(metrics.total_requests, 1), 6
                ),
            },
            "by_provider": {
                provider: round(cost, 6)
                for provider, cost in metrics.by_provider.items()
            },
            "by_model": {
                model: round(cost, 6)
                for model, cost in metrics.by_model.items()
            },
            "tokens": {
                "input": metrics.total_input_tokens,
                "output": metrics.total_output_tokens,
                "cache_read": metrics.total_cache_read_tokens,
                "cache_creation": metrics.total_cache_creation_tokens,
            },
        }
        
        return report

    def get_hourly_report(self) -> dict:
        """Generate hourly cost report."""
        metrics = self.aggregator.get_metrics_in_window(minutes=60)
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "period": "hourly",
            "summary": {
                "total_cost": round(metrics.total_cost, 6),
                "total_requests": metrics.total_requests,
                "avg_cost_per_request": round(
                    metrics.total_cost / max(metrics.total_requests, 1), 6
                ),
            },
            "by_provider": {
                provider: round(cost, 6)
                for provider, cost in metrics.by_provider.items()
            },
            "by_model": {
                model: round(cost, 6)
                for model, cost in metrics.by_model.items()
            },
        }
        
        return report

    def export_daily_report(self, filepath: str) -> None:
        """Export daily report to JSON."""
        report = self.get_daily_report()
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Exported daily report to {filepath}")

    def export_costs_snapshot(self, filepath: str) -> None:
        """Export current cost records snapshot."""
        self.aggregator.export_requests(filepath)
        logger.info(f"Exported {len(self.aggregator.requests)} requests to {filepath}")


class CostComparator:
    """Compare costs across models and providers."""

    def __init__(self):
        self.aggregator = get_cost_aggregator()

    def cost_per_input_token(self, model: str) -> Optional[float]:
        """Calculate cost per input token for a model."""
        requests = [r for r in self.aggregator.requests if r.model == model]
        
        if not requests:
            return None

        total_input = sum(r.input_tokens for r in requests)
        total_cost = sum(r.total_cost for r in requests)
        
        if total_input == 0:
            return None
        
        return total_cost / total_input

    def cost_per_output_token(self, model: str) -> Optional[float]:
        """Calculate cost per output token for a model."""
        requests = [r for r in self.aggregator.requests if r.model == model]
        
        if not requests:
            return None

        total_output = sum(r.output_tokens for r in requests)
        total_cost = sum(r.total_cost for r in requests)
        
        if total_output == 0:
            return None
        
        return total_cost / total_output

    def most_expensive_models(self, top_n: int = 5) -> list:
        """Get most expensive models by total cost."""
        metrics = self.aggregator.get_aggregated_metrics()
        
        sorted_models = sorted(
            metrics.by_model.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_models[:top_n]

    def most_efficient_models(self, top_n: int = 5) -> list:
        """Get most cost-efficient models (lowest cost per token)."""
        model_efficiency = {}
        
        for model in set(r.model for r in self.aggregator.requests):
            cost_per_token = (
                self.cost_per_input_token(model) or 0 +
                self.cost_per_output_token(model) or 0
            )
            model_efficiency[model] = cost_per_token
        
        sorted_models = sorted(
            model_efficiency.items(),
            key=lambda x: x[1]
        )
        
        return sorted_models[:top_n]


def example_production_observer():
    """Example: Production cost observer."""
    
    observer = CostObserver(
        cost_threshold_usd=0.10,
        alert_threshold_pct=50.0,
    )
    
    # Simulate processing responses (with real API, these would be from actual calls)
    mock_responses = [
        {
            "model": "claude-3-haiku-20240307",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
        {
            "model": "claude-3-sonnet-20240229",
            "usage": {
                "input_tokens": 500,
                "output_tokens": 200,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    ]
    
    for i, response in enumerate(mock_responses):
        observer.process_response(
            response,
            provider="anthropic",
            request_id=f"req_{i:05d}",
            metadata={"endpoint": "/chat", "user": "example"},
        )
    
    # Get reports
    daily_report = observer.get_daily_report()
    hourly_report = observer.get_hourly_report()
    
    print("Daily Report:")
    print(json.dumps(daily_report, indent=2))
    
    print("\nHourly Report:")
    print(json.dumps(hourly_report, indent=2))


def example_cost_comparison():
    """Example: Compare costs across models."""
    
    # (In production, this would be called after tracking actual requests)
    comparator = CostComparator()
    
    print("\nMost Expensive Models:")
    for model, cost in comparator.most_expensive_models(3):
        print(f"  {model}: ${cost:.6f}")


if __name__ == "__main__":
    print("=" * 70)
    print("Production-Ready Cost Observer")
    print("=" * 70)
    
    example_production_observer()
    example_cost_comparison()
