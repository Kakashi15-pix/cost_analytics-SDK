"""Tests for cost extractors."""

import pytest
from pricing.extractors import (
    AnthropicExtractor,
    OpenAIExtractor,
    get_extractor,
)


class TestAnthropicExtractor:
    """Test Anthropic-specific cost extraction."""

    def test_extract_usage_valid_response(self):
        """Test extracting usage from valid Anthropic response."""
        response = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        }
        
        extractor = AnthropicExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage is not None
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    def test_extract_usage_with_cache(self):
        """Test extracting usage with cache tokens."""
        response = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 25,
                "cache_read_input_tokens": 10,
            }
        }
        
        extractor = AnthropicExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage["cache_creation_tokens"] == 25
        assert usage["cache_read_tokens"] == 10

    def test_extract_model(self):
        """Test extracting model from response."""
        response = {"model": "claude-3-opus-20240229"}
        
        extractor = AnthropicExtractor()
        model = extractor.extract_model(response)
        
        assert model == "claude-3-opus-20240229"

    def test_compute_cost(self):
        """Test cost computation for Anthropic."""
        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        }
        
        pricing = {
            "input_cost_per_1m_tokens": 3.0,
            "output_cost_per_1m_tokens": 15.0,
            "cache_creation_cost_per_1m_tokens": 3.75,
            "cache_read_cost_per_1m_tokens": 0.3,
        }
        
        extractor = AnthropicExtractor()
        cost = extractor.compute_cost(usage, pricing)
        
        assert cost.input_cost == 3.0
        assert cost.output_cost == 1.5
        assert cost.total_cost == pytest.approx(4.5)

    def test_compute_cost_with_cache(self):
        """Test cost computation with cache tokens."""
        usage = {
            "input_tokens": 500_000,
            "output_tokens": 50_000,
            "cache_creation_tokens": 100_000,
            "cache_read_tokens": 50_000,
        }
        
        pricing = {
            "input_cost_per_1m_tokens": 10.0,
            "output_cost_per_1m_tokens": 30.0,
            "cache_creation_cost_per_1m_tokens": 12.5,
            "cache_read_cost_per_1m_tokens": 1.0,
        }
        
        extractor = AnthropicExtractor()
        cost = extractor.compute_cost(usage, pricing)
        
        assert cost.input_cost == 5.0
        assert cost.output_cost == 1.5
        assert cost.cache_creation_cost == 1.25
        assert cost.cache_read_cost == 0.05


class TestOpenAIExtractor:
    """Test OpenAI-specific cost extraction."""

    def test_extract_usage_valid_response(self):
        """Test extracting usage from valid OpenAI response."""
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_prompt_tokens": 0,
            }
        }
        
        extractor = OpenAIExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage is not None
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    def test_extract_usage_with_cache(self):
        """Test extracting usage with cached tokens."""
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_prompt_tokens": 20,
            }
        }
        
        extractor = OpenAIExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage["cache_read_tokens"] == 20

    def test_compute_cost(self):
        """Test cost computation for OpenAI."""
        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        }
        
        pricing = {
            "input_cost_per_1m_tokens": 10.0,
            "output_cost_per_1m_tokens": 30.0,
        }
        
        extractor = OpenAIExtractor()
        cost = extractor.compute_cost(usage, pricing)
        
        assert cost.input_cost == 10.0
        assert cost.output_cost == 3.0
        assert cost.total_cost == pytest.approx(13.0)


class TestExtractorRegistry:
    """Test extractor registry and lookup."""

    def test_get_anthropic_extractor(self):
        """Test getting Anthropic extractor."""
        extractor = get_extractor("anthropic")
        assert isinstance(extractor, AnthropicExtractor)

    def test_get_openai_extractor(self):
        """Test getting OpenAI extractor."""
        extractor = get_extractor("openai")
        assert isinstance(extractor, OpenAIExtractor)

    def test_get_missing_extractor(self):
        """Test getting extractor for unknown provider."""
        extractor = get_extractor("unknown-provider")
        assert extractor is None
