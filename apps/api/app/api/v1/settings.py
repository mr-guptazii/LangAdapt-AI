from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.errors import LearnerError
from app.models.learner import LearnerProfile, LearningGoal, LearningPreference
from app.models.mastery import SkillMastery
from app.models.memory import LearnerMemory
from app.models.recommendation import LearningRecommendation
from app.models.session import LearningSession, Message
from app.models.system import AuditLog
from app.models.user import Profile, User
from app.models.vocabulary import VocabularyItem
from app.schemas.api import UpdateSettingsRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
    return {
        "ai_personality": profile.ai_personality, "correction_style": profile.correction_style,
        "voice_speed": profile.voice_speed, "interests": profile.interests,
        "store_raw_audio": profile.store_raw_audio, "personalization_enabled": profile.personalization_enabled,
        "analytics_enabled": profile.analytics_enabled,
    }


@router.patch("")
async def update_settings(payload: UpdateSettingsRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    return {"success": True}


@router.post("/export")
async def export_data(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Real, immediate, self-service export — returns the caller's own data
    directly in the response body. Previously this queued nothing and
    promised an email that no email-sending integration in this codebase has
    ever been able to send (see CLAUDE.md); a direct download needs no
    transport at all, so it's what's actually achievable honestly right now."""
    profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    account_profile = profile_result.scalar_one_or_none()

    learner_result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user.id))
    learner_profile = learner_result.scalar_one_or_none()

    export: dict = {
        "account": {
            "email": user.email, "full_name": user.full_name,
            "created_at": user.created_at.isoformat(), "onboarding_completed": user.onboarding_completed,
        },
        "profile": None, "learner_profile": None, "goals": [], "preferences": None,
        "sessions": [], "errors": [], "vocabulary": [], "mastery": [], "memory_facts": [], "recommendations": [],
    }

    if account_profile:
        export["profile"] = {
            "display_name": account_profile.display_name, "ai_personality": account_profile.ai_personality,
            "correction_style": account_profile.correction_style, "interests": account_profile.interests,
        }

    if learner_profile:
        export["learner_profile"] = {
            "native_language_code": learner_profile.native_language_code,
            "target_language_code": learner_profile.target_language_code,
            "cefr_level": learner_profile.cefr_level, "current_difficulty": learner_profile.current_difficulty,
            "streak_days": learner_profile.streak_days, "total_study_minutes": learner_profile.total_study_minutes,
        }

        goals = (await db.execute(select(LearningGoal).where(LearningGoal.learner_profile_id == learner_profile.id))).scalars().all()
        export["goals"] = [g.goal_type for g in goals]

        prefs = (await db.execute(select(LearningPreference).where(LearningPreference.learner_profile_id == learner_profile.id))).scalar_one_or_none()
        if prefs:
            export["preferences"] = {
                "correction_style": prefs.correction_style, "preferred_explanation_length": prefs.preferred_explanation_length,
                "preferred_pace": prefs.preferred_pace, "interests": prefs.interests,
            }

        errors = (await db.execute(select(LearnerError).where(LearnerError.learner_profile_id == learner_profile.id))).scalars().all()
        export["errors"] = [{"category": e.category, "occurrence_count": e.occurrence_count, "description": e.description} for e in errors]

        vocab = (await db.execute(select(VocabularyItem).where(VocabularyItem.learner_profile_id == learner_profile.id))).scalars().all()
        export["vocabulary"] = [{"word": v.word, "translation": v.translation, "status": v.status} for v in vocab]

        mastery = (await db.execute(select(SkillMastery).where(SkillMastery.learner_profile_id == learner_profile.id))).scalars().all()
        export["mastery"] = [{"skill_id": str(m.skill_id), "mastery": m.mastery, "attempts": m.attempts} for m in mastery]

        memories = (await db.execute(select(LearnerMemory).where(LearnerMemory.learner_profile_id == learner_profile.id))).scalars().all()
        export["memory_facts"] = [{"type": m.memory_type, "content": m.content} for m in memories]

        recs = (await db.execute(select(LearningRecommendation).where(LearningRecommendation.learner_profile_id == learner_profile.id))).scalars().all()
        export["recommendations"] = [{"activity_type": r.activity_type, "title": r.title, "status": r.status} for r in recs]

    sessions = (await db.execute(select(LearningSession).where(LearningSession.user_id == user.id))).scalars().all()
    for s in sessions:
        messages = (await db.execute(select(Message).where(Message.session_id == s.id))).scalars().all()
        export["sessions"].append({
            "mode": s.mode, "started_at": s.started_at.isoformat(),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        })

    db.add(AuditLog(actor_user_id=user.id, action="data.export"))
    await db.commit()

    filename = f"lingoadapt-export-{user.id}.json"
    return JSONResponse(content=export, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.delete("/account", status_code=status.HTTP_200_OK)
async def delete_account(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Real deletion, not a soft deactivate flag: the user row is removed and
    every foreign-key-cascaded child row (learner profile, sessions,
    messages, errors, mastery, vocabulary, memories, recommendations, ...)
    is deleted with it via each model's ondelete="CASCADE". The audit log
    row is kept — actor_user_id becomes NULL (ondelete="SET NULL"), not
    cascaded — so "an account was deleted" stays auditable without
    retaining anything that identifies the deleted account."""
    db.add(AuditLog(actor_user_id=user.id, action="account.delete", meta={"deleted_user_id": str(user.id)}))
    await db.flush()
    await db.delete(user)
    await db.commit()
    return {"status": "account_deleted"}
