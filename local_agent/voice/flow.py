"""End-to-End Voice Conversation Flow for NOVA — Phase 8.

Pipeline:
  User speaks → Speech Recognition → AI Brain → Task Planner → Tool Execution → Spoken Response.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

from local_agent.engine.nova_engine import NovaEngine
from local_agent.schemas import NovaResponse, ResponseType
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.planner import TaskPlanner
from local_agent.voice.controller import VoiceController

logger = logging.getLogger(__name__)


@dataclass
class VoiceTurnResult:
    """Detailed summary of one complete voice turn."""
    transcript: str
    detected_intent: str
    response_text: str
    action_executed: bool
    plan_summary: Optional[str]
    spoken: bool
    details: Dict[str, Any]


class VoiceConversationFlow:
    """Orchestrates end-to-end voice-driven assistant interactions."""

    def __init__(
        self,
        voice_controller: VoiceController,
        engine: NovaEngine,
        planner: Optional[TaskPlanner] = None,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self.voice = voice_controller
        self.engine = engine
        self.planner = planner
        self.orchestrator = orchestrator

    def process_voice_turn(
        self,
        audio_source: Optional[Union[Path, str]] = None,
        conversation_id: Optional[str] = None,
        timeout: float = 5.0,
    ) -> VoiceTurnResult:
        """Run the full voice interaction pipeline.

        Args:
            audio_source: Optional audio file path. If None, listens to microphone.
            conversation_id: Active conversation ID. If None, creates a fresh one.
            timeout: Listening timeout in seconds.
        """
        # 1. Speech Recognition
        if audio_source:
            stt_result = self.voice.transcribe_audio_file(audio_source)
        else:
            stt_result = self.voice.listen(timeout=timeout)

        raw_transcript = stt_result.get("text", "").strip()
        if not raw_transcript:
            return VoiceTurnResult(
                transcript="",
                detected_intent="unknown",
                response_text="I did not detect any speech.",
                action_executed=False,
                plan_summary=None,
                spoken=False,
                details={"error": "empty_transcript"},
            )

        # 2. Wake-word filtering (if enabled)
        user_command = raw_transcript
        if self.voice.wakeword.enabled:
            if not self.voice.wakeword.is_wake_word(raw_transcript):
                return VoiceTurnResult(
                    transcript=raw_transcript,
                    detected_intent="ignored",
                    response_text="Wake word not detected.",
                    action_executed=False,
                    plan_summary=None,
                    spoken=False,
                    details={"wake_word_triggered": False},
                )
            user_command = self.voice.wakeword.extract_command(raw_transcript)

        # 3. AI Brain: Natural-language understanding & structured intent
        conv_id = conversation_id or self.engine.store.new_conversation()
        nova_resp: NovaResponse = self.engine.chat(conv_id, user_command)

        response_text = nova_resp.user_message or "Understood."
        action_executed = False
        plan_summary = None

        # 4. Task Planner & Tool Execution (if action requested)
        if nova_resp.response_type == ResponseType.ACTION_REQUEST and self.planner and self.orchestrator:
            try:
                plan = self.planner.plan(user_command)
                if plan.steps:
                    self.orchestrator.submit(plan)
                    if not plan.requires_approval:
                        exec_result = self.orchestrator.run(plan.task_id)
                        action_executed = True
                        plan_summary = f"Executed {len(plan.steps)} steps: {exec_result.status.value}"
                        response_text = f"I have completed your request: {plan.intent_summary}."
                    else:
                        response_text = f"This action requires your confirmation before proceeding: {plan.intent_summary}."
            except Exception as e:
                logger.warning("Voice task planning or execution failed: %s", e)
                response_text = f"I understood your request, but could not execute the task: {e}"

        # 5. Spoken Response
        spoken_result = self.voice.speak(response_text)
        spoken_success = spoken_result.get("spoken", False)

        return VoiceTurnResult(
            transcript=raw_transcript,
            detected_intent=nova_resp.detected_intent.value,
            response_text=response_text,
            action_executed=action_executed,
            plan_summary=plan_summary,
            spoken=spoken_success,
            details={
                "conversation_id": conv_id,
                "requires_confirmation": nova_resp.requires_confirmation,
                "required_tools": nova_resp.required_tools,
            },
        )
