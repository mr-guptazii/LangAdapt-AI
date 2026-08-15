"""Spaced-repetition scheduler (section 17).

This implements a simplified SM-2-style algorithm rather than full FSRS: FSRS's
17-parameter model needs a large per-learner review history to fit meaningfully,
which a new product has none of yet. SM-2's ease/interval/repetitions state is a
documented, well-understood subset of what FSRS tracks, and this module is
isolated behind update_schedule() specifically so it can be swapped for a real
FSRS implementation later without touching call sites.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class ScheduleState:
    ease: float
    interval_days: float
    repetitions: int
    retention_estimate: float


@dataclass
class ScheduleResult(ScheduleState):
    next_review_at: datetime


def update_schedule(state: ScheduleState, *, quality: int, now: datetime | None = None) -> ScheduleResult:
    """quality is 0-5 (SM-2 convention): 0-2 = failed recall, 3-5 = success with
    increasing ease. Practice attempts map is_correct -> quality via `quality_from_correctness`.
    """
    now = now or datetime.now(timezone.utc)
    ease = state.ease
    interval = state.interval_days
    reps = state.repetitions

    if quality < 3:
        reps = 0
        interval = 1.0
    else:
        reps += 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 6.0
        else:
            interval = round(interval * ease, 2)

    ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    retention_estimate = min(1.0, 0.5 + 0.1 * reps) if quality >= 3 else max(0.2, state.retention_estimate - 0.2)

    return ScheduleResult(
        ease=round(ease, 3),
        interval_days=interval,
        repetitions=reps,
        retention_estimate=round(retention_estimate, 3),
        next_review_at=now + timedelta(days=interval),
    )


def quality_from_correctness(is_correct: bool, response_time_ms: int | None = None, confidence: float | None = None) -> int:
    if not is_correct:
        return 1
    if response_time_ms is not None and response_time_ms < 4000:
        return 5
    if confidence is not None and confidence < 0.6:
        return 3
    return 4
