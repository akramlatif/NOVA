"""NOVA Voice Assistant Module — Phase 8.

Provides local speech recognition, text-to-speech synthesis (SAPI5),
recording indicators, wake-word privacy controls, and end-to-end voice conversation flow.
"""

from local_agent.voice.tts import TextToSpeechEngine, TTSError
from local_agent.voice.stt import (
    SpeechRecognizer,
    SpeechRecognitionError,
    SpeechTimeoutError,
    SpeechUnintelligibleError,
    AudioDeviceError,
)
from local_agent.voice.wakeword import WakeWordDetector, WakeWordConsentError
from local_agent.voice.controller import VoiceController
from local_agent.voice.flow import VoiceConversationFlow, VoiceTurnResult

__all__ = [
    "TextToSpeechEngine",
    "TTSError",
    "SpeechRecognizer",
    "SpeechRecognitionError",
    "SpeechTimeoutError",
    "SpeechUnintelligibleError",
    "AudioDeviceError",
    "WakeWordDetector",
    "WakeWordConsentError",
    "VoiceController",
    "VoiceConversationFlow",
    "VoiceTurnResult",
]
