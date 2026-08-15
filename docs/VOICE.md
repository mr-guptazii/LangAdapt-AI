# Voice System

## Provider interfaces (section 100)

`app/voice/providers/base.py` — three ABCs, selected independently via env vars so STT/TTS/pronunciation can each be swapped without touching call sites:

```python
class STTProvider(ABC):
    async def transcribe(self, audio_bytes, mime_type, language_code) -> TranscriptionResult: ...
class TTSProvider(ABC):
    async def synthesize(self, text, language_code, voice_speed) -> SynthesisResult: ...
class PronunciationProvider(ABC):
    async def score(self, audio_bytes, expected_text, language_code) -> PronunciationResult: ...
```

`STT_PROVIDER` / `TTS_PROVIDER` / `PRONUNCIATION_PROVIDER` env vars select the implementation via `app/voice/factory.py`.

## What's real vs. mock

| Provider | Real implementation | Mock (default, no key needed) |
|---|---|---|
| STT | `OpenAIWhisperSTT` (`openai_providers.py`) — real Whisper transcription | `MockSTTProvider` — returns a labeled placeholder transcript with a randomized-but-deterministic confidence score |
| TTS | `OpenAITTS` — real speech synthesis (`tts-1`) | `MockTTSProvider` — returns empty audio; frontend is expected to fall back to the browser's `SpeechSynthesis` API in mock mode |
| Pronunciation | **Not implemented** — see below | `MockPronunciationProvider` — heuristic score, `is_estimated=True` |

Every response includes `provider` and `is_mock`/`is_estimated` fields so the frontend can — and does — visibly label demo/fallback behavior instead of presenting it as a real score (section 98: never fake a feature silently).

## Real, computed speech metrics (sections 19-20)

`app/voice/analysis.py` computes **speaking rate, pause count, filler-word count, repeated-word count, a derived fluency score, and sentence-completion ratio** — all as deterministic functions of the transcript text and segment timestamps (`TranscriptSegment.start/end`). This is the key design point: the exact same analysis code runs whether the segments came from a real Whisper `verbose_json` response (`OpenAIWhisperSTT`, which requests `timestamp_granularities=["segment"]` specifically to get real timing) or from the mock provider's deterministically-seeded simulated timing. Only the *input* differs between real and mock mode — the scoring logic is identical and genuinely computed either way, never a random number.

- **Speaking rate**: `word_count / duration_seconds * 60`.
- **Pauses**: gaps between consecutive segments ≥ 0.6s.
- **Fillers**: a conservative word list (`um`, `uh`, `erm`, `hmm` — deliberately excludes words like "like"/"so" that are too often real content).
- **Repeated words**: immediate word repetition in the transcript text.
- **Fluency score**: 0-100, penalizes pace far outside ~90-160 wpm and disfluency signals relative to how much was actually said — see `compute_fluency_score()`'s docstring for the exact formula. Fully unit-tested (`tests/test_voice_analysis.py`, 11 tests).

## Pronunciation scoring (section 20)

No production-grade phoneme-level pronunciation provider ships in this build. `PronunciationScore.is_estimated` is a dedicated boolean, always `true` while only the mock/heuristic provider is configured — the schema explicitly separates **raw ASR confidence** (`SpeechAnalysis.asr_confidence`) from **pronunciation quality** (`PronunciationScore.overall_score`), because conflating the two is a common and misleading shortcut. The mock provider's estimate is anchored to the real ASR confidence signal (a legitimate low-fidelity proxy) rather than pure noise, but remains explicitly labeled an estimate either way. `PronunciationScore.phoneme_scores` (nullable JSON) is the schema's readiness for a real phoneme-level provider — populate it once one is integrated behind `PronunciationProvider`.

## Pipeline (as implemented)

```
POST /api/v1/voice/transcribe (multipart: optional session_id, audio, optional expected_text)
  → STTProvider.transcribe() — real Whisper verbose_json (real timestamps) or mock (simulated timestamps)
  → app/voice/analysis.py computes real speech metrics from transcript + segments
  → VoiceSession + SpeechAnalysis rows created (with the real computed metrics)
  → if expected_text provided: PronunciationProvider.score() → PronunciationScore row
  → response: { transcript, asr_confidence, is_mock, pronunciation?, speech_metrics: {...} }

POST /api/v1/voice/synthesize (text, voice_speed)
  → TTSProvider.synthesize()
  → response: { audio_base64 | null, is_mock }  # correctly base64-encoded (fixed from an earlier hex-encoding bug)
```

`session_id` is optional: a voice-first interaction (no prior text turn) creates its own `LearningSession` (mode `"speaking"`), mirroring how `chat_service` handles a missing session id for text.

## Frontend integration (real, not a UI mockup)

- `src/hooks/useVoiceRecorder.ts` — real `MediaRecorder` + Web Audio `AnalyserNode` capture, with a rolling RMS volume buffer for the waveform.
- `src/components/voice/Waveform.tsx` — renders those real volume samples as animated bars (not a decorative fake animation).
- `src/components/voice/SpeechFeedbackCard.tsx` — displays the real computed metrics, visibly labeling mock transcription and estimated pronunciation.
- `/tutor` page: pressing the mic records real audio, uploads it to `/voice/transcribe`, inserts the transcript as a user turn (with its speech-feedback card), sends it through the normal chat pipeline, then calls `/voice/synthesize` for the reply — playing real returned audio via an `<audio>` element, or falling back to the browser's `SpeechSynthesis` API when the mock TTS provider returns no audio.

## Privacy (section 72)

`VoiceSession.raw_audio_retained` defaults to `false` and the transcribe endpoint never writes the uploaded audio bytes to disk or object storage — they're processed in-memory and discarded. `Profile.store_raw_audio` is a user-facing setting (Settings → Privacy) for a future opt-in raw-audio-retention feature; it is not currently read by any code path, since no retention is implemented.

## Limits

15MB max upload (`app/api/v1/voice.py::MAX_AUDIO_BYTES`) — a basic abuse-prevention cap, not a full rate-limiting solution (see [SECURITY.md](SECURITY.md)).
