"""Automated unit and integration tests for Phase 8 Voice Assistant."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from local_agent.engine.nova_engine import NovaEngine
from local_agent.llm.provider import ChatMessage, LLMProvider, ProviderConfig
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.planner import TaskPlanner
from local_agent.tasks.registry import ToolRegistry, ToolSpec, PermissionLevel
from local_agent.tasks.voice_tools import register_voice_tools
from local_agent.voice.controller import VoiceController
from local_agent.voice.flow import VoiceConversationFlow, VoiceTurnResult
from local_agent.voice.stt import (
    AudioDeviceError,
    SpeechRecognitionError,
    SpeechRecognizer,
    SpeechTimeoutError,
    SpeechUnintelligibleError,
)
from local_agent.voice.tts import TextToSpeechEngine, TTSError
from local_agent.voice.wakeword import WakeWordConsentError, WakeWordDetector


# ---------------------------------------------------------------------------
# Text-to-Speech Engine Tests
# ---------------------------------------------------------------------------
class TestTextToSpeechEngine:
    """Verify local SAPI5 synthesis, mute, rate, volume, and file generation."""

    @pytest.fixture
    def tts(self) -> TextToSpeechEngine:
        return TextToSpeechEngine()

    def test_list_voices_returns_installed_voices(self, tts: TextToSpeechEngine):
        voices = tts.list_voices()
        assert isinstance(voices, list)
        assert len(voices) > 0
        assert "name" in voices[0]

    def test_mute_unmute_toggle(self, tts: TextToSpeechEngine):
        assert tts.is_muted is False
        tts.mute()
        assert tts.is_muted is True
        res = tts.speak("Test speech while muted")
        assert res["spoken"] is False
        assert res["muted"] is True

        tts.unmute()
        assert tts.is_muted is False

    def test_rate_and_volume_clamping(self, tts: TextToSpeechEngine):
        tts.set_rate(500)
        assert tts.rate == 400
        tts.set_rate(50)
        assert tts.rate == 80

        tts.set_volume(1.5)
        assert tts.volume == 1.0
        tts.set_volume(-0.5)
        assert tts.volume == 0.0

    def test_save_speech_to_wav_file(self, tts: TextToSpeechEngine, tmp_path: Path):
        output_file = tmp_path / "spoken_response.wav"
        res = tts.save_to_file("Hello from NOVA voice synthesis", output_file)
        assert res["success"] is True
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_save_empty_text_raises(self, tts: TextToSpeechEngine, tmp_path: Path):
        output_file = tmp_path / "empty.wav"
        with pytest.raises(TTSError, match="Cannot synthesize empty text"):
            tts.save_to_file("   ", output_file)


# ---------------------------------------------------------------------------
# Speech Recognizer Tests
# ---------------------------------------------------------------------------
class TestSpeechRecognizer:
    """Verify audio file parsing, noise handling, and structured error handling."""

    @pytest.fixture
    def stt(self) -> SpeechRecognizer:
        return SpeechRecognizer()

    def test_transcribe_nonexistent_file_raises(self, stt: SpeechRecognizer, tmp_path: Path):
        fake_file = tmp_path / "nonexistent.wav"
        with pytest.raises(SpeechRecognitionError, match="does not exist"):
            stt.transcribe_file(fake_file)

    def test_transcribe_wav_file(self, stt: SpeechRecognizer, tmp_path: Path):
        # Generate a real WAV file using TTS first
        tts = TextToSpeechEngine()
        audio_path = tmp_path / "sample_speech.wav"
        tts.save_to_file("Testing audio transcription", audio_path)

        # Mock recognize_audio_data to avoid live cloud dependency in unit test
        with patch.object(stt, "_recognize_audio_data", return_value="testing audio transcription"):
            result = stt.transcribe_file(audio_path)
            assert result["success"] is True
            assert result["text"] == "testing audio transcription"

    def test_unintelligible_audio_raises(self, stt: SpeechRecognizer, tmp_path: Path):
        tts = TextToSpeechEngine()
        audio_path = tmp_path / "noise.wav"
        tts.save_to_file("Noise", audio_path)

        import speech_recognition as sr
        with patch.object(stt, "_recognize_audio_data", side_effect=sr.UnknownValueError):
            with pytest.raises(SpeechUnintelligibleError):
                stt.transcribe_file(audio_path)

    def test_microphone_timeout_raises(self, stt: SpeechRecognizer):
        import speech_recognition as sr
        with patch("speech_recognition.Microphone"):
            with patch.object(sr.Recognizer, "listen", side_effect=sr.WaitTimeoutError):
                with pytest.raises(SpeechTimeoutError, match="No speech detected"):
                    stt.listen_from_microphone(timeout=1.0, adjust_noise=False)


# ---------------------------------------------------------------------------
# Wake-Word Detector Tests
# ---------------------------------------------------------------------------
class TestWakeWordDetector:
    """Verify privacy safeguards, user consent gating, and trigger matching."""

    def test_default_is_disabled_and_unconsented(self):
        detector = WakeWordDetector()
        assert detector.enabled is False
        assert detector.has_user_consent is False

    def test_enable_without_consent_raises(self):
        detector = WakeWordDetector()
        with pytest.raises(WakeWordConsentError, match="explicit user consent"):
            detector.enable_with_consent(consent=False)

    def test_enable_with_consent_succeeds(self):
        detector = WakeWordDetector()
        detector.enable_with_consent(consent=True)
        assert detector.enabled is True
        assert detector.has_user_consent is True

    def test_wake_word_trigger_matching(self):
        detector = WakeWordDetector()
        detector.enable_with_consent(consent=True)

        assert detector.is_wake_word("Hey Nova, what is the weather?") is True
        assert detector.is_wake_word("Nova open calculator") is True
        assert detector.is_wake_word("Hello world, play music") is False

    def test_extract_command(self):
        detector = WakeWordDetector()
        detector.enable_with_consent(consent=True)

        cmd1 = detector.extract_command("Hey Nova, open notepad")
        assert cmd1 == "open notepad"

        cmd2 = detector.extract_command("Nova, check system memory")
        assert cmd2 == "check system memory"


# ---------------------------------------------------------------------------
# Voice Controller Tests
# ---------------------------------------------------------------------------
class TestVoiceController:
    """Verify visual/state indicators, mute control, and coordination."""

    def test_controller_status(self):
        ctrl = VoiceController()
        status = ctrl.get_status()
        assert status["is_listening"] is False
        assert status["is_recording"] is False
        assert status["is_speaking"] is False
        assert status["is_muted"] is False

    def test_controller_mute_toggle(self):
        ctrl = VoiceController()
        ctrl.set_mute(True)
        assert ctrl.get_status()["is_muted"] is True
        ctrl.set_mute(False)
        assert ctrl.get_status()["is_muted"] is False


# ---------------------------------------------------------------------------
# Conversation Flow Tests
# ---------------------------------------------------------------------------
class DummyLLMProvider(LLMProvider):
    def __init__(self, output: str) -> None:
        super().__init__(ProviderConfig(model_name="dummy"))
        self.output = output

    def is_available(self) -> bool:
        return True

    def generate(self, context: list[ChatMessage]) -> str:
        return self.output

    def generate_stream(self, context: list[ChatMessage]):
        yield self.output


class TestVoiceConversationFlow:
    """Verify end-to-end voice loop: Speech -> Engine -> Planner -> Orchestrator -> Voice."""

    @pytest.fixture
    def flow_setup(self, tmp_path: Path):
        ctrl = VoiceController()
        # Mute audio during testing to avoid sound card disturbance
        ctrl.set_mute(True)

        engine_response = (
            '{"response_type": "conversation", "detected_intent": "chat", '
            '"requested_action": null, "required_tools": [], '
            '"execution_plan": [], "requires_confirmation": false}'
        )
        provider = DummyLLMProvider(engine_response)
        engine = NovaEngine(provider=provider, data_dir=tmp_path)

        flow = VoiceConversationFlow(voice_controller=ctrl, engine=engine)
        return flow, ctrl, tmp_path

    def test_voice_turn_from_audio_file(self, flow_setup):
        flow, ctrl, tmp_path = flow_setup
        audio_file = tmp_path / "input.wav"
        ctrl.tts.save_to_file("Hello NOVA", audio_file)

        # Mock STT to return transcription
        with patch.object(ctrl.stt, "_recognize_audio_data", return_value="hello nova"):
            turn = flow.process_voice_turn(audio_source=audio_file)
            assert turn.transcript == "hello nova"
            assert turn.detected_intent == "chat"
            assert turn.response_text != ""

    def test_voice_turn_with_wake_word_filter(self, flow_setup):
        flow, ctrl, tmp_path = flow_setup
        ctrl.wakeword.enable_with_consent(consent=True)

        audio_file = tmp_path / "untriggered.wav"
        ctrl.tts.save_to_file("random background chatter", audio_file)

        with patch.object(ctrl.stt, "_recognize_audio_data", return_value="random background chatter"):
            turn = flow.process_voice_turn(audio_source=audio_file)
            assert turn.detected_intent == "ignored"
            assert "Wake word not detected" in turn.response_text


# ---------------------------------------------------------------------------
# Tool Registry Integration Tests
# ---------------------------------------------------------------------------
class TestVoiceToolRegistration:
    """Verify tool registration into ToolRegistry and execution."""

    def test_all_voice_tools_registered(self):
        registry = ToolRegistry()
        ctrl = VoiceController()
        ctrl.set_mute(True)
        register_voice_tools(registry, voice_controller=ctrl)

        expected = [
            "voice_speak",
            "voice_listen",
            "voice_set_mute",
            "voice_get_status",
            "voice_configure_wakeword",
        ]
        for name in expected:
            assert registry.has(name)

    def test_voice_speak_tool_to_file(self, tmp_path: Path):
        registry = ToolRegistry()
        ctrl = VoiceController()
        register_voice_tools(registry, voice_controller=ctrl)

        dest_file = tmp_path / "tool_speech.wav"
        speak_tool = registry.get("voice_speak")
        res = speak_tool.handler(text="Testing voice tool", save_path=str(dest_file))
        assert res["success"] is True
        assert dest_file.exists()
