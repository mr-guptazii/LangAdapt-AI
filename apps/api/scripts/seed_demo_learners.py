"""Seeds the two deterministic demo learners used to verify personalization
actually diverges (see app/services/demo_learners.py for the exact profiles,
and tests/integration/test_personalization_divergence.py for the automated
proof). Idempotent — safe to run more than once.

Run with: python scripts/seed_demo_learners.py  (from apps/api, venv active)
Requires the English curriculum skills to already exist — run scripts/seed.py
first if starting from an empty database.
"""
import asyncio

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.learning.curriculum import get_curriculum
from app.models.language import Language, Skill
from app.services.demo_learners import DEMO_LEARNER_A_EMAIL, DEMO_LEARNER_B_EMAIL, DEMO_PASSWORD, create_demo_learner_a, create_demo_learner_b


async def _ensure_curriculum(db) -> None:
    existing = await db.execute(select(Language).where(Language.code == "en"))
    if existing.scalar_one_or_none() is None:
        db.add(Language(code="en", name="English", native_name="English", supports_learning_engine=True))
        await db.commit()

    for skill_data in get_curriculum("en"):
        existing_skill = await db.execute(select(Skill).where(Skill.language_code == "en", Skill.code == skill_data["code"]))
        if existing_skill.scalar_one_or_none() is None:
            db.add(Skill(language_code="en", **skill_data))
    await db.commit()


async def seed():
    async with AsyncSessionLocal() as db:
        await _ensure_curriculum(db)
        await create_demo_learner_a(db)
        await create_demo_learner_b(db)
        await db.commit()
        print(f"Demo Learner A: {DEMO_LEARNER_A_EMAIL} / {DEMO_PASSWORD}")
        print(f"Demo Learner B: {DEMO_LEARNER_B_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
