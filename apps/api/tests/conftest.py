import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("LLM_PROVIDER", "mock")
# STT/TTS must stay mock in tests regardless of what local .env has configured
# for live/manual verification (e.g. real Groq Whisper) — tests send synthetic
# non-audio bytes, which a real provider correctly rejects as invalid media,
# and tests should never make real network calls anyway.
os.environ.setdefault("STT_PROVIDER", "mock")
os.environ.setdefault("TTS_PROVIDER", "mock")
os.environ.setdefault("JWT_SECRET", "test-secret")
