"""Real speech analysis (section 19-20): speaking rate, pauses, filler words,
repeated words, and a derived fluency score are all computed deterministically
from the transcript text and segment timestamps — never randomly generated.

This module is provider-agnostic on purpose: it operates on `TranscriptionResult`
(transcript + segments), so the exact same code path scores a real Whisper
verbose_json response and the mock provider's simulated-but-consistent timing.
The one thing that stays out of scope here is phoneme-level PRONUNCIATION
QUALITY, which no wired-up provider can genuinely produce — see
app/voice/providers/base.py::PronunciationResult.is_estimated.
"""
import re
from dataclasses import dataclass

from app.voice.providers.base import TranscriptSegment

# Conservative filler-word list: only words that are near-never meaningful
# content in isolation, to avoid false positives (e.g. "like" and "so" are
# excluded because they're frequently real content words).
FILLER_WORDS = {"um", "uh", "erm", "hmm", "uhh", "umm"}

MIN_PAUSE_SECONDS = 0.6  # gap between segments long enough to count as a hesitation pause


@dataclass
class SpeechMetrics:
    word_count: int
    speaking_rate_wpm: float | None
    pause_count: int
    filler_word_count: int
    repeated_word_count: int
    fluency_score: float | None  # 0..100, derived from the above
    sentence_completion_ratio: float  # 0..1, fraction of segments ending in terminal punctuation-like pause


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def count_filler_words(transcript: str) -> int:
    words = _tokenize(transcript)
    return sum(1 for w in words if w in FILLER_WORDS)


def count_repeated_words(transcript: str) -> int:
    """Immediate word repetition ('I I went', 'the the market') — a real,
    text-only signal of disfluency, not a random number."""
    words = _tokenize(transcript)
    return sum(1 for i in range(1, len(words)) if words[i] == words[i - 1])


def count_pauses(segments: list[TranscriptSegment], min_gap_seconds: float = MIN_PAUSE_SECONDS) -> int:
    if len(segments) < 2:
        return 0
    pauses = 0
    for prev, nxt in zip(segments, segments[1:], strict=False):
        if nxt.start - prev.end >= min_gap_seconds:
            pauses += 1
    return pauses


def compute_speaking_rate_wpm(word_count: int, duration_seconds: float) -> float | None:
    if duration_seconds <= 0 or word_count == 0:
        return None
    return round((word_count / duration_seconds) * 60, 1)


def compute_fluency_score(
    *, speaking_rate_wpm: float | None, pause_count: int, filler_word_count: int,
    repeated_word_count: int, word_count: int,
) -> float | None:
    """Deterministic 0..100 fluency estimate. Comfortable conversational pace
    for a language learner is treated as ~90-160 wpm; the score is penalized
    for pace far outside that band, and for pauses/fillers/repeats relative to
    how much was actually said (a single filler in a long answer matters less
    than one in a three-word answer)."""
    if word_count == 0:
        return None

    pace_score = 100.0
    if speaking_rate_wpm is not None:
        if speaking_rate_wpm < 90:
            pace_score = max(40.0, 100.0 - (90 - speaking_rate_wpm) * 1.2)
        elif speaking_rate_wpm > 160:
            pace_score = max(40.0, 100.0 - (speaking_rate_wpm - 160) * 0.8)

    disfluency_rate = (pause_count + filler_word_count + repeated_word_count) / max(word_count, 1)
    disfluency_penalty = min(50.0, disfluency_rate * 200)

    score = max(0.0, min(100.0, pace_score - disfluency_penalty))
    return round(score, 1)


def compute_sentence_completion_ratio(segments: list[TranscriptSegment]) -> float:
    """Fraction of segments that end with terminal punctuation — a rough,
    real proxy for 'did the speaker finish their thought' vs. trailing off."""
    if not segments:
        return 1.0
    completed = sum(1 for s in segments if s.text.strip().endswith((".", "!", "?")))
    return round(completed / len(segments), 2)


def analyze(transcript: str, segments: list[TranscriptSegment], duration_seconds: float) -> SpeechMetrics:
    words = _tokenize(transcript)
    word_count = len(words)
    rate = compute_speaking_rate_wpm(word_count, duration_seconds)
    pauses = count_pauses(segments)
    fillers = count_filler_words(transcript)
    repeats = count_repeated_words(transcript)
    fluency = compute_fluency_score(
        speaking_rate_wpm=rate, pause_count=pauses, filler_word_count=fillers,
        repeated_word_count=repeats, word_count=word_count,
    )
    completion = compute_sentence_completion_ratio(segments)
    return SpeechMetrics(
        word_count=word_count, speaking_rate_wpm=rate, pause_count=pauses,
        filler_word_count=fillers, repeated_word_count=repeats, fluency_score=fluency,
        sentence_completion_ratio=completion,
    )
