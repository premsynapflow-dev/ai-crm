"""
Voice Agent Service — transcription + synthesis stubs.

External dependencies required before this activates:
  1. Deepgram (speech-to-text):
       pip install deepgram-sdk
       Set DEEPGRAM_API_KEY=<your key> in .env
       Sign up at https://deepgram.com

  2. ElevenLabs (text-to-speech):
       pip install elevenlabs
       Set ELEVENLABS_API_KEY=<your key> in .env
       Set ELEVENLABS_VOICE_ID=<your voice ID> in .env
       Sign up at https://elevenlabs.io

Once both keys are present in .env the stubs below become live.
"""

from __future__ import annotations

import os
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEEPGRAM_KEY = os.getenv("DEEPGRAM_API_KEY", "")
_ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
_ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """
    Convert audio bytes to text using Deepgram Nova-2.

    Returns the transcribed string, or empty string on failure / missing key.
    """
    if not _DEEPGRAM_KEY:
        logger.warning("DEEPGRAM_API_KEY not set — transcription unavailable.")
        return ""

    try:
        from deepgram import DeepgramClient, PrerecordedOptions  # type: ignore

        client = DeepgramClient(_DEEPGRAM_KEY)
        options = PrerecordedOptions(model="nova-2", smart_format=True, language="en")
        payload = {"buffer": audio_bytes, "mimetype": mime_type}
        response = await client.listen.asyncprerecorded.v("1").transcribe_file(payload, options)
        transcript: str = (
            response.results.channels[0].alternatives[0].transcript
        )
        return transcript.strip()
    except Exception as exc:
        logger.error(f"Deepgram transcription failed: {exc}")
        return ""


async def synthesize_speech(text: str, voice_id: Optional[str] = None) -> bytes:
    """
    Convert text to MP3 audio bytes using ElevenLabs.

    Returns raw MP3 bytes, or empty bytes on failure / missing key.
    """
    if not _ELEVENLABS_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — speech synthesis unavailable.")
        return b""

    vid = voice_id or _ELEVENLABS_VOICE_ID
    if not vid:
        logger.warning("ELEVENLABS_VOICE_ID not set — speech synthesis unavailable.")
        return b""

    try:
        from elevenlabs.client import ElevenLabs  # type: ignore
        from elevenlabs import VoiceSettings  # type: ignore

        client = ElevenLabs(api_key=_ELEVENLABS_KEY)
        audio_generator = client.text_to_speech.convert(
            voice_id=vid,
            text=text,
            model_id="eleven_turbo_v2",
            voice_settings=VoiceSettings(stability=0.4, similarity_boost=0.75),
        )
        return b"".join(audio_generator)
    except Exception as exc:
        logger.error(f"ElevenLabs synthesis failed: {exc}")
        return b""


def is_voice_ready() -> dict:
    """Return which voice capabilities are available based on env keys."""
    return {
        "transcription": bool(_DEEPGRAM_KEY),
        "synthesis": bool(_ELEVENLABS_KEY and _ELEVENLABS_VOICE_ID),
    }
