from app.learning.spaced_repetition import ScheduleState, quality_from_correctness, update_schedule


def test_failed_recall_resets_repetitions_and_interval():
    state = ScheduleState(ease=2.5, interval_days=10, repetitions=4, retention_estimate=0.9)
    result = update_schedule(state, quality=1)
    assert result.repetitions == 0
    assert result.interval_days == 1.0


def test_successful_recall_grows_interval_with_repetitions():
    state = ScheduleState(ease=2.5, interval_days=0, repetitions=0, retention_estimate=1.0)
    r1 = update_schedule(state, quality=5)
    assert r1.interval_days == 1.0 and r1.repetitions == 1

    r2 = update_schedule(ScheduleState(r1.ease, r1.interval_days, r1.repetitions, r1.retention_estimate), quality=5)
    assert r2.interval_days == 6.0 and r2.repetitions == 2

    r3 = update_schedule(ScheduleState(r2.ease, r2.interval_days, r2.repetitions, r2.retention_estimate), quality=5)
    assert r3.interval_days > r2.interval_days
    assert r3.repetitions == 3


def test_quality_from_correctness_maps_sensibly():
    assert quality_from_correctness(False) == 1
    assert quality_from_correctness(True, response_time_ms=2000) == 5
    assert quality_from_correctness(True, response_time_ms=8000, confidence=0.9) == 4
    assert quality_from_correctness(True, response_time_ms=8000, confidence=0.4) == 3


def test_next_review_at_is_in_the_future():
    state = ScheduleState(ease=2.5, interval_days=0, repetitions=0, retention_estimate=1.0)
    result = update_schedule(state, quality=4)
    assert result.next_review_at is not None
