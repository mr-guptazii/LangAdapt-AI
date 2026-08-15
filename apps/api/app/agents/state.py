"""Typed LangGraph state (section 40). Every node reads/writes a subset of this;
nothing is passed around as untyped dicts beyond this contract."""
from typing import TypedDict


class DetectedErrorDict(TypedDict):
    type: str
    category: str
    incorrect: str
    correct: str
    severity: str
    explanation: str
    confidence: float


class TutorState(TypedDict, total=False):
    # Identity / routing
    user_id: str
    session_id: str
    learner_profile_id: str
    input_mode: str  # text|voice

    # Input
    user_message: str
    conversation_context: list[dict]  # [{role, content}, ...] recent turns

    # Loaded context
    learner_profile: dict
    learning_preferences: dict
    relevant_memories: list[str]
    recent_error_categories: list[str]

    # Routing decision
    is_significant_learning_event: bool
    agents_invoked: list[str]

    # Agent outputs
    conversation_output: dict
    detected_errors: list[DetectedErrorDict]
    skill_updates: list[dict]  # [{skill_code, new_mastery, delta}]
    difficulty_decision: dict
    teaching_strategy: dict
    recommended_activity: dict | None

    # Final
    response: str
    follow_up_question: str

    # Bookkeeping
    usage_log: list[dict]
    error: str | None
