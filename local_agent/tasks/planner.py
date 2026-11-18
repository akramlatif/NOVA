# ==============================================================================
# NOVA — Task Planner (Phase 3, Tasks 1 & 2)
# ------------------------------------------------------------------------------
# Converts a natural-language request into a VALIDATED multi-step plan.
#
# Hard rules:
#   1. Every tool_name in the proposed plan MUST exist in the ToolRegistry.
#   2. Steps are renumbered into strict execution order.
#   3. The plan records whether ANY step is permission-gated -> the
#      orchestrator then refuses to run without approval (Phase 3, Task 6).
#   4. The planner NEVER executes anything. It only produces data.
#
# Parsing strategy (same defensive approach as Phase 2): small local models
# wrap JSON in prose; we extract candidates, validate with Pydantic, and
# fail with PlanValidationError if nothing parses. The caller then asks the
# user for clarification — NOVA never fabricates a plan.
# ==============================================================================

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from local_agent.memory.manager import MemoryManager

from local_agent.llm.provider import ChatMessage, LLMProvider
from local_agent.tasks.registry import PermissionLevel, ToolRegistry
from local_agent.tasks.schemas import (
    PlanStep,
    PlanValidationError,
    TaskPlan,
)

logger = logging.getLogger("nova.planner")

_MAX_PLAN_STEPS = 12  # controlled execution ceiling — no endless autonomous loops

PLANNER_INSTRUCTION = """You are NOVA's task planner. Break the user's request into a JSON plan.

You may ONLY use tools from this catalog:
{catalog}

Output ONLY a JSON object with these keys:
- intent_summary: one sentence, what the user wants
- expected_result: one sentence, what success looks like
- steps: array of objects, each with:
    - description: what this step does
    - tool_name: EXACTLY a tool name from the catalog above
    - parameters: object with the input keys that tool accepts

Rules:
- Use at most {max_steps} steps. Fewer is better.
- Order steps by execution order (array order = execution order).
- If the request cannot be done with the available tools, output:
  {{"intent_summary": "...", "expected_result": "...", "steps": []}}
  and explain briefly in intent_summary. Never invent tool names.
- parameters must match the tool's input keys. No extra keys.

User request: {request}"""


class TaskPlanner:
    """Natural language -> validated TaskPlan. Provider-injected (replaceable)."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        memory_manager: Optional[MemoryManager] = None,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.memory_manager = memory_manager

    # ------------------------------------------------------------------ main entry
    def plan(self, user_request: str) -> TaskPlan:
        """Produce a validated plan or raise PlanValidationError."""
        mem_context = ""
        if self.memory_manager and self.memory_manager.enabled:
            mem_context = self.memory_manager.get_context_for_prompt(user_request)

        request_with_context = user_request
        if mem_context:
            request_with_context = f"{user_request}\n\n{mem_context}"

        prompt = PLANNER_INSTRUCTION.format(
            catalog=self.registry.catalog_for_planner(),
            max_steps=_MAX_PLAN_STEPS,
            request=request_with_context,
        )
        context = [ChatMessage(role="system", content="You are a precise planner."),
                   ChatMessage(role="user", content=prompt)]

        raw = self.provider.generate(context)
        logger.debug("Planner raw output: %s", raw[:300])

        data = self._extract_json(raw)
        if data is None:
            raise PlanValidationError(
                f"Planner output was not parseable JSON: {raw[:200]!r}"
            )

        steps = data.get("steps")
        if not isinstance(steps, list):
            raise PlanValidationError("Planner output missing 'steps' array")

        # Empty steps = model says it cannot plan this with available tools.
        # That's a VALID outcome — surface it as an empty (non-executable) plan.
        if steps:
            return self._build_validated_plan(user_request, data)
        return TaskPlan(
            task_id=str(uuid.uuid4()),
            user_request=user_request,
            intent_summary=str(data.get("intent_summary", ""))[:500] or "Unable to plan",
            expected_result=str(data.get("expected_result", ""))[:500] or "N/A",
            steps=[],
            requires_approval=False,
        )

    # ------------------------------------------------------------------ validation
    def _build_validated_plan(self, user_request: str, data: dict) -> TaskPlan:
        # 1. Renumber into strict execution order, reject duplicates/malformed
        seen_ids: set[int] = set()
        parsed: list[dict] = []
        for i, s in enumerate(steps_list := data["steps"], start=1):
            if not isinstance(s, dict):
                raise PlanValidationError(f"Step {i} is not an object")
            if "tool_name" not in s:
                raise PlanValidationError(f"Step {i} missing tool_name")
            parsed.append({
                "step_id": i,
                "description": str(s.get("description", "")),
                "tool_name": str(s["tool_name"]),
                "parameters": s.get("parameters") or {},
            })

        # 2. Registry gate — unknown tools are rejected HERE, at planning time
        validated_steps: list[PlanStep] = []
        any_sensitive = False
        for p in parsed:
            spec = self.registry.get(p["tool_name"])  # raises UnknownToolError
            try:
                step = PlanStep(**p)
            except Exception as e:
                raise PlanValidationError(
                    f"Step {p['step_id']} failed schema validation: {e}"
                ) from e
            if spec.permission_level >= PermissionLevel.SENSITIVE:
                any_sensitive = True
            validated_steps.append(step)

        if len(validated_steps) > _MAX_PLAN_STEPS:
            raise PlanValidationError(
                f"Plan exceeds the {_MAX_PLAN_STEPS}-step ceiling"
            )

        # 3. Assemble the final validated plan
        try:
            return TaskPlan(
                task_id=str(uuid.uuid4()),
                user_request=user_request,
                intent_summary=str(data.get("intent_summary", ""))[:500],
                expected_result=str(data.get("expected_result", ""))[:500],
                steps=validated_steps,
                requires_approval=any_sensitive,
            )
        except Exception as e:
            raise PlanValidationError(f"Plan assembly failed: {e}") from e

    # ------------------------------------------------------------------ json extraction
    @staticmethod
    def _extract_json(raw: str) -> Optional[dict]:
        """Fenced -> first-block -> raw text candidates (same as Phase 2)."""
        text = raw.strip()
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidates: list[str] = []
        if fenced:
            candidates.append(fenced[0])
        block = re.search(r"\{.*\}", text, re.DOTALL)
        if block:
            candidates.append(block.group(0))
        candidates.append(text)

        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
        return None
