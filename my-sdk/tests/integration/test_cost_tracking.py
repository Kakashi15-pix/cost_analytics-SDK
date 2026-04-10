"""Integration tests for cost tracking."""

import pytest
from pricing import (
    CostInterceptor,
    AnthropicInterceptor,
    OpenAIInterceptor,
    get_pricing_manager,
    get_cost_aggregator,
)


class TestCostInterceptor:
    """Test cost interceptor integration."""

    def test_process_anthropic_response(self):
        """Test processing Anthropic API response."""
        interceptor = CostInterceptor()
        
        response = {
            "id": "msg_123",
            "model": "claude-3-haiku-20240307",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "stop_reason": "end_turn",
        }
        
        cost = interceptor.process_response(
            response,
            provider="anthropic",
            request_id="req_001",
        )
        
        assert cost is not None
        assert cost.total_cost > 0
        assert cost.model == "claude-3-haiku-20240307"
        assert cost.provider == "anthropic"

    def test_process_openai_response(self):
        """Test processing OpenAI API response."""
        interceptor = CostInterceptor()
        
        response = {
            "id": "chatcmpl_123",
            "model": "gpt-3.5-turbo",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_prompt_tokens": 0,
            },
        }
        
        cost = interceptor.process_response(
            response,
            provider="openai",
            request_id="req_002",
        )
        
        assert cost is not None
        assert cost.total_cost > 0
        assert cost.model == "gpt-3.5-turbo"
        assert cost.provider == "openai"

    def test_aggregation_after_processing(self):
        """Test that costs are aggregated after processing."""
        interceptor = CostInterceptor()
        aggregator = get_cost_aggregator()
        
        # Clear previous data
        aggregator.clear()
        
        response = {
            "model": "claude-3-haiku-20240307",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
        
        interceptor.process_response(response, provider="anthropic", request_id="req_001")
        
        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 1
        assert metrics.total_cost > 0

    def test_multiple_requests_aggregation(self):
        """Test aggregation of multiple requests."""
        interceptor = CostInterceptor()
        aggregator = get_cost_aggregator()
        aggregator.clear()
        
        for i in range(3):
            response = {
                "model": "claude-3-haiku-20240307",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            }
            interceptor.process_response(
                response,
                provider="anthropic",
                request_id=f"req_{i:03d}",
            )
        
        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 3

    def test_pricing_sync_on_init(self):
        """Test pricing sync on initialization."""
        interceptor = CostInterceptor(auto_sync_pricing=True)
        pricing_mgr = get_pricing_manager()
        
        # Should have pricing data (either synced or bundled)
        assert len(pricing_mgr.pricing_data) > 0


class TestAnthropicInterceptor:
    """Test Anthropic-specific interceptor."""

    def test_anthropic_response_processing(self):
        """Test Anthropic-specific response handling."""
        interceptor = AnthropicInterceptor()
        
        response = {
            "model": "claude-3-sonnet-20240229",
            "usage": {
                "input_tokens": 500,
                "output_tokens": 100,
                "cache_creation_input_tokens": 50,
                "cache_read_input_tokens": 0,
            },
            "stop_reason": "end_turn",
        }
        
        cost = interceptor.process_response(response, provider="anthropic")
        
        assert cost is not None
        assert cost.cache_creation_tokens == 50


class TestOpenAIInterceptor:
    """Test OpenAI-specific interceptor."""

    def test_openai_response_processing(self):
        """Test OpenAI-specific response handling."""
        interceptor = OpenAIInterceptor()
        
        response = {
            "model": "gpt-4-turbo",
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 100,
                "cached_prompt_tokens": 50,
            },
        }
        
        cost = interceptor.process_response(response, provider="openai")
        
        assert cost is not None
        assert cost.cache_read_tokens == 50


class TestEndToEndCostTracking:
    """End-to-end cost tracking scenarios."""

    def test_full_tracking_workflow(self):
        """Test complete cost tracking workflow."""
        # Get components
        interceptor = CostInterceptor()
        aggregator = get_cost_aggregator()
        aggregator.clear()
        
        # Process multiple responses
        responses = [
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
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        ]
        
        for i, response in enumerate(responses):
            interceptor.process_response(
                response,
                provider="anthropic",
                request_id=f"req_{i}",
            )
        
        # Check metrics
        metrics = aggregator.get_aggregated_metrics()
        
        assert metrics.total_requests == 2
        assert metrics.total_cost > 0
        assert metrics.total_input_tokens == 300
        assert metrics.total_output_tokens == 150
        assert len(metrics.by_model) == 2

    def test_mixed_provider_tracking(self):
        """Test tracking across multiple providers."""
        interceptor = CostInterceptor()
        aggregator = get_cost_aggregator()
        aggregator.clear()
        
        # Anthropic request
        anthropic_response = {
            "model": "claude-3-haiku-20240307",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
        
        # OpenAI request
        openai_response = {
            "model": "gpt-3.5-turbo",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_prompt_tokens": 0,
            },
        }
        
        interceptor.process_response(anthropic_response, provider="anthropic", request_id="a1")
        interceptor.process_response(openai_response, provider="openai", request_id="o1")
        
        metrics = aggregator.get_aggregated_metrics()
        
        assert metrics.total_requests == 2
        assert "anthropic" in metrics.by_provider
        assert "openai" in metrics.by_provider
