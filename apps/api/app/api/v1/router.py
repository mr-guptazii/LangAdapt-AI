from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    assessment,
    auth,
    chat,
    memory,
    mistakes,
    onboarding,
    practice,
    progress,
    recommendations,
    sessions,
    settings,
    users,
    vocabulary,
    voice,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(onboarding.router)
api_router.include_router(assessment.router)
api_router.include_router(chat.router)
api_router.include_router(voice.router)
api_router.include_router(practice.router)
api_router.include_router(vocabulary.router)
api_router.include_router(progress.router)
api_router.include_router(mistakes.router)
api_router.include_router(recommendations.router)
api_router.include_router(memory.router)
api_router.include_router(sessions.router)
api_router.include_router(analytics.router)
api_router.include_router(settings.router)
