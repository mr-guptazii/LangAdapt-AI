"""Voice pipeline endpoints (sections 18-20). Audio bytes are processed and, unless
the caller's profile has store_raw_audio enabled, never persisted (section 72)."""
import base64
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.deps import get_current_user, get_learner_profile
from app.core.rate_limit import RateLimit
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.session import LearningSession
from app.models.user import User
from app.models.voice import PronunciationScore, SpeechAnalysis, VoiceSession
from app.services import event_service
from app.voice import analysis as speech_analysis_lib
from app.voice.factory import get_pronunciation_provider, get_stt_provider, get_tts_provider

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15MB upload cap (section 71: audio upload limits)

_transcribe_limit = RateLimit(times=20, seconds=60, scope="voice_transcribe")
_synthesize_limit = RateLimit(times=40, seconds=60, scope="voice_synthesize")


@router.post("/transcribe", dependencies=[Depends(_transcribe_limit)])
async def transcribe(
    session_id: UUID | None = Form(None),
    expected_text: str | None = Form(None),
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    learner_profile: LearnerProfile = Depends(get_learner_profile),
    db: AsyncSession = Depends(get_db),
):
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Audio file too large.")
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio upload.")

    session: LearningSession | None = None
    if session_id is not None:
        session = await db.get(LearningSession, session_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    else:
        # Voice-first interactions (no prior text turn) create their own session,
        # mirroring chat_service._get_or_create_session's behavior for text.
        session = LearningSession(user_id=user.id, mode="speaking", started_at=datetime.now(timezone.utc), difficulty=learner_profile.current_difficulty)
        db.add(session)
        await db.flush()
    session_id = session.id

    stt = get_stt_provider()
    transcription = await stt.transcribe(audio_bytes, audio.content_type or "audio/webm", learner_profile.target_language_code)

    # Real, deterministic speech-metric computation (section 19-20) — runs on
    # both real (Whisper) and mock timing data via the same code path.
    metrics = speech_analysis_lib.analyze(transcription.transcript, transcription.segments, transcription.duration_seconds)

    voice_session = VoiceSession(
        session_id=session_id, started_at=datetime.now(timezone.utc), stt_provider=stt.name, tts_provider=app_settings.TTS_PROVIDER,
        raw_audio_retained=False,  # raw audio is processed and discarded, never written to disk here
    )
    db.add(voice_session)
    await db.flush()
    event_service.emit(db, event_type=event_service.VOICE_SESSION_STARTED, user_id=user.id, session_id=session_id, payload={"provider": stt.name})

    pronunciation_payload = None
    pron_overall_score = None
    if expected_text:
        pron_provider = get_pronunciation_provider()
        pron = await pron_provider.score(audio_bytes, expected_text, learner_profile.target_language_code, transcription.confidence)
        pron_overall_score = pron.overall_score
        pronunciation_payload = {"overall_score": pron.overall_score, "is_estimated": pron.is_estimated, "provider": pron.provider}
        event_service.emit(
            db, event_type=event_service.PRONUNCIATION_EVALUATED, user_id=user.id, session_id=session_id,
            payload={"overall_score": pron.overall_score, "is_estimated": pron.is_estimated},
        )

    speaking_score = metrics.fluency_score
    if speaking_score is not None and pron_overall_score is not None:
        speaking_score = round(0.5 * speaking_score + 0.5 * pron_overall_score, 1)

    speech_row = SpeechAnalysis(
        voice_session_id=voice_session.id, transcript=transcription.transcript, asr_confidence=transcription.confidence,
        speaking_score=speaking_score, fluency_score=metrics.fluency_score, speaking_rate_wpm=metrics.speaking_rate_wpm,
        pause_count=metrics.pause_count, filler_word_count=metrics.filler_word_count, repeated_word_count=metrics.repeated_word_count,
    )
    db.add(speech_row)
    await db.flush()

    if pronunciation_payload:
        db.add(PronunciationScore(
            speech_analysis_id=speech_row.id, provider=pronunciation_payload["provider"],
            overall_score=pronunciation_payload["overall_score"], is_estimated=pronunciation_payload["is_estimated"],
            phoneme_scores=None,
        ))

    await db.commit()
    return {
        "session_id": str(session_id),
        "transcript": transcription.transcript,
        "asr_confidence": transcription.confidence,
        "provider": transcription.provider,
        "is_mock": transcription.provider == "mock",
        "pronunciation": pronunciation_payload,
        "speech_metrics": {
            "word_count": metrics.word_count,
            "speaking_rate_wpm": metrics.speaking_rate_wpm,
            "pause_count": metrics.pause_count,
            "filler_word_count": metrics.filler_word_count,
            "repeated_word_count": metrics.repeated_word_count,
            "fluency_score": metrics.fluency_score,
            "speaking_score": speaking_score,
            "sentence_completion_ratio": metrics.sentence_completion_ratio,
        },
    }


@router.post("/synthesize", dependencies=[Depends(_synthesize_limit)])
async def synthesize(text: str = Form(...), voice_speed: float = Form(1.0), learner_profile: LearnerProfile = Depends(get_learner_profile)):
    tts = get_tts_provider()
    result = await tts.synthesize(text, learner_profile.target_language_code, voice_speed)
    return {
        "provider": result.provider,
        "is_mock": result.provider == "mock",
        "mime_type": result.mime_type,
        "audio_base64": base64.b64encode(result.audio_bytes).decode("ascii") if result.audio_bytes else None,
        "note": "mock provider returns no audio — the frontend falls back to the browser SpeechSynthesis API" if result.provider == "mock" else None,
    }
