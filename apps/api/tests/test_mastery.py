from app.learning.mastery import apply_forgetting_curve, update_mastery


def test_correct_answer_increases_mastery():
    result = update_mastery(current_mastery=0.4, is_correct=True, difficulty="B1")
    assert result.new_mastery > 0.4
    assert result.delta > 0


def test_incorrect_answer_decreases_mastery():
    result = update_mastery(current_mastery=0.6, is_correct=False, difficulty="B1")
    assert result.new_mastery < 0.6
    assert result.delta < 0


def test_mastery_is_clamped_between_0_and_1():
    high = update_mastery(current_mastery=0.98, is_correct=True, difficulty="C2")
    low = update_mastery(current_mastery=0.02, is_correct=False, difficulty="A1")
    assert 0.0 <= high.new_mastery <= 1.0
    assert 0.0 <= low.new_mastery <= 1.0


def test_repeated_mistakes_penalized_more_than_isolated_slip():
    isolated = update_mastery(current_mastery=0.5, is_correct=False, consecutive_repeats_of_same_mistake=0)
    repeated = update_mastery(current_mastery=0.5, is_correct=False, consecutive_repeats_of_same_mistake=3)
    assert repeated.new_mastery < isolated.new_mastery


def test_forgetting_curve_decays_toward_floor_over_time():
    fresh = apply_forgetting_curve(0.8, days_since_last_review=0)
    decayed = apply_forgetting_curve(0.8, days_since_last_review=30)
    assert fresh == 0.8
    assert decayed < fresh
    assert decayed >= 0.4  # floor is mastery * 0.5
