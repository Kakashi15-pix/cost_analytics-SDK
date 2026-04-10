"""Tests for pricing manager."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from pricing.manager import PricingManager, get_pricing_manager


class TestPricingManager:
    """Test pricing manager functionality."""

    def test_load_bundled_pricing(self):
        """Test loading bundled pricing file."""
        manager = PricingManager()
        assert len(manager.pricing_data) > 0
        assert "claude-3-opus-20240229" in manager.pricing_data

    def test_get_pricing_existing_model(self):
        """Test retrieving pricing for existing model."""
        manager = PricingManager()
        pricing = manager.get_pricing("claude-3-opus-20240229")
        
        assert pricing is not None
        assert "input_cost_per_1m_tokens" in pricing
        assert "output_cost_per_1m_tokens" in pricing

    def test_get_pricing_missing_model(self):
        """Test retrieving pricing for missing model."""
        manager = PricingManager()
        pricing = manager.get_pricing("nonexistent-model-xyz")
        assert pricing is None

    def test_get_pricing_with_provider(self):
        """Test retrieving pricing with provider hint."""
        manager = PricingManager()
        pricing = manager.get_pricing("claude-3-opus-20240229", provider="anthropic")
        assert pricing is not None

    @patch('pricing.manager.requests.get')
    def test_sync_from_upstream_success(self, mock_get):
        """Test successful upstream sync."""
        mock_data = {"test-model": {"input_cost_per_1m_tokens": 1.0}}
        mock_get.return_value.json.return_value = mock_data
        
        manager = PricingManager()
        manager.sync_state["last_sync"] = None  # Force sync
        
        success = manager.sync_from_upstream()
        
        assert success
        assert manager.pricing_data == mock_data

    @patch('pricing.manager.requests.get')
    def test_sync_from_upstream_failure(self, mock_get):
        """Test upstream sync failure (fallback to local)."""
        mock_get.side_effect = Exception("Network error")
        
        manager = PricingManager()
        manager.sync_state["last_sync"] = None
        initial_data = manager.pricing_data.copy()
        
        success = manager.sync_from_upstream()
        
        assert not success
        # Should still have bundled data
        assert manager.pricing_data == initial_data

    def test_hash_detection(self):
        """Test that unchanged data is not re-saved."""
        manager = PricingManager()
        data1 = {"model": {"cost": 1.0}}
        hash1 = manager._get_hash(data1)
        
        data2 = {"model": {"cost": 1.0}}
        hash2 = manager._get_hash(data2)
        
        assert hash1 == hash2

    def test_global_singleton(self):
        """Test that get_pricing_manager returns singleton."""
        mgr1 = get_pricing_manager()
        mgr2 = get_pricing_manager()
        assert mgr1 is mgr2


class TestPricingFormat:
    """Test pricing data format compliance."""

    def test_pricing_json_valid(self):
        """Test pricing.json is valid JSON."""
        pricing_path = Path(__file__).parent.parent / "pricing" / "pricing.json"
        with open(pricing_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_pricing_has_required_fields(self):
        """Test pricing entries have required fields."""
        manager = PricingManager()
        required_fields = ["input_cost_per_1m_tokens", "output_cost_per_1m_tokens"]
        
        for model, pricing in manager.pricing_data.items():
            if isinstance(pricing, dict):
                for field in required_fields:
                    assert field in pricing, f"Missing {field} for {model}"
                    assert isinstance(pricing[field], (int, float))
