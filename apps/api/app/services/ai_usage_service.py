"""Shared AI-usage logging for services that call an LLMProvider directly
(outside the agent graph's TutorState['usage_log'] mechanism — see
agents/nodes/persistence.py for that path). Keeps the two mechanisms writing
to the same AIUsageLog table with the same cost-estimation logic."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import LLMUsage, ModelTier
from app.models.analytics import AIUsageLog
from app.services.usage_cost import estimate_cost_usd


def log(
    db: AsyncSession, *, user_id: UUID | None, session_id: UUID | None, node: str, usage: LLMUsage, tier: ModelTier,
) -> None:
    db.add(AIUsageLog(
        user_id=user_id, session_id=session_id, node=node, provider=usage.provider, model=usage.model,
        tier=tier.value, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        estimated_cost_usd=estimate_cost_usd(usage.model, usage.input_tokens, usage.output_tokens),
    ))
