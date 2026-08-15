"""Real STT/TTS via OpenAI-compatible endpoints, selected only when
STT_PROVIDER=openai_whisper / TTS_PROVIDER=openai_tts and OPENAI_API_KEY is set.

STT requests verbose_json specifically so we get real segment-level timestamps
back — that's what lets app/voice/analysis.py compute genuine speaking rate,
pause, and fluency metrics instead of guessing.
"""
import io

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.voice.providers.base import STTProvider, SynthesisResult, TranscriptionResult, TranscriptSegment, TTSProvider

logger = get_logger(__name__)


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


class OpenAIWhisperSTT(STTProvider):
    name = "openai_whisper"

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language_code: str) -> TranscriptionResult:
        client = _client()
        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "audio.webm"

        resp = await client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
            language=language_code,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

        segments: list[TranscriptSegment] = []
        raw_segments = getattr(resp, "segments", None) or []
        for seg in raw_segments:
            # SDK returns objects with .text/.start/.end when timestamps are requested.
            text = getattr(seg, "text", "") or (seg.get("text") if isinstance(seg, dict) else "")
            start = getattr(seg, "start", None) if not isinstance(seg, dict) else seg.get("start")
            end = getattr(seg, "end", None) if not isinstance(seg, dict) else seg.get("end")
            if text and start is not None and end is not None:
                segments.append(TranscriptSegment(text=text.strip(), start=float(start), end=float(end)))

        duration = float(getattr(resp, "duration", 0.0) or 0.0)
        if not duration and segments:
            duration = segments[-1].end

        # Whisper doesn't return a scalar confidence; approximate one from the
        # average per-segment no_speech_prob / avg_logprob when present, else a
        # conservative constant — this is documented as an approximation, not
        # asserted as a precise ASR confidence.
        confidence = 0.9
        logprobs = [getattr(s, "avg_logprob", None) for s in raw_segments if getattr(s, "avg_logprob", None) is not None]
        if logprobs:
            import math
            avg_logprob = sum(logprobs) / len(logprobs)
            confidence = round(max(0.4, min(0.99, math.exp(avg_logprob))), 2)

        return TranscriptionResult(
            transcript=resp.text, confidence=confidence, language_detected=language_code,
            provider=self.name, segments=segments, duration_seconds=duration,
        )


class OpenAITTS(TTSProvider):
    name = "openai_tts"

    async def synthesize(self, text: str, language_code: str, voice_speed: float = 1.0) -> SynthesisResult:
        client = _client()
        # OpenAI TTS speed is clamped to [0.25, 4.0]; our own voice_speed slider is [0.5, 1.5].
        speed = max(0.25, min(4.0, voice_speed))
        resp = await client.audio.speech.create(model="tts-1", voice="alloy", input=text, speed=speed)
        audio_bytes = resp.read() if hasattr(resp, "read") else resp.content
        return SynthesisResult(audio_bytes=audio_bytes, mime_type="audio/mpeg", provider=self.name)
