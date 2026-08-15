"""Pydantic models used as LLM structured-output targets throughout the agent
graph. These are the ONLY shapes the agents are allowed to return — see
LLMProvider.structured(). Keeping them here (not scattered per-node) means the
prompt <-> schema contract is easy to audit in one place."""
from pydantic import BaseModel, Field


class ConversationOutput(BaseModel):
    """Section 6 — Conversation Agent output."""
    response: str = Field(description="The tutor's natural-language reply, at the learner's level.")
    follow_up_question: str = Field(description="A question that keeps the learner talking.")
    correction_needed: bool = Field(description="Whether the learner's message contained a mistake worth surfacing.")
    correction_priority: str = Field(description="none|low|medium|high")
    teaching_intent: str = Field(description="Short skill code this turn is implicitly reinforcing, e.g. past_tense_practice.")


class DetectedError(BaseModel):
    type: str = Field(description="grammar|vocabulary|spelling|fluency|pronunciation")
    category: str = Field(description="e.g. past_tense, articles, prepositions, word_choice")
    incorrect: str
    correct: str
    severity: str = Field(description="low|medium|high")
    explanation: str
    confidence: float = Field(ge=0, le=1)


class ErrorAnalysisOutput(BaseModel):
    """Section 7 — Error Analysis Agent output."""
    errors: list[DetectedError] = Field(default_factory=list)


class AdaptationDecision(BaseModel):
    """Section 10 / 121 — structured, non-chain-of-thought decision record."""
    decision: str = Field(description="increase_difficulty|maintain|decrease_difficulty")
    reason_code: str
    confidence: float = Field(ge=0, le=1)
    recommended_action: str
    target_skill: str | None = None


class TeachingStrategyDecision(BaseModel):
    """Section 11."""
    strategy: str = Field(
        description="direct_explanation|socratic|conversational|repetition|examples|analogy|"
        "multiple_choice|guided_practice|free_response|correction_first|delayed_correction|"
        "challenge_mode|confidence_building"
    )
    reason_code: str
    reason_summary: str
    confidence: float = Field(ge=0, le=1)


class GeneratedExercise(BaseModel):
    question_type: str
    prompt: str
    options: list[str] | None = None
    correct_answer: str
    explanation: str


class PracticeGenerationOutput(BaseModel):
    """Section 12."""
    exercises: list[GeneratedExercise]


class RecommendationItem(BaseModel):
    activity_type: str
    title: str
    reason_summary: str
    estimated_minutes: int


class RecommendationOutput(BaseModel):
    """Section 45."""
    items: list[RecommendationItem]


class LearnerMemoryStatement(BaseModel):
    memory_type: str = Field(description="recurring_mistake|mastered_topic|preference|milestone|strategy_success")
    content: str
    importance: float = Field(ge=0, le=1)


class LearnerMemoryBatch(BaseModel):
    """Section 8/120 — output of the background learner-model summarizer."""
    statements: list[LearnerMemoryStatement] = Field(default_factory=list)
