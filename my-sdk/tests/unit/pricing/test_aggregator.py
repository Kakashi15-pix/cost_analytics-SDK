"""Tests for cost aggregator."""

import pytest
from datetime import datetime, timedelta
from pricing.aggregator import CostAggregator, RequestCost, AggregatedMetrics


class TestCostAggregator:
    """Test cost aggregation functionality."""

    def test_record_single_request(self):
        """Test recording a single request."""
        aggregator = CostAggregator()
        
        aggregator.record_request(
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
        )
        
        assert len(aggregator.requests) == 1
        request = aggregator.requests[0]
        assert request.request_id == "req_001"
        assert request.total_cost == 0.05

    def test_aggregated_metrics(self):
        """Test aggregated metrics calculation."""
        aggregator = CostAggregator()
        
        aggregator.record_request(
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
        )
        
        aggregator.record_request(
            request_id="req_002",
            model="claude-3-sonnet-20240229",
            provider="anthropic",
            total_cost=0.02,
            input_tokens=500,
            output_tokens=50,
        )
        
        metrics = aggregator.get_aggregated_metrics()
        
        assert metrics.total_cost == pytest.approx(0.07)
        assert metrics.total_requests == 2
        assert metrics.total_input_tokens == 1500
        assert metrics.total_output_tokens == 150

    def test_metrics_by_model(self):
        """Test metrics grouped by model."""
        aggregator = CostAggregator()
        
        aggregator.record_request(
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
        )
        
        aggregator.record_request(
            request_id="req_002",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.03,
            input_tokens=600,
            output_tokens=60,
        )
        
        metrics = aggregator.get_aggregated_metrics()
        
        assert "claude-3-opus-20240229" in metrics.by_model
        assert metrics.by_model["claude-3-opus-20240229"] == pytest.approx(0.08)

    def test_metrics_by_provider(self):
        """Test metrics grouped by provider."""
        aggregator = CostAggregator()
        
        aggregator.record_request(
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
        )
        
        aggregator.record_request(
            request_id="req_002",
            model="gpt-4",
            provider="openai",
            total_cost=0.10,
            input_tokens=2000,
            output_tokens=200,
        )
        
        metrics = aggregator.get_aggregated_metrics()
        
        assert "anthropic" in metrics.by_provider
        assert "openai" in metrics.by_provider
        assert metrics.by_provider["anthropic"] == pytest.approx(0.05)
        assert metrics.by_provider["openai"] == pytest.approx(0.10)

    def test_window_metrics(self):
        """Test metrics for requests in time window."""
        aggregator = CostAggregator()
        
        # Record request from 2 hours ago
        old_request = RequestCost(
            timestamp=datetime.utcnow() - timedelta(hours=2),
            request_id="old_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
        )
        aggregator.requests.append(old_request)
        
        # Record request from 30 minutes ago
        new_request = RequestCost(
            timestamp=datetime.utcnow() - timedelta(minutes=30),
            request_id="new_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.03,
            input_tokens=600,
            output_tokens=60,
        )
        aggregator.requests.append(new_request)
        
        # Get metrics for last hour
        metrics = aggregator.get_metrics_in_window(minutes=60)
        
        assert metrics.total_requests == 1
        assert metrics.total_cost == pytest.approx(0.03)

    def test_cache_tokens_aggregation(self):
        """Test aggregation of cache tokens."""
        aggregator = CostAggregator()
        
        aggregator.record_request(
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
            cache_read_tokens=500,
            cache_creation_tokens=200,
        )
        
        metrics = aggregator.get_aggregated_metrics()
        
        assert metrics.total_cache_read_tokens == 500
        assert metrics.total_cache_creation_tokens == 200

    def test_clear_aggregator(self):
        """Test clearing all records."""
        aggregator = CostAggregator()
        
        aggregator.record_request(
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
        )
        
        assert len(aggregator.requests) == 1
        
        aggregator.clear()
        
        assert len(aggregator.requests) == 0


class TestRequestCostData:
    """Test RequestCost data class."""

    def test_request_cost_to_dict(self):
        """Test converting RequestCost to dict."""
        request = RequestCost(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            request_id="req_001",
            model="claude-3-opus-20240229",
            provider="anthropic",
            total_cost=0.05,
            input_tokens=1000,
            output_tokens=100,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
        
        data = request.to_dict()
        
        assert data["request_id"] == "req_001"
        assert data["model"] == "claude-3-opus-20240229"
        assert data["total_cost"] == 0.05


class TestMetricsData:
    """Test AggregatedMetrics data class."""

    def test_metrics_to_dict(self):
        """Test converting metrics to dict."""
        metrics = AggregatedMetrics(
            total_cost=0.10,
            total_requests=2,
            total_input_tokens=1500,
            total_output_tokens=150,
        )
        
        data = metrics.to_dict()
        
        assert data["total_cost"] == 0.10
        assert data["total_requests"] == 2
        assert isinstance(data, dict)
