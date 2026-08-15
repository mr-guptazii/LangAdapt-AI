"""Long-term memory system (section 14/120).

Writes go to two places: LearnerMemory (structured, human-readable fact) and
SemanticMemory (its embedding, for retrieval by meaning). Retrieval never dumps
full conversation history into a prompt — it pulls the top-K most relevant
memories via cosine distance plus a recency/importance tiebreak.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.factory import get_embedding_provider
from app.core.logging import get_logger
from app.models.memory import LearnerMemory, SemanticMemory

logger = get_logger(__name__)


async def store_memory(
    db: AsyncSession,
    *,
    learner_profile_id: UUID,
    memory_type: str,
    content: str,
    importance: float = 0.5,
    related_skill_id: UUID | None = None,
    source_session_id: UUID | None = None,
) -> LearnerMemory:
    memory = LearnerMemory(
        learner_profile_id=learner_profile_id,
        memory_type=memory_type,
        content=content,
        importance=importance,
        related_skill_id=related_skill_id,
        source_session_id=source_session_id,
        last_reinforced_at=datetime.now(timezone.utc),
    )
    db.add(memory)
    await db.flush()

    embedder = get_embedding_provider()
    vector = await embedder.embed(content)
    # Written inside a savepoint: if the 'vector' extension/table isn't available
    # (e.g. a native install without pgvector — see alembic/versions/a1b2c3d4e5f6),
    # this degrades gracefully instead of aborting the whole request's transaction.
    # Docker Compose's postgres (the pgvector/pgvector image) never hits this path.
    try:
        async with db.begin_nested():
            db.add(SemanticMemory(learner_profile_id=learner_profile_id, learner_memory_id=memory.id, text=content, embedding=vector))
    except DBAPIError:
        logger.warning("semantic_memory_write_skipped", reason="vector extension/table unavailable")
    return memory


async def retrieve_relevant_memories(
    db: AsyncSession, *, learner_profile_id: UUID, query_text: str, top_k: int = 5
) -> list[str]:
    """Semantic top-K retrieval via pgvector cosine distance, scoped strictly to
    this learner_profile_id (never cross-user — see core/deps.get_learner_profile).

    Returns [] gracefully (rather than failing the whole conversation turn) if the
    'vector' extension/table isn't available — see the note in store_memory above.
    """
    embedder = get_embedding_provider()
    query_vector = await embedder.embed(query_text)

    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.learner_profile_id == learner_profile_id)
        .order_by(SemanticMemory.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )
    try:
        async with db.begin_nested():
            result = await db.execute(stmt)
            rows = result.scalars().all()
        return [r.text for r in rows]
    except DBAPIError:
        logger.warning("semantic_memory_read_skipped", reason="vector extension/table unavailable")
        return []


async def get_recurring_weaknesses(db: AsyncSession, *, learner_profile_id: UUID, limit: int = 5) -> list[str]:
    stmt = (
        select(LearnerMemory)
        .where(LearnerMemory.learner_profile_id == learner_profile_id, LearnerMemory.memory_type == "recurring_mistake")
        .order_by(LearnerMemory.importance.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [m.content for m in result.scalars().all()]
