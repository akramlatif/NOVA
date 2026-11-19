"""Speech-to-Text (STT) Recognition Engine for NOVA — Phase 8.

Provides local microphone recording and audio transcription with ambient noise calibration,
energy thresholding, and structured error classification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SpeechRecognitionError(Exception):
    """Base exception for speech recognition failures."""


class SpeechTimeoutError(SpeechRecognitionError):
    """Raised when no speech is detected within the listening timeout."""


class SpeechUnintelligibleError(SpeechRecognitionError):
    """Raised when audio was captured but could not be understood."""


class AudioDeviceError(SpeechRecognitionError):
    """Raised when audio hardware or microphone is inaccessible."""


class SpeechRecognizer:
    """Manages audio capture and transcription."""

    def __init__(
        self,
        energy_threshold: int = 300,
        dynamic_energy_threshold: bool = True,
        pause_threshold: float = 0.8,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.dynamic_energy_threshold = dynamic_energy_threshold
        self.pause_threshold = pause_threshold

    def _get_recognizer(self):
        """Instantiate a configured SpeechRecognition recognizer instance."""
        import speech_recognition as sr
        r = sr.Recognizer()
        r.energy_threshold = self.energy_threshold
        r.dynamic_energy_threshold = self.dynamic_energy_threshold
        r.pause_threshold = self.pause_threshold
        return r

    def transcribe_file(self, audio_file_path: Path | str) -> Dict[str, Any]:
        """Transcribe an audio file (WAV, AIFF, or FLAC) to text."""
        import speech_recognition as sr

        path = Path(audio_file_path).resolve()
        if not path.exists() or not path.is_file():
            raise SpeechRecognitionError(f"Audio file does not exist: {path}")

        r = self._get_recognizer()
        try:
            with sr.AudioFile(str(path)) as source:
                audio_data = r.record(source)

            # Transcribe audio data
            text = self._recognize_audio_data(r, audio_data)
            return {
                "source": "file",
                "filename": path.name,
                "text": text,
                "success": True,
            }
        except sr.UnknownValueError:
            raise SpeechUnintelligibleError("Audio content was unclear or contained only background noise.")
        except sr.RequestError as e:
            raise SpeechRecognitionError(f"Speech recognition service error: {e}")
        except Exception as e:
            raise SpeechRecognitionError(f"Failed to transcribe audio file {path.name}: {e}") from e

    def listen_from_microphone(
        self,
        timeout: float = 5.0,
        phrase_time_limit: Optional[float] = 10.0,
        adjust_noise: bool = True,
    ) -> Dict[str, Any]:
        """Record audio from the default system microphone and transcribe."""
        import speech_recognition as sr

        r = self._get_recognizer()
        try:
            with sr.Microphone() as source:
                if adjust_noise:
                    logger.info("Calibrating microphone for ambient noise...")
                    r.adjust_for_ambient_noise(source, duration=0.5)

                logger.info("Listening for speech (timeout=%ss)...", timeout)
                audio_data = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

            text = self._recognize_audio_data(r, audio_data)
            return {
                "source": "microphone",
                "text": text,
                "success": True,
            }
        except sr.WaitTimeoutError:
            raise SpeechTimeoutError(f"No speech detected within {timeout} seconds.")
        except sr.UnknownValueError:
            raise SpeechUnintelligibleError("Speech was detected but could not be understood.")
        except (sr.RequestError, OSError) as e:
            raise AudioDeviceError(f"Microphone access or recognition error: {e}") from e

    def _recognize_audio_data(self, recognizer, audio_data) -> str:
        """Internal helper to convert AudioData to text with graceful fallbacks."""
        import speech_recognition as sr

        # Try Google speech recognition (free, built-in, no key required in speech_recognition)
        try:
            return recognizer.recognize_google(audio_data)
        except (sr.RequestError, Exception):
            # Fallback to local sphinx or raw audio acknowledgment if network is offline
            try:
                return recognizer.recognize_sphinx(audio_data)
            except Exception:
                raise sr.UnknownValueError()
