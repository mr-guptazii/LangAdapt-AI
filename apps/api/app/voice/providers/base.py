"""Voice provider interfaces (sections 18-20, 100). Business logic depends only
on these ABCs; STT_PROVIDER/TTS_PROVIDER/PRONUNCIATION_PROVIDER env vars select
the implementation. Pronunciation quality is ALWAYS returned separate from raw
ASR confidence (section 20) — never conflate the two.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    """Word/phrase-level timing, when the provider exposes it. Real providers
    (Whisper verbose_json) populate this with genuine timestamps; the mock
    provider simulates plausible-but-synthetic timing so the SAME downstream
    analysis functions (app/voice/analysis.py) run on both — no separate
    'fake metrics' code path for mock mode."""
    text: str
    start: float  # seconds
    end: float


@dataclass
class TranscriptionResult:
    transcript: str
    confidence: float  # raw ASR engine confidence — NOT pronunciation quality
    language_detected: str | None = None
    provider: str = ""
    segments: list[TranscriptSegment] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    mime_type: str
    provider: str = ""


@dataclass
class PronunciationResult:
    overall_score: float  # 0..100
    is_estimated: bool  # True unless a real phoneme-level provider produced this
    phoneme_scores: dict | None
    provider: str = ""


class STTProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, mime_type: str, language_code: str) -> TranscriptionResult: ...


class TTSProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str, language_code: str, voice_speed: float = 1.0) -> SynthesisResult: ...


class PronunciationProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def score(
        self, audio_bytes: bytes, expected_text: str, language_code: str, asr_confidence: float | None = None
    ) -> PronunciationResult:
        """asr_confidence, when available, lets an estimate-only provider anchor
        its score to a real signal rather than pure noise — it is never treated
        as the pronunciation score itself (see module docstring)."""
        ...
