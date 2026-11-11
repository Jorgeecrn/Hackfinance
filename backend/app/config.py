"""Configuración central leída de variables de entorno (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
FRONTEND_DIR = ROOT_DIR / "frontend"

load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


class Settings:
    # --- Claude (Anthropic) ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
    # low = respuestas rápidas; sube a "medium" si quieres análisis más profundos
    claude_effort: str = os.getenv("CLAUDE_EFFORT", "low")
    claude_timeout_s: float = float(os.getenv("CLAUDE_TIMEOUT_S", "40"))
    claude_max_tool_rounds: int = int(os.getenv("CLAUDE_MAX_TOOL_ROUNDS", "4"))

    # --- ElevenLabs ---
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    elevenlabs_tts_model: str = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2")
    elevenlabs_stt_model: str = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1")

    # --- Investigación externa (opcionales) ---
    online_checks: bool = _bool("ONLINE_CHECKS", True)  # RDAP (antigüedad de dominio)
    google_safe_browsing_key: str = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "")

    # --- Notificaciones (opcional): Telegram para avisar al familiar ---
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Escudo bancario ---
    shield_minutes: int = int(os.getenv("SHIELD_MINUTES", "60"))
    shield_amount_threshold: float = float(os.getenv("SHIELD_AMOUNT_THRESHOLD", "300"))

    # Fuerza el modo sin IA (solo reglas). Útil para tests y si no hay red.
    force_offline: bool = _bool("FORCE_OFFLINE", False)

    # --- Tope de gasto diario (ver app/budget.py). Al llegar al tope: reglas / voz del navegador / analista ---
    ia_max_llamadas_dia: int = int(os.getenv("IA_MAX_LLAMADAS_DIA", "500"))
    ia_max_tokens_dia: int = int(os.getenv("IA_MAX_TOKENS_DIA", "4000000"))
    voz_max_caracteres_dia: int = int(os.getenv("VOZ_MAX_CARACTERES_DIA", "30000"))
    voz_max_transcripciones_dia: int = int(os.getenv("VOZ_MAX_TRANSCRIPCIONES_DIA", "100"))

    # --- Rutas de administración de la demo (reiniciar, simular mensajes, decidir casos...) ---
    # Por defecto solo responden desde el propio portátil. ADMIN_REMOTO=1 las abre a toda la red (no recomendado).
    admin_remoto: bool = _bool("ADMIN_REMOTO", False)

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key) and not self.force_offline

    @property
    def elevenlabs_enabled(self) -> bool:
        return bool(self.elevenlabs_api_key) and not self.force_offline


settings = Settings()
