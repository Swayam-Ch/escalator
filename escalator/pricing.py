"""Bedrock on-demand prices in USD per 1M tokens (input, output).

Check these against https://aws.amazon.com/bedrock/pricing/ before publishing numbers;
if you change ESCALATOR_SMALL_MODEL / ESCALATOR_LARGE_MODEL, add their prices here.
"""

from __future__ import annotations

PRICES: dict[str, tuple[float, float]] = {
    "us.amazon.nova-micro-v1:0": (0.035, 0.14),
    "us.amazon.nova-lite-v1:0": (0.06, 0.24),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00),
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": (3.00, 15.00),
}


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    if model_id not in PRICES:
        raise KeyError(f"no price for {model_id}; add it to escalator/pricing.py")
    price_in, price_out = PRICES[model_id]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
