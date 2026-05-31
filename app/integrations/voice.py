"""
Voice integration routes.

POST /integrations/voice/transcribe  — upload audio, get transcript
POST /integrations/voice/synthesize  — post text, get MP3 bytes
GET  /integrations/voice/status      — check which capabilities are live
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.dependencies.auth import require_api_key
from app.services.voice_agent import is_voice_ready, synthesize_speech, transcribe_audio

router = APIRouter(prefix="/integrations/voice", tags=["voice"])


@router.get("/status")
def voice_status(current_client=Depends(require_api_key)):
    """Returns which voice features are available based on configured API keys."""
    return is_voice_ready()


@router.post("/transcribe")
async def transcribe_endpoint(
    audio: UploadFile = File(...),
    current_client=Depends(require_api_key),
):
    """
    Upload an audio file (WAV, MP3, OGG, FLAC) and receive the transcript.

    Requires DEEPGRAM_API_KEY in environment.
    """
    audio_bytes = await audio.read()
    mime = audio.content_type or "audio/wav"
    transcript = await transcribe_audio(audio_bytes, mime_type=mime)
    return {"transcript": transcript, "chars": len(transcript)}


@router.post("/synthesize")
async def synthesize_endpoint(
    text: str = Form(...),
    voice_id: str = Form(default=""),
    current_client=Depends(require_api_key),
):
    """
    Convert text to speech and return raw MP3 audio bytes.

    Requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in environment.
    """
    mp3_bytes = await synthesize_speech(text, voice_id=voice_id or None)
    if not mp3_bytes:
        return {"error": "Speech synthesis unavailable — check ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID"}
    return Response(content=mp3_bytes, media_type="audio/mpeg")
