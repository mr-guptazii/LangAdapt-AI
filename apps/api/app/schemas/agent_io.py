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
    # Matches Message.teaching_intent's column width (app/models/session.py) — see
    # AdaptationDecision.recommended_action's comment below for why these LLM-output
    # max_lengths exist: an unconstrained one crashed a DB write in production.
    teaching_intent: str = Field(max_length=64, description="Short skill code this turn is implicitly reinforcing, e.g. past_tense_practice.")


class DetectedError(BaseModel):
    type: str = Field(description="grammar|vocabulary|spelling|fluency|pronunciation")
    category: str = Field(description="e.g. past_tense, articles, prepositions, word_choice")
    # Matches ErrorOccurrence.incorrect_text/correct_text's column width (app/models/errors.py).
    incorrect: str = Field(max_length=490)
    correct: str = Field(max_length=490)
    severity: str = Field(description="low|medium|high")
    # Matches LearnerError.description's column width (500) — the smaller of the two
    # destinations this value is copied into (ErrorOccurrence.explanation allows 1000).
    explanation: str = Field(max_length=490)
    confidence: float = Field(ge=0, le=1)


class ErrorAnalysisOutput(BaseModel):
    """Section 7 — Error Analysis Agent output."""
    errors: list[DetectedError] = Field(default_factory=list)


class AdaptationDecision(BaseModel):
    """Section 10 / 121 — structured, non-chain-of-thought decision record."""
    decision: str = Field(description="increase_difficulty|maintain|decrease_difficulty")
    reason_code: str = Field(max_length=64)  # matches AgentDecision.reason_code's column width
    confidence: float = Field(ge=0, le=1)
    # max_length is a real safety net, not just a hint: AgentDecision.recommended_action
    # (app/models/agent.py, widened to String(500) alongside this) is a bounded DB
    # column, and an unconstrained free-text field here crashed persist_learning_event
    # outright in production (StringDataRightTruncationError) once the model wrote a
    # longer-than-expected recommendation. The prompt asks for a short sentence; this
    # is the hard ceiling for whatever slips past that, not the target length.
    recommended_action: str = Field(max_length=490)
    target_skill: str | None = None


class TeachingStrategyDecision(BaseModel):
    """Section 11."""
    strategy: str = Field(
        description="direct_explanation|socratic|conversational|repetition|examples|analogy|"
        "multiple_choice|guided_practice|free_response|correction_first|delayed_correction|"
        "challenge_mode|confidence_building"
    )
    reason_code: str = Field(max_length=64)  # matches AgentDecision.reason_code's column width
    reason_summary: str = Field(max_length=490)  # matches AgentDecision.reason_summary's column width
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
    title: str = Field(max_length=200)  # matches LearningRecommendation.title's column width
    reason_summary: str = Field(max_length=490)  # matches LearningRecommendation.reason_summary's column width
    estimated_minutes: int


class RecommendationOutput(BaseModel):
    """Section 45."""
    items: list[RecommendationItem]


class LearnerMemoryStatement(BaseModel):
    memory_type: str = Field(description="recurring_mistake|mastered_topic|preference|milestone|strategy_success")
    content: str = Field(max_length=990)  # matches LearnerMemory.content's column width (1000)
    importance: float = Field(ge=0, le=1)


class LearnerMemoryBatch(BaseModel):
    """Section 8/120 — output of the background learner-model summarizer."""
    statements: list[LearnerMemoryStatement] = Field(default_factory=list)
