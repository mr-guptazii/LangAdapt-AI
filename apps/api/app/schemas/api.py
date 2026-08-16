"""Request/response schemas for the public API (kept separate from agent_io.py,
which is the internal LLM structured-output contract)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    onboarding_completed: bool


# ---- onboarding ----
class OnboardingRequest(BaseModel):
    native_language_code: str
    target_language_code: str
    goal_types: list[str]
    self_estimated_level: str | None = None
    interests: list[str] = Field(default_factory=list)
    ai_personality: str = "encouraging"
    correction_style: str = "balanced"


# ---- assessment ----
class StartAssessmentRequest(BaseModel):
    # Optional because the placement assessment runs before a LearnerProfile
    # exists (see app/core/deps.py's get_learner_profile_optional) — the
    # onboarding page sends the language picked in its own step 1.
    target_language_code: str | None = None


class StartAssessmentResponse(BaseModel):
    assessment_session_id: UUID
    question: dict


class SubmitAssessmentAnswerRequest(BaseModel):
    question_id: UUID
    answer: str
    target_language_code: str | None = None


class AssessmentProgressResponse(BaseModel):
    completed: bool
    next_question: dict | None = None
    result: dict | None = None


# ---- chat ----
class SendMessageRequest(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=2000)
    mode: str = "conversation"
    input_mode: str = "text"


class CorrectionCard(BaseModel):
    type: str
    category: str
    incorrect: str
    correct: str
    severity: str
    explanation: str


class SendMessageResponse(BaseModel):
    session_id: UUID
    response: str
    follow_up_question: str
    corrections: list[CorrectionCard]
    teaching_strategy: str | None = None
    difficulty_decision: str | None = None
    recommended_activity: dict | None = None
    agents_invoked: list[str]


# ---- practice ----
class PracticeQuestionResponse(BaseModel):
    id: UUID
    question_type: str
    difficulty: str
    prompt: str
    options: list[str] | None
    source_error_id: UUID | None = None
    source_skill_id: UUID | None = None


class SubmitPracticeAnswerRequest(BaseModel):
    question_id: UUID
    answer: str
    response_time_ms: int = 0


class SubmitPracticeAnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str
    new_mastery: float | None = None
    mastery_delta: float | None = None


# ---- vocabulary ----
class VocabularyItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    word: str
    translation: str
    part_of_speech: str | None
    example_sentence: str | None
    status: str
    next_review_at: datetime | None


class VocabularyReviewRequest(BaseModel):
    vocabulary_item_id: UUID
    recalled_correctly: bool
    response_time_ms: int = 0


# ---- settings ----
class UpdateSettingsRequest(BaseModel):
    ai_personality: str | None = None
    correction_style: str | None = None
    voice_speed: float | None = None
    interests: list[str] | None = None
    store_raw_audio: bool | None = None
    personalization_enabled: bool | None = None
    analytics_enabled: bool | None = None
