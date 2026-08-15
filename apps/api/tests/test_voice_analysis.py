from app.voice.analysis import (
    analyze,
    compute_fluency_score,
    compute_sentence_completion_ratio,
    compute_speaking_rate_wpm,
    count_filler_words,
    count_pauses,
    count_repeated_words,
)
from app.voice.providers.base import TranscriptSegment


def test_speaking_rate_computed_from_word_count_and_duration():
    assert compute_speaking_rate_wpm(word_count=20, duration_seconds=10) == 120.0


def test_speaking_rate_none_when_no_duration():
    assert compute_speaking_rate_wpm(word_count=5, duration_seconds=0) is None


def test_filler_word_detection():
    assert count_filler_words("um so I went to the uh market") == 2
    assert count_filler_words("I really like the market") == 0  # 'like' is not treated as filler


def test_repeated_word_detection():
    assert count_repeated_words("I I went to the the market") == 2
    assert count_repeated_words("I went to the market") == 0


def test_pause_detection_from_segment_gaps():
    segments = [
        TranscriptSegment(text="I went", start=0.0, end=0.5),
        TranscriptSegment(text="to the market", start=0.55, end=1.2),  # no pause (small gap)
        TranscriptSegment(text="and bought fruit", start=2.5, end=3.2),  # pause (1.3s gap)
    ]
    assert count_pauses(segments) == 1


def test_pause_detection_respects_threshold():
    segments = [
        TranscriptSegment(text="a", start=0.0, end=0.5),
        TranscriptSegment(text="b", start=0.7, end=1.0),  # 0.2s gap, below default 0.6s threshold
    ]
    assert count_pauses(segments) == 0
    assert count_pauses(segments, min_gap_seconds=0.1) == 1


def test_fluency_score_penalizes_slow_pace():
    fast_fluent = compute_fluency_score(speaking_rate_wpm=120, pause_count=0, filler_word_count=0, repeated_word_count=0, word_count=20)
    slow = compute_fluency_score(speaking_rate_wpm=40, pause_count=0, filler_word_count=0, repeated_word_count=0, word_count=20)
    assert fast_fluent is not None and slow is not None
    assert fast_fluent > slow


def test_fluency_score_penalizes_disfluency():
    clean = compute_fluency_score(speaking_rate_wpm=120, pause_count=0, filler_word_count=0, repeated_word_count=0, word_count=20)
    disfluent = compute_fluency_score(speaking_rate_wpm=120, pause_count=3, filler_word_count=3, repeated_word_count=2, word_count=20)
    assert clean > disfluent
    assert 0 <= disfluent <= 100


def test_fluency_score_none_for_empty_transcript():
    assert compute_fluency_score(speaking_rate_wpm=None, pause_count=0, filler_word_count=0, repeated_word_count=0, word_count=0) is None


def test_sentence_completion_ratio():
    segments = [
        TranscriptSegment(text="I went to the market.", start=0, end=1),
        TranscriptSegment(text="and bought some fruit", start=1, end=2),  # no terminal punctuation
    ]
    assert compute_sentence_completion_ratio(segments) == 0.5
    assert compute_sentence_completion_ratio([]) == 1.0


def test_analyze_end_to_end_produces_consistent_metrics():
    segments = [
        TranscriptSegment(text="Yesterday I went", start=0.0, end=1.0),
        TranscriptSegment(text="to the market.", start=2.0, end=3.0),
    ]
    result = analyze("Yesterday I went to the market.", segments, duration_seconds=3.0)
    assert result.word_count == 6
    assert result.speaking_rate_wpm == compute_speaking_rate_wpm(6, 3.0)
    assert result.pause_count == 1
    assert result.fluency_score is not None
    assert 0 <= result.fluency_score <= 100
