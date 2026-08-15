"""Deterministic, dependency-free provider used when no API key is configured
(section 99/114). This lets the whole application boot and demo end-to-end
without external calls. Never used in production (see factory.py)."""
import hashlib
import random
import re

from pydantic import BaseModel

from app.ai.providers.base import EmbeddingProvider, LLMMessage, LLMProvider, LLMResult, LLMUsage, ModelTier

_PAST_TENSE_MAP = {
    "go": "went", "eat": "ate", "buy": "bought", "see": "saw",
    "make": "made", "come": "came", "take": "took", "meet": "met", "get": "got",
}
# 'have' is deliberately excluded: it's overwhelmingly common as an unrelated
# word ("I have a car") or a legitimate auxiliary ("I have eaten"), so
# standalone-word matching on it produced false positives (e.g. flagging both
# 'have' and 'go' in "I have go to the office yesterday" when the learner's
# actual single mistake is 'go' — 'have' isn't wrong there, "had go" isn't the
# fix either). The other entries are safe because they're near-always main verbs.

_ENCOURAGEMENTS = [
    "That's a great point!",
    "I understand what you mean.",
    "Interesting — tell me more.",
    "Nice, let's keep going.",
    "Thanks for sharing that.",
    "That makes sense to me.",
    "I like where this is going.",
    "Good, I'm following along.",
    "That's a nice way to put it.",
    "Got it — makes sense.",
]

# Two pools, not one hardcoded string: without this, every mock reply ended in
# the exact same sentence ("What did you do after that?"), which is what made
# the mock tutor feel like it was repeating itself turn after turn. Splitting
# by whether an error was just detected also makes the pick contextually
# sensible (practice-oriented vs. purely conversational) rather than just
# reducing repetition for its own sake.
_FOLLOW_UPS_GENERAL = [
    "What did you do after that?",
    "How did that make you feel?",
    "Can you tell me more about that?",
    "What happened next?",
    "Why do you think that happened?",
    "What's your favorite part about that?",
    "Has that happened to you before?",
    "What would you do differently next time?",
]
_FOLLOW_UPS_AFTER_CORRECTION = [
    "Can you try that sentence again, using the past tense this time?",
    "What else did you do that day?",
    "Let's practice that a little more — what happened first?",
    "Good effort — want to try rephrasing that?",
]


class MockLLMProvider(LLMProvider):
    """Rule-based stand-in for a real LLM. It can hold a plausible conversation,
    detect a small set of common tense errors, and produce well-formed structured
    output matching whatever Pydantic schema is requested — enough to exercise the
    full agent graph end-to-end without any API key."""

    name = "mock"

    async def complete(self, messages: list[LLMMessage], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024) -> LLMResult:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        reply = f"{random.choice(_ENCOURAGEMENTS)} (mock response to: '{last_user[:60]}')"
        return LLMResult(text=reply, usage=LLMUsage(input_tokens=len(last_user.split()), output_tokens=20, provider=self.name, model="mock-v1"))

    async def structured(
        self, messages: list[LLMMessage], response_model: type[BaseModel], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024
    ) -> tuple[BaseModel, LLMUsage]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        full_text = "\n".join(m.content for m in messages)
        instance = _build_mock_instance(response_model, last_user, full_text)
        usage = LLMUsage(input_tokens=len(last_user.split()), output_tokens=30, provider=self.name, model="mock-v1")
        return instance, usage


def _detect_past_tense_errors(text: str) -> list[dict]:
    errors = []
    words = re.findall(r"\b\w+\b", text.lower())
    has_yesterday = "yesterday" in words or "ago" in words or "last" in words
    if has_yesterday:
        for w in words:
            if w in _PAST_TENSE_MAP:
                errors.append({
                    "type": "grammar",
                    "category": "past_tense",
                    "incorrect": w,
                    "correct": _PAST_TENSE_MAP[w],
                    "severity": "medium",
                    "explanation": f"'{w}' should be in the past tense ('{_PAST_TENSE_MAP[w]}') because the sentence describes something that already happened.",
                    "confidence": 0.9,
                })
    return errors


_MOCK_EXERCISE_BANK = {
    "past_tense": [
        {"question_type": "fill_blank", "prompt": "Yesterday, I ___ (go) to the market and ___ (buy) some fruit.",
         "options": None, "correct_answer": "went / bought", "explanation": "Both verbs describe completed past actions, so they take the simple past form."},
        {"question_type": "multiple_choice", "prompt": "Choose the correct sentence.",
         "options": ["I go to college and meet my friend yesterday.", "I went to college and met my friend yesterday.", "I going to college and meeting my friend yesterday."],
         "correct_answer": "I went to college and met my friend yesterday.", "explanation": "Both verbs need the simple past tense to match 'yesterday'."},
    ],
    "default": [
        {"question_type": "fill_blank", "prompt": "Complete the sentence with the correct form of the word in parentheses.",
         "options": None, "correct_answer": "See the explanation for this skill.", "explanation": "Generated by the mock provider — configure a real LLM_PROVIDER for fully tailored exercises."},
    ],
}


def _extract_skill_code(full_text: str) -> str:
    match = re.search(r'targeting the skill "([^"]+)"', full_text)
    if not match:
        return "default"
    name = match.group(1).lower().replace(" ", "_")
    return name if name in _MOCK_EXERCISE_BANK else "default"


_MOCK_ASSESSMENT_BANK = {
    "vocabulary": {"question_type": "multiple_choice", "prompt": "Which word means 'to obtain something'?",
                   "options": ["achieve", "negotiate", "reliable", "deadline"], "correct_answer": "achieve", "explanation": "'achieve' means to successfully obtain or complete something through effort."},
    "grammar": {"question_type": "multiple_choice", "prompt": "Choose the grammatically correct sentence.",
                "options": ["She go to work every day.", "She goes to work every day.", "She going to work every day."],
                "correct_answer": "She goes to work every day.", "explanation": "Third-person singular subjects take the -s form in the present simple tense."},
    "reading": {"question_type": "multiple_choice", "prompt": "\"After the meeting, Sam felt relieved.\" How did Sam feel?",
                "options": ["Anxious", "Relieved", "Confused"], "correct_answer": "Relieved", "explanation": "The passage states directly that Sam felt relieved."},
    "listening": {"question_type": "multiple_choice", "prompt": "(Audio placeholder) The speaker mentions their weekend plans. What are they doing?",
                  "options": ["Working", "Traveling", "Studying"], "correct_answer": "Traveling", "explanation": "Placeholder listening item — a real STT/audio pipeline is required for authentic listening assessment."},
    "writing": {"question_type": "free_response", "prompt": "Write 2-3 sentences describing your favorite hobby.",
                "options": None, "correct_answer": "A grammatically coherent 2-3 sentence response describing a hobby.", "explanation": "Evaluated on grammar, vocabulary range, and coherence."},
    "speaking": {"question_type": "free_response", "prompt": "(Voice placeholder) Describe your typical morning routine out loud.",
                 "options": None, "correct_answer": "A fluent spoken description of a morning routine.", "explanation": "Placeholder speaking item — requires the voice pipeline for authentic evaluation."},
}


def _extract_candidates(full_text: str) -> list[dict]:
    """The recommendation prompt embeds the real, already-ranked candidate list as
    a Python repr in the system message — parse it back out so the mock provider
    echoes real ranking-engine output instead of inventing unrelated activities."""
    chunks = re.findall(r"\{[^{}]*'activity_type'[^{}]*\}", full_text)
    candidates = []
    for chunk in chunks:
        title = re.search(r"'title': '([^']*)'", chunk)
        activity = re.search(r"'activity_type': '([^']*)'", chunk)
        minutes = re.search(r"'estimated_minutes': (\d+)", chunk)
        reason = re.search(r"'reason_code': '([^']*)'", chunk)
        if title and activity:
            candidates.append({
                "activity_type": activity.group(1), "title": title.group(1),
                "estimated_minutes": int(minutes.group(1)) if minutes else 5,
                "reason_code": reason.group(1) if reason else "weak_skill",
            })
    return candidates


def _build_mock_instance(model: type[BaseModel], user_text: str, full_text: str = "") -> BaseModel:
    """Fills a Pydantic model with plausible mock values based on field names/types,
    special-casing the fields our own schemas actually use so the mock is useful
    (e.g. it really does detect go->went) rather than just structurally valid."""
    if model.__name__ == "GeneratedExercise":
        area_match = re.search(r'skill area "([^"]+)"', full_text)
        area = area_match.group(1) if area_match else "grammar"
        return model.model_validate(_MOCK_ASSESSMENT_BANK.get(area, _MOCK_ASSESSMENT_BANK["grammar"]))

    fields = model.model_fields
    values: dict = {}
    detected = _detect_past_tense_errors(user_text)

    for name, f in fields.items():
        ann = str(f.annotation)
        if name == "errors" and "list" in ann:
            values[name] = detected
        elif name == "exercises":
            values[name] = _MOCK_EXERCISE_BANK[_extract_skill_code(full_text)]
        elif name == "items":
            candidates = _extract_candidates(full_text)
            values[name] = [
                {"activity_type": c["activity_type"], "title": c["title"], "estimated_minutes": c["estimated_minutes"],
                 "reason_summary": f"Ranked highest by the recommendation engine ({c['reason_code'].replace('_', ' ')})."}
                for c in candidates
            ]
        elif name == "statements":
            values[name] = []
        elif name in ("response", "text") and "str" in ann:
            values[name] = f"{random.choice(_ENCOURAGEMENTS)} (mock)"
        elif name == "follow_up_question":
            pool = _FOLLOW_UPS_AFTER_CORRECTION if detected else _FOLLOW_UPS_GENERAL
            values[name] = random.choice(pool)
        elif name == "correction_needed":
            values[name] = len(detected) > 0
        elif name == "correction_priority":
            values[name] = "medium" if detected else "low"
        elif name == "teaching_intent":
            values[name] = "past_tense_practice" if detected else "general_conversation"
        elif name in ("decision",):
            values[name] = "maintain"
        elif name == "reason_code":
            values[name] = "insufficient_data_mock"
        elif name == "confidence":
            values[name] = 0.6
        elif name == "recommended_action":
            values[name] = "continue_conversation"
        elif "float" in ann:
            values[name] = round(random.uniform(0.4, 0.8), 2)
        elif "int" in ann:
            values[name] = random.randint(1, 5)
        elif "bool" in ann:
            values[name] = False
        elif "list" in ann:
            values[name] = []
        elif "dict" in ann:
            values[name] = {}
        elif f.default is not None and f.default.__class__.__name__ != "PydanticUndefinedType":
            continue
        else:
            values[name] = f"mock_{name}"
    # model_validate (not model_construct) so nested schemas like DetectedError
    # inside ErrorAnalysisOutput.errors get properly coerced from plain dicts.
    return model.model_validate(values)


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic pseudo-embedding: hashes text into a fixed-size unit vector.
    Not semantically meaningful, but stable and dependency-free for local dev."""

    name = "mock"

    def __init__(self, dim: int = 384):
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        vec = [rng.uniform(-1, 1) for _ in range(self.dim)]
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]
