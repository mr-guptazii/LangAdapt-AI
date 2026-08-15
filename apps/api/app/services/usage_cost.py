"""Rough, approximate USD cost estimation from token counts (section 42/57).
Prices are per-million-tokens and deliberately conservative/approximate — this
powers an internal usage dashboard, not billing. Update PRICING as providers
change their published rates; unknown models return 0.0 rather than guessing.
"""

# (input $/1M tokens, output $/1M tokens). Mock/unknown models are intentionally absent.
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-opus-5": (15.00, 75.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model)
    if rates is None:
        return 0.0
    input_rate, output_rate = rates
    cost = (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
    return round(cost, 6)
