"""Integración con ElevenLabs: transcripción de notas de voz (Scribe) y voz (TTS)."""
from __future__ import annotations

import httpx

from . import budget
from .config import settings

API = "https://api.elevenlabs.io/v1"
# Voz por defecto (voz prediseñada; el modelo multilingüe habla español).
# Recomendado: elegir una voz española cálida en la Voice Library y poner su ID en ELEVENLABS_VOICE_ID.
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


class ElevenLabsError(RuntimeError):
    pass


async def transcribe(audio: bytes, filename: str, mime: str) -> str:
    """Convierte una nota de voz en texto con ElevenLabs Scribe."""
    if not settings.elevenlabs_enabled:
        raise ElevenLabsError("ElevenLabs no está configurado (falta ELEVENLABS_API_KEY).")
    try:
        budget.reserve_transcription()
    except budget.BudgetExceeded as exc:
        raise ElevenLabsError(str(exc)) from exc
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{API}/speech-to-text",
            headers={"xi-api-key": settings.elevenlabs_api_key},
            data={"model_id": settings.elevenlabs_stt_model, "language_code": "es"},
            files={"file": (filename or "audio.webm", audio, mime or "application/octet-stream")},
        )
    if r.status_code != 200:
        raise ElevenLabsError(f"Error de transcripción ({r.status_code}): {r.text[:200]}")
    return (r.json().get("text") or "").strip()


async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """Genera audio MP3 con una voz tranquila y clara para leer el veredicto."""
    if not settings.elevenlabs_enabled:
        raise ElevenLabsError("ElevenLabs no está configurado (falta ELEVENLABS_API_KEY).")
    try:
        budget.reserve_voice(len(text))
    except budget.BudgetExceeded as exc:
        raise ElevenLabsError(str(exc)) from exc
    voice = voice_id or settings.elevenlabs_voice_id or DEFAULT_VOICE_ID
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API}/text-to-speech/{voice}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": settings.elevenlabs_api_key, "Accept": "audio/mpeg"},
            json={
                "text": text,
                "model_id": settings.elevenlabs_tts_model,
                "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "speed": 0.92},
            },
        )
    if r.status_code != 200:
        raise ElevenLabsError(f"Error de síntesis de voz ({r.status_code}): {r.text[:200]}")
    return r.content
