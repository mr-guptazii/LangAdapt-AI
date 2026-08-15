"""Mock voice providers for local dev without STT/TTS API keys (section 99).
Clearly marked via `provider` field and PronunciationResult.is_estimated=True so
the frontend can visibly flag demo/fallback behavior instead of presenting it as
a real score (section 98).

Even in mock mode, downstream speech-metric computation (speaking rate, pauses,
fillers, fluency — app/voice/analysis.py) runs on the SAME deterministic code
path as the real provider; only the *input* (transcript + segment timing) is
synthetic here. That keeps "we don't fake pronunciation scores" true even in
demo mode — the scores really are computed, just from simulated input.
"""
import hashlib
import random

from app.voice.providers.base import (
    PronunciationProvider,
    PronunciationResult,
    STTProvider,
    SynthesisResult,
    TranscriptionResult,
    TranscriptSegment,
    TTSProvider,
)

_MOCK_TRANSCRIPT_WORDS = [
    "Yesterday", "I", "went", "to", "the", "market", "and", "bought", "some", "fresh", "fruit",
]


class MockSTTProvider(STTProvider):
    name = "mock"

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language_code: str) -> TranscriptionResult:
        # No real ASR is available in mock mode, so the transcript is a labeled
        # placeholder — but segment timing is synthesized deterministically
        # (seeded by the audio payload) so the real analysis pipeline still runs
        # on genuine-shaped input rather than being skipped or faked downstream.
        seed = int(hashlib.sha256(audio_bytes[:2048] or b"empty").hexdigest(), 16) % 1000
        rng = random.Random(seed)
        confidence = round(rng.uniform(0.75, 0.97), 2)

        words = _MOCK_TRANSCRIPT_WORDS
        segments: list[TranscriptSegment] = []
        t = 0.0
        for i, word in enumerate(words):
            duration = rng.uniform(0.25, 0.45)
            # Insert one simulated hesitation pause partway through so pause
            # detection has something real to find in the synthetic timeline.
            if i == len(words) // 2:
                t += rng.uniform(0.6, 1.0)
            end = t + duration
            text = word + ("." if i == len(words) - 1 else "")
            segments.append(TranscriptSegment(text=text, start=round(t, 2), end=round(end, 2)))
            t = end + rng.uniform(0.05, 0.15)

        # The transcript text matches the segments exactly (unlike a disclaimer
        # baked into the string) so downstream word-count/rate analysis stays
        # internally consistent; callers should surface "mock" via the
        # `is_mock`/`provider` response fields instead, not by mangling the text.
        return TranscriptionResult(
            transcript=" ".join(words) + ".",
            confidence=confidence,
            language_detected=language_code,
            provider=self.name,
            segments=segments,
            duration_seconds=round(t, 2),
        )


class MockTTSProvider(TTSProvider):
    name = "mock"

    async def synthesize(self, text: str, language_code: str, voice_speed: float = 1.0) -> SynthesisResult:
        # Returns an empty audio payload; the frontend detects provider == "mock"
        # and falls back to the browser's SpeechSynthesis API for local dev.
        return SynthesisResult(audio_bytes=b"", mime_type="audio/mpeg", provider=self.name)


class MockPronunciationProvider(PronunciationProvider):
    name = "mock"

    async def score(self, audio_bytes: bytes, expected_text: str, language_code: str, asr_confidence: float | None = None) -> PronunciationResult:
        seed = int(hashlib.sha256((expected_text + language_code).encode()).hexdigest(), 16) % 1000
        rng = random.Random(seed)
        # No phoneme-level provider is wired up, so this stays an estimate — but
        # it's now anchored to a real signal (ASR confidence) rather than pure
        # noise, which is a legitimate low-fidelity proxy: a low-confidence
        # transcription usually correlates with less clear pronunciation.
        base = (asr_confidence * 100) if asr_confidence is not None else rng.uniform(60, 90)
        jitter = rng.uniform(-8, 8)
        score = max(0.0, min(100.0, base + jitter))
        return PronunciationResult(
            overall_score=round(score, 1),
            is_estimated=True,
            phoneme_scores=None,
            provider=self.name,
        )
