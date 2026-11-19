"""Voice Tool Adapters for NOVA's Task Planner and Tool Registry — Phase 8."""

from __future__ import annotations

from typing import Any, Dict, Optional
from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec
from local_agent.voice.controller import VoiceController


def register_voice_tools(
    registry: ToolRegistry,
    voice_controller: Optional[VoiceController] = None,
) -> VoiceController:
    """Register all Phase 8 Voice Assistant tools into the ToolRegistry."""
    voice = voice_controller or VoiceController()

    # 1. Voice Speak
    def _speak(text: str, save_path: Optional[str] = None) -> Dict[str, Any]:
        if save_path:
            return voice.tts.save_to_file(text, save_path)
        return voice.speak(text)

    registry.register(ToolSpec(
        name="voice_speak",
        description="Speak text aloud using native local text-to-speech, or render to an audio file.",
        handler=_speak,
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=15.0,
        input_schema={"text": "string", "save_path": "optional string"},
        output_schema={"spoken": "bool", "text": "string"},
    ))

    # 2. Voice Listen / Transcribe
    def _listen(file_path: Optional[str] = None, timeout: float = 5.0) -> Dict[str, Any]:
        if file_path:
            return voice.transcribe_audio_file(file_path)
        return voice.listen(timeout=timeout)

    registry.register(ToolSpec(
        name="voice_listen",
        description="Capture microphone speech or transcribe an audio file to text.",
        handler=_listen,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=20.0,
        input_schema={"file_path": "optional string", "timeout": "optional float"},
        output_schema={"text": "string", "success": "bool"},
        error_notes="Raises SpeechRecognitionError on timeout or unintelligible speech.",
    ))

    # 3. Voice Set Mute
    registry.register(ToolSpec(
        name="voice_set_mute",
        description="Mute or unmute spoken audio responses.",
        handler=lambda muted: voice.set_mute(muted) or {"action": "set_mute", "muted": muted},
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={"muted": "bool"},
        output_schema={"action": "string", "muted": "bool"},
    ))

    # 4. Voice Get Status
    registry.register(ToolSpec(
        name="voice_get_status",
        description="Get current voice assistant status: listening, recording, speaking, and mute flags.",
        handler=lambda: voice.get_status(),
        permission_level=PermissionLevel.SAFE,
        timeout_seconds=5.0,
        input_schema={},
        output_schema={"is_listening": "bool", "is_recording": "bool", "is_muted": "bool"},
    ))

    # 5. Voice Configure Wake Word
    def _config_wakeword(enabled: bool, has_user_consent: bool = False) -> Dict[str, Any]:
        if enabled:
            voice.wakeword.enable_with_consent(has_user_consent)
        else:
            voice.wakeword.disable()
        return {"action": "configure_wakeword", "enabled": voice.wakeword.enabled}

    registry.register(ToolSpec(
        name="voice_configure_wakeword",
        description="Enable or disable wake-word activation with explicit user consent.",
        handler=_config_wakeword,
        permission_level=PermissionLevel.NORMAL,
        timeout_seconds=5.0,
        input_schema={"enabled": "bool", "has_user_consent": "optional bool"},
        output_schema={"action": "string", "enabled": "bool"},
        error_notes="Raises WakeWordConsentError if enabling without explicit consent.",
    ))

    return voice
