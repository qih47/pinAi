"""
DEPRECATED: This module is deprecated. Use backend.app.services.pipeline instead.
This file is kept for backward compatibility.
"""

from backend.app.services.pipeline import (
    extract_pdf_text,
    execute_layer_0_gateway,
    _gateway_rule_based_fallback,
    _gateway_flash_result,
    execute_layer_1_analyzer,
    _get_fallback_cognitive_params_rule_based,
    _get_fallback_cognitive_params,
    execute_layer_2_gemma_agentic,
    _format_sse,
)

__all__ = [
    "extract_pdf_text",
    "execute_layer_0_gateway",
    "_gateway_rule_based_fallback",
    "_gateway_flash_result",
    "execute_layer_1_analyzer",
    "_get_fallback_cognitive_params_rule_based",
    "_get_fallback_cognitive_params",
    "execute_layer_2_gemma_agentic",
    "_format_sse",
]
