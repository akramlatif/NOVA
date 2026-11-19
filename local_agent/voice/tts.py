"""Text-to-Speech (TTS) Engine for NOVA — Phase 8.

Integrates local Windows SAPI5 via pyttsx3 with zero latency, zero cloud dependencies,
and zero memory overhead. Supports mute control, rate/volume adjustments, voice selection,
and saving spoken responses to audio files.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """Raised when speech synthesis fails."""


class TextToSpeechEngine:
    """Local, low-latency Text-to-Speech engine utilizing native Windows SAPI5."""

    def __init__(
        self,
        rate: int = 175,
        volume: float = 0.9,
        voice_id: Optional[str] = None,
        muted: bool = False,
    ) -> None:
        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))
        self.voice_id = voice_id
        self._muted = muted
        self._lock = threading.Lock()

    @property
    def is_muted(self) -> bool:
        return self._muted

    def mute(self) -> None:
        """Mute spoken audio output."""
        self._muted = True
        logger.info("NOVA Voice output muted.")

    def unmute(self) -> None:
        """Unmute spoken audio output."""
        self._muted = False
        logger.info("NOVA Voice output unmuted.")

    def list_voices(self) -> List[Dict[str, str]]:
        """List all available native SAPI5 voices installed on the system."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            result = []
            for v in voices:
                result.append({
                    "id": v.id,
                    "name": getattr(v, "name", "Unknown Voice"),
                    "languages": getattr(v, "languages", []),
                    "gender": getattr(v, "gender", "unknown"),
                })
            engine.stop()
            return result
        except Exception as e:
            logger.warning("Could not list TTS voices: %s", e)
            return []

    def set_rate(self, rate: int) -> None:
        """Set speaking speed in words per minute (typically 100-300)."""
        self.rate = max(80, min(400, rate))

    def set_volume(self, volume: float) -> None:
        """Set playback volume between 0.0 (silent) and 1.0 (loudest)."""
        self.volume = max(0.0, min(1.0, volume))

    def set_voice(self, voice_name_or_id: str) -> bool:
        """Select a voice by ID or matching name substring."""
        voices = self.list_voices()
        for v in voices:
            if voice_name_or_id.lower() in v["id"].lower() or voice_name_or_id.lower() in v["name"].lower():
                self.voice_id = v["id"]
                logger.info("Selected TTS voice: %s", v["name"])
                return True
        return False

    def speak(self, text: str) -> Dict[str, Any]:
        """Synthesize and speak text aloud unless muted."""
        clean_text = text.strip()
        if not clean_text:
            return {"action": "speak", "spoken": False, "reason": "empty text"}

        if self._muted:
            logger.info("[MUTED] NOVA speech: %s", clean_text)
            return {"action": "speak", "spoken": False, "muted": True, "text": clean_text}

        with self._lock:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                if self.voice_id:
                    engine.setProperty("voice", self.voice_id)

                engine.say(clean_text)
                engine.runAndWait()
                engine.stop()
                return {"action": "speak", "spoken": True, "text": clean_text, "rate": self.rate, "volume": self.volume}
            except Exception as e:
                logger.warning("TTS audio playback failed (may be in non-interactive environment): %s", e)
                return {"action": "speak", "spoken": False, "error": str(e), "text": clean_text}

    def save_to_file(self, text: str, output_path: Path | str) -> Dict[str, Any]:
        """Render speech directly to an audio file (.wav)."""
        clean_text = text.strip()
        if not clean_text:
            raise TTSError("Cannot synthesize empty text to file.")

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                if self.voice_id:
                    engine.setProperty("voice", self.voice_id)

                engine.save_to_file(clean_text, str(dest))
                engine.runAndWait()
                engine.stop()

                if not dest.exists() or dest.stat().st_size == 0:
                    raise TTSError(f"TTS output file {dest.name} was not created or is empty.")

                return {
                    "action": "save_to_file",
                    "path": str(dest),
                    "filename": dest.name,
                    "size_bytes": dest.stat().st_size,
                    "text": clean_text,
                    "success": True,
                }
            except Exception as e:
                raise TTSError(f"Failed to render speech to file {dest}: {e}") from e
