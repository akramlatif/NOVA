"""Unified Voice Controller for NOVA — Phase 8.

Coordinates microphone capture, recording indicators, speech transcription,
spoken responses, mute controls, and wake-word verification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from local_agent.voice.stt import SpeechRecognizer, SpeechRecognitionError
from local_agent.voice.tts import TextToSpeechEngine
from local_agent.voice.wakeword import WakeWordDetector

logger = logging.getLogger(__name__)


class VoiceController:
    """Manages audio state, active listening, recording indicators, and audio output."""

    def __init__(
        self,
        tts_engine: Optional[TextToSpeechEngine] = None,
        stt_engine: Optional[SpeechRecognizer] = None,
        wakeword_detector: Optional[WakeWordDetector] = None,
    ) -> None:
        self.tts = tts_engine or TextToSpeechEngine()
        self.stt = stt_engine or SpeechRecognizer()
        self.wakeword = wakeword_detector or WakeWordDetector()

        # Visual and state indicators
        self._is_recording: bool = False
        self._is_listening: bool = False
        self._is_speaking: bool = False

    @property
    def is_recording(self) -> bool:
        """Recording indicator: True when microphone buffer is actively receiving audio."""
        return self._is_recording

    @property
    def is_listening(self) -> bool:
        """Listening indicator: True when the system is waiting for speech."""
        return self._is_listening

    @property
    def is_speaking(self) -> bool:
        """Speaking indicator: True during TTS audio generation."""
        return self._is_speaking

    def get_status(self) -> Dict[str, Any]:
        """Return real-time voice system status."""
        return {
            "is_listening": self._is_listening,
            "is_recording": self._is_recording,
            "is_speaking": self._is_speaking,
            "is_muted": self.tts.is_muted,
            "wakeword_enabled": self.wakeword.enabled,
            "speech_rate": self.tts.rate,
            "speech_volume": self.tts.volume,
        }

    def set_mute(self, muted: bool) -> None:
        """Toggle audio output muting."""
        if muted:
            self.tts.mute()
        else:
            self.tts.unmute()

    def speak(self, text: str) -> Dict[str, Any]:
        """Synthesize and speak text response aloud."""
        self._is_speaking = True
        try:
            return self.tts.speak(text)
        finally:
            self._is_speaking = False

    def listen(self, timeout: float = 5.0, phrase_time_limit: float = 10.0) -> Dict[str, Any]:
        """Capture microphone speech and transcribe to text with status indicators."""
        self._is_listening = True
        self._is_recording = True
        try:
            result = self.stt.listen_from_microphone(timeout=timeout, phrase_time_limit=phrase_time_limit)
            return result
        finally:
            self._is_recording = False
            self._is_listening = False

    def transcribe_audio_file(self, file_path: Path | str) -> Dict[str, Any]:
        """Transcribe an audio file into text."""
        return self.stt.transcribe_file(file_path)
