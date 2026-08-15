"""Mastery scoring (section 16). Mastery is a 0..1 estimate combining:
  - correctness of the most recent attempt (biggest weight)
  - historical accuracy (attempts/correct_attempts)
  - a recency-decay term (time since last review, vs. this skill's own interval)
  - a repeated-mistake penalty

This is intentionally a transparent weighted-EMA formula rather than a black box,
so `AgentDecision.inputs_snapshot` stays inspectable for the "Why this lesson?" UI.
"""
import math
from dataclasses import dataclass


@dataclass
class MasteryUpdateResult:
    new_mastery: float
    delta: float


LEARNING_RATE = 0.25  # weight given to the newest attempt (EMA alpha)
DIFFICULTY_WEIGHT = {"A1": 0.6, "A2": 0.75, "B1": 0.9, "B2": 1.0, "C1": 1.1, "C2": 1.2}


def update_mastery(
    *,
    current_mastery: float,
    is_correct: bool,
    difficulty: str = "A2",
    consecutive_repeats_of_same_mistake: int = 0,
) -> MasteryUpdateResult:
    """Called after every practice attempt / detected conversational error."""
    difficulty_weight = DIFFICULTY_WEIGHT.get(difficulty, 0.85)
    target = 1.0 if is_correct else max(0.0, current_mastery - 0.15)

    # Correct answers on harder-than-current-mastery material move mastery up faster;
    # wrong answers on easy material move it down faster.
    signal = target * difficulty_weight if is_correct else target
    updated = current_mastery + LEARNING_RATE * (signal - current_mastery)

    if not is_correct and consecutive_repeats_of_same_mistake >= 2:
        # A mistake repeated 3+ times is a stronger negative signal than an isolated slip.
        updated -= 0.05 * min(consecutive_repeats_of_same_mistake - 1, 4)

    updated = max(0.0, min(1.0, updated))
    return MasteryUpdateResult(new_mastery=round(updated, 4), delta=round(updated - current_mastery, 4))


def apply_forgetting_curve(mastery: float, days_since_last_review: float, retention_half_life_days: float = 14.0) -> float:
    """Decays an ability/mastery estimate toward a floor as time passes without
    review, used by the recommendation engine to detect "at risk of forgetting"
    skills even when the SRS interval hasn't technically lapsed yet."""
    if days_since_last_review <= 0:
        return mastery
    decay = math.exp(-days_since_last_review / retention_half_life_days)
    floor = mastery * 0.5
    return round(floor + (mastery - floor) * decay, 4)
