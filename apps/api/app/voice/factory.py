from functools import lru_cache

from app.core.config import settings
from app.voice.providers.base import PronunciationProvider, STTProvider, TTSProvider


@lru_cache
def get_stt_provider() -> STTProvider:
    if settings.STT_PROVIDER == "openai_whisper" and settings.OPENAI_API_KEY:
        from app.voice.providers.openai_providers import OpenAIWhisperSTT
        return OpenAIWhisperSTT()
    from app.voice.providers.mock_providers import MockSTTProvider
    return MockSTTProvider()


@lru_cache
def get_tts_provider() -> TTSProvider:
    if settings.TTS_PROVIDER == "openai_tts" and settings.OPENAI_API_KEY:
        from app.voice.providers.openai_providers import OpenAITTS
        return OpenAITTS()
    from app.voice.providers.mock_providers import MockTTSProvider
    return MockTTSProvider()


@lru_cache
def get_pronunciation_provider() -> PronunciationProvider:
    # No production-grade phoneme-level provider is wired up yet; this is the
    # extension point (section 20) — implement PronunciationProvider and select
    # it here behind PRONUNCIATION_PROVIDER once one is integrated.
    from app.voice.providers.mock_providers import MockPronunciationProvider
    return MockPronunciationProvider()
