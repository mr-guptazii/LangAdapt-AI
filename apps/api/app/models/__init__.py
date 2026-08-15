"""Import every model module so Base.metadata is fully populated for Alembic
autogenerate and for create_all() in tests."""

from app.database.base import Base
from app.models.agent import AgentDecision, TeachingStrategy
from app.models.analytics import AIUsageLog, AnalyticsEvent
from app.models.assessment import AssessmentAnswer, AssessmentQuestion, AssessmentSession
from app.models.errors import ErrorOccurrence, LearnerError
from app.models.language import Language, Skill
from app.models.learner import LearnerProfile, LearningGoal, LearningPreference
from app.models.mastery import SkillMastery
from app.models.memory import LearnerMemory, SemanticMemory
from app.models.practice import PracticeAttempt, PracticeQuestion
from app.models.recommendation import LearningRecommendation
from app.models.session import ConversationTurn, LearningSession, Message
from app.models.system import AuditLog, Notification, Subscription
from app.models.user import Profile, User
from app.models.vocabulary import VocabularyItem, VocabularyReview
from app.models.voice import PronunciationScore, SpeechAnalysis, VoiceSession

__all__ = [
    "AIUsageLog",
    "AgentDecision",
    "AnalyticsEvent",
    "AssessmentAnswer",
    "AssessmentQuestion",
    "AssessmentSession",
    "AuditLog",
    "Base",
    "ConversationTurn",
    "ErrorOccurrence",
    "Language",
    "LearnerError",
    "LearnerMemory",
    "LearnerProfile",
    "LearningGoal",
    "LearningPreference",
    "LearningRecommendation",
    "LearningSession",
    "Message",
    "Notification",
    "PracticeAttempt",
    "PracticeQuestion",
    "Profile",
    "PronunciationScore",
    "SemanticMemory",
    "Skill",
    "SkillMastery",
    "SpeechAnalysis",
    "Subscription",
    "TeachingStrategy",
    "User",
    "VocabularyItem",
    "VocabularyReview",
    "VoiceSession",
]
