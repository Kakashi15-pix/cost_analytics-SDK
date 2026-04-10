"""
Interceptor middleware for LLM client libraries.
Extracts cost information from API responses without modifying request/response.
"""
from typing import Any, Callable, Optional, Dict
import logging
import uuid

from pricing.manager import get_pricing_manager
from pricing.extractors import get_extractor, CostBreakdown
from pricing.aggregator import get_cost_aggregator

logger = logging.getLogger(__name__)


class CostInterceptor:
    """
    Intercepts LLM API responses to extract and compute costs.
    Works with signal-plus-pull model: credentials never leave client.
    """

    def __init__(self, auto_sync_pricing: bool = True):
        self.pricing_manager = get_pricing_manager()
        self.aggregator = get_cost_aggregator()
        self.auto_sync_pricing = auto_sync_pricing

    def sync_pricing(self) -> None:
        """Sync pricing from upstream (silent fallback on failure)."""
        if not self.auto_sync_pricing:
            return
        self.pricing_manager.sync_from_upstream()

    def process_response(
        self,
        response: Dict[str, Any],
        provider: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[CostBreakdown]:
        """
        Process API response to extract and compute cost.
        
        Args:
            response: API response dict from provider
            provider: Provider name ('anthropic', 'openai', etc.)
            request_id: Optional request tracking ID
            metadata: Optional metadata to attach to cost record
        
        Returns:
            CostBreakdown with computed costs, or None if extraction failed
        """
        if not response:
            return None

        # Get provider-specific extractor
        extractor = get_extractor(provider)
        if not extractor:
            logger.error(f"No extractor for provider: {provider}")
            return None

        # Extract usage
        usage = extractor.extract_usage(response)
        if not usage:
            logger.warning(f"Failed to extract usage from {provider} response")
            return None

        # Extract model
        model = extractor.extract_model(response)
        if not model:
            logger.warning("Failed to extract model from response")
            return None

        # Get pricing
        pricing = self.pricing_manager.get_pricing(model, provider)
        if not pricing:
            logger.warning(f"No pricing found for model: {model}")
            return None

        # Compute cost
        cost_breakdown = extractor.compute_cost(usage, pricing)
        cost_breakdown.model = model
        cost_breakdown.provider = provider

        # Extract stop reason if available
        if hasattr(extractor, 'extract_stop_reason'):
            cost_breakdown.stop_reason = extractor.extract_stop_reason(response)

        # Record cost
        request_id = request_id or str(uuid.uuid4())
        self.aggregator.record_request(
            request_id=request_id,
            model=model,
            provider=provider,
            total_cost=cost_breakdown.total_cost,
            input_tokens=cost_breakdown.input_tokens,
            output_tokens=cost_breakdown.output_tokens,
            cache_read_tokens=cost_breakdown.cache_read_tokens,
            cache_creation_tokens=cost_breakdown.cache_creation_tokens,
            stop_reason=cost_breakdown.stop_reason,
            metadata=metadata,
        )

        logger.info(
            f"Cost computed for {provider}/{model}: "
            f"${cost_breakdown.total_cost:.6f} "
            f"({cost_breakdown.input_tokens} in, {cost_breakdown.output_tokens} out)"
        )

        return cost_breakdown

    def get_aggregated_metrics(self):
        """Get aggregated cost metrics."""
        return self.aggregator.get_aggregated_metrics()

    def get_metrics_in_window(self, minutes: int = 60):
        """Get metrics for requests in last N minutes."""
        return self.aggregator.get_metrics_in_window(minutes)

    def export_costs(self, filepath: str) -> None:
        """Export all recorded costs to JSON."""
        self.aggregator.export_requests(filepath)


class AnthropicInterceptor(CostInterceptor):
    """Interceptor specifically for Anthropic client library."""

    def __call__(self, response: Any) -> Any:
        """
        Decorator/callable for wrapping Anthropic responses.
        
        Usage:
            interceptor = AnthropicInterceptor()
            
            # Wrap existing client
            client = Anthropic()
            original_message = client.messages.create
            
            def wrapped_create(*args, **kwargs):
                resp = original_message(*args, **kwargs)
                interceptor.process_response(resp.model_dump(), 'anthropic')
                return resp
            
            client.messages.create = wrapped_create
        """
        return self

    def wrap_client(self, client: Any) -> Any:
        """
        Wrap Anthropic client to intercept API calls.
        
        Args:
            client: anthropic.Anthropic() instance
        
        Returns:
            Wrapped client (modified in place)
        """
        original_create = client.messages.create

        def wrapped_create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            
            # Extract response data
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            else:
                response_dict = response.__dict__
            
            # Process for cost
            self.process_response(
                response_dict,
                provider='anthropic',
                metadata={'method': 'messages.create'},
            )
            
            return response

        client.messages.create = wrapped_create
        return client


class OpenAIInterceptor(CostInterceptor):
    """Interceptor specifically for OpenAI client library."""

    def wrap_client(self, client: Any) -> Any:
        """
        Wrap OpenAI client to intercept API calls.
        
        Args:
            client: openai.OpenAI() instance
        
        Returns:
            Wrapped client (modified in place)
        """
        original_create = client.chat.completions.create

        def wrapped_create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            
            # Extract response data
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            else:
                response_dict = response.__dict__
            
            # Process for cost
            self.process_response(
                response_dict,
                provider='openai',
                metadata={'method': 'chat.completions.create'},
            )
            
            return response

        client.chat.completions.create = wrapped_create
        return client


def wrap_anthropic_client(client: Any) -> Any:
    """Convenience function to wrap Anthropic client."""
    interceptor = AnthropicInterceptor()
    return interceptor.wrap_client(client)


def wrap_openai_client(client: Any) -> Any:
    """Convenience function to wrap OpenAI client."""
    interceptor = OpenAIInterceptor()
    return interceptor.wrap_client(client)
