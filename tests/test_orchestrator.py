# ==============================================================================
# NOVA — Phase 3 tests
# ------------------------------------------------------------------------------
# Master-required scenarios, all covered:
#   * simple tasks            * timeouts
#   * multi-step tasks        * failures + failure recovery (resume)
#   * invalid tool calls      * cancellation
#   * permission restrictions * approval mechanism
#
# Uses a FakeProvider (no Ollama) and fake/deterministic tools (echo, clock,
# a flaky tool, a hanging tool, a sensitive tool). Per the phase rule, NO
# real desktop/browser/terminal tools are connected anywhere in this suite.
# ==============================================================================

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

import pytest

from local_agent.llm.provider import ChatMessage, ProviderConfig
from local_agent.tasks.builtin_tools import register_builtin_tools
from local_agent.tasks.history import TaskHistory
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.planner import TaskPlanner
from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec
from local_agent.tasks.schemas import (
    InvalidTransitionError,
    PlanStep,
    PlanValidationError,
    TaskCancelledError,
    TaskPlan,
    TaskStatus,
    TaskResult,
    UnknownToolError,
)

from tests.test_ai_brain import FakeProvider  # reuse the deterministic double


# ============================================================================== fixtures
@pytest.fixture()
def registry() -> ToolRegistry:
    r = ToolRegistry()
    register_builtin_tools(r)

    # extra test tools: a failing one, a hanging one, a sensitive one
    def always_fail(**kwargs):
        raise RuntimeError("simulated tool failure")

    def hang(**kwargs):
        time.sleep(5)

    def secret_op(text: str = "done") -> str:
        return text

    r.register(ToolSpec(
        name="failing_tool", description="always fails",
        handler=always_fail, permission_level=PermissionLevel.SAFE,
        timeout_seconds=2.0,
    ))
    r.register(ToolSpec(
        name="hanging_tool", description="blocks forever",
        handler=hang, permission_level=PermissionLevel.SAFE,
        timeout_seconds=1.0,
    ))
    r.register(ToolSpec(
        name="sensitive_tool", description="pretends to delete files",
        handler=secret_op, permission_level=PermissionLevel.SENSITIVE,
        timeout_seconds=5.0,
    ))
    return r


@pytest.fixture()
def history(tmp_path: Path) -> TaskHistory:
    h = TaskHistory(tmp_path / "tasks.db")
    yield h
    h.close()


def make_plan(steps: List[PlanStep], sensitive: bool = False,
             request: str = "test request") -> TaskPlan:
    return TaskPlan(
        task_id=f"task-{abs(hash(request)) % 100000}",
        user_request=request,
        intent_summary="test intent",
        expected_result="test result",
        steps=steps,
        requires_approval=sensitive,
    )


# ============================================================================== simple + multi-step execution
class TestTaskExecution:
    def test_simple_single_step_task_completes(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history)
        plan = make_plan([PlanStep(step_id=1, description="say hi",
                                   tool_name="echo", parameters={"text": "hi"})])
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.COMPLETED
        assert result.steps[0].output == "hi"
        assert result.verification["all_steps_completed"] is True

    def test_multi_step_task_runs_in_order(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history)
        plan = make_plan([
            PlanStep(step_id=1, description="time", tool_name="clock", parameters={}),
            PlanStep(step_id=2, description="echo", tool_name="echo",
                     parameters={"text": "second"}),
            PlanStep(step_id=3, description="echo", tool_name="echo",
                     parameters={"text": "third"}),
        ])
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.COMPLETED
        assert [s.step_id for s in result.steps] == [1, 2, 3]
        assert result.steps[1].output == "second"
        assert result.steps[2].output == "third"

    def test_execution_stops_at_first_failure(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history)
        plan = make_plan([
            PlanStep(step_id=1, description="ok", tool_name="echo",
                     parameters={"text": "first"}),
            PlanStep(step_id=2, description="fails", tool_name="failing_tool"),
            PlanStep(step_id=3, description="never", tool_name="echo",
                     parameters={"text": "should not run"}),
        ])
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.FAILED
        assert len(result.steps) == 2          # step 3 never executed
        assert result.steps[1].status == TaskStatus.FAILED

    def test_result_verification_counts(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history)
        plan = make_plan([
            PlanStep(step_id=1, description="a", tool_name="echo", parameters={"text": "x"}),
            PlanStep(step_id=2, description="b", tool_name="echo", parameters={"text": "y"}),
        ])
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.verification == {
            "all_steps_completed": True,
            "planned_step_count": 2,
            "completed_step_count": 2,
            "expected_result": "test result",
        }


# ============================================================================== invalid tool calls
class TestInvalidToolCalls:
    def test_planner_rejects_unknown_tool(self, registry) -> None:
        malicious = json.dumps({
            "intent_summary": "x", "expected_result": "y",
            "steps": [{"description": "evil", "tool_name": "format_c_drive",
                       "parameters": {}}],
        })
        planner = TaskPlanner(FakeProvider([malicious]), registry)
        with pytest.raises(UnknownToolError):
            planner.plan("wipe my drive")

    def test_planner_rejects_wrong_parameters(self, registry) -> None:
        bad = json.dumps({
            "intent_summary": "x", "expected_result": "y",
            "steps": [{"description": "echo", "tool_name": "echo",
                       "parameters": {"wrong_key": 1}}],
        })
        planner = TaskPlanner(FakeProvider([bad]), registry)
        # planner accepts parameters dict; the TOOL rejects unexpected kwargs
        plan = planner.plan("say something")
        orch = Orchestrator(registry)
        orch.submit(plan)
        result = orch.run(plan.task_id)
        # echo(text=...) gets unexpected kwarg -> step fails cleanly
        assert result.status == TaskStatus.FAILED

    def test_planner_rejects_non_json_output(self, registry) -> None:
        planner = TaskPlanner(FakeProvider(["I will not use JSON"]), registry)
        with pytest.raises(PlanValidationError):
            planner.plan("anything")

    def test_registry_get_unknown_tool_raises(self, registry) -> None:
        with pytest.raises(UnknownToolError):
            registry.get("nonexistent")

    def test_registry_rejects_duplicate_registration(self, registry) -> None:
        with pytest.raises(ValueError):
            registry.register(ToolSpec(
                name="echo", description="dup", handler=lambda **k: None,
                permission_level=PermissionLevel.SAFE,
            ))


# ============================================================================== timeouts + retries
class TestTimeoutsAndRetries:
    def test_hanging_tool_times_out_and_fails_after_retries(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history, max_retries=1)
        plan = make_plan([PlanStep(step_id=1, description="hang",
                                   tool_name="hanging_tool")])
        orch.submit(plan)
        start = time.time()
        result = orch.run(plan.task_id)
        elapsed = time.time() - start
        # 2 attempts x 1s timeout each = ~2s, NOT 5s+ (hang would take 5s)
        assert elapsed < 4.0, f"timeout did not bound the hang: {elapsed}s"
        assert result.status == TaskStatus.FAILED
        assert result.steps[0].attempts == 2
        assert "timeout" in (result.steps[0].error or "").lower()

    def test_retries_exhausted_records_error(self, registry) -> None:
        orch = Orchestrator(registry, max_retries=2)
        plan = make_plan([PlanStep(step_id=1, description="x",
                                   tool_name="failing_tool")])
        orch.submit(plan)
        result = orch.run(plan.task_id)
        # failing_tool raises RuntimeError (untyped) -> fails on FIRST attempt,
        # no retry (only ToolTimeoutError is retryable)
        assert result.status == TaskStatus.FAILED
        assert result.steps[0].attempts == 1


# ============================================================================== permissions + approval
class TestPermissionRestrictions:
    def test_sensitive_plan_pauses_without_auto_approver(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history)  # no approver wired
        plan = make_plan(
            [PlanStep(step_id=1, description="sensitive",
                      tool_name="sensitive_tool", parameters={"text": "boom"})],
            sensitive=True,
        )
        orch.submit(plan)
        result = orch.run(plan.task_id)
        # FAIL-SAFE: without an approver, sensitive steps NEVER execute
        assert result.status == TaskStatus.WAITING_FOR_APPROVAL
        assert result.steps == []  # nothing ran

    def test_approval_via_callback(self, registry, history) -> None:
        approvals: list = []
        orch = Orchestrator(
            registry, history=history,
            approver=lambda plan, step_id: (approvals.append(step_id) or True),
        )
        plan = make_plan(
            [PlanStep(step_id=1, description="sensitive",
                      tool_name="sensitive_tool", parameters={"text": "ok"})],
            sensitive=True,
        )
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.COMPLETED
        assert approvals == [0]  # plan-level approval recorded
        assert result.steps[0].output == "ok"

    def test_declined_approval_cancels(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history, approver=lambda p, s: False)
        plan = make_plan(
            [PlanStep(step_id=1, description="sensitive",
                      tool_name="sensitive_tool")],
            sensitive=True,
        )
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.CANCELLED
        assert result.steps == []

    def test_approve_and_resume_runs_previously_paused_task(self, registry, history) -> None:
        orch = Orchestrator(registry, history=history)  # no approver initially
        plan = make_plan(
            [PlanStep(step_id=1, description="sensitive",
                      tool_name="sensitive_tool", parameters={"text": "resumed"})],
            sensitive=True,
        )
        orch.submit(plan)
        first = orch.run(plan.task_id)
        assert first.status == TaskStatus.WAITING_FOR_APPROVAL

        # human approves -> task completes
        second = orch.approve_and_resume(plan.task_id)
        assert second.status == TaskStatus.COMPLETED
        assert second.steps[0].output == "resumed"

    def test_resume_on_non_waiting_task_is_illegal(self, registry) -> None:
        orch = Orchestrator(registry)
        plan = make_plan([PlanStep(step_id=1, description="a",
                                   tool_name="echo", parameters={"text": "x"})])
        orch.submit(plan)
        orch.run(plan.task_id)  # completes
        with pytest.raises(InvalidTransitionError):
            orch.approve_and_resume(plan.task_id)


# ============================================================================== cancellation
class TestCancellation:
    def test_cancel_before_run(self, registry) -> None:
        orch = Orchestrator(registry)
        plan = make_plan([PlanStep(step_id=1, description="a",
                                   tool_name="echo", parameters={"text": "x"})])
        orch.submit(plan)
        orch.cancel(plan.task_id)
        assert orch.status(plan.task_id) == TaskStatus.CANCELLED
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.CANCELLED

    def test_completed_task_cannot_be_cancelled(self, registry) -> None:
        orch = Orchestrator(registry)
        plan = make_plan([PlanStep(step_id=1, description="a",
                                   tool_name="echo", parameters={"text": "x"})])
        orch.submit(plan)
        orch.run(plan.task_id)
        orch.cancel(plan.task_id)  # no-op on completed
        assert orch.status(plan.task_id) == TaskStatus.COMPLETED


# ============================================================================== failure recovery
class TestFailureRecovery:
    def test_state_machine_allows_replan_after_failure(self, registry) -> None:
        orch = Orchestrator(registry)
        plan = make_plan([PlanStep(step_id=1, description="f",
                                   tool_name="failing_tool")])
        orch.submit(plan)
        result = orch.run(plan.task_id)
        assert result.status == TaskStatus.FAILED
        # FAILED -> PENDING is a legal transition (replan/retry path)
        orch._set_status(plan.task_id, TaskStatus.PENDING)
        assert orch.status(plan.task_id) == TaskStatus.PENDING

    def test_illegal_transition_detected(self, registry) -> None:
        orch = Orchestrator(registry)
        plan = make_plan([PlanStep(step_id=1, description="a",
                                   tool_name="echo", parameters={"text": "x"})])
        orch.submit(plan)
        with pytest.raises(InvalidTransitionError):
            orch._set_status(plan.task_id, TaskStatus.COMPLETED)  # PENDING -> COMPLETED illegal


# ============================================================================== history
class TestTaskHistory:
    def test_history_records_task_and_steps(self, registry, tmp_path) -> None:
        h = TaskHistory(tmp_path / "h.db")
        orch = Orchestrator(registry, history=h)
        plan = make_plan([
            PlanStep(step_id=1, description="a", tool_name="clock", parameters={}),
            PlanStep(step_id=2, description="b", tool_name="echo", parameters={"text": "done"}),
        ])
        orch.submit(plan)
        orch.run(plan.task_id)

        row = h.get_task(plan.task_id)
        assert row["status"] == "completed"
        steps = h.get_steps(plan.task_id)
        assert len(steps) == 2
        assert steps[1]["tool_name"] == "echo"
        h.close()

    def test_history_persists_across_reopen(self, registry, tmp_path) -> None:
        db = tmp_path / "persist.db"
        h1 = TaskHistory(db)
        orch = Orchestrator(registry, history=h1)
        plan = make_plan([PlanStep(step_id=1, description="a",
                                   tool_name="echo", parameters={"text": "x"})])
        orch.submit(plan)
        orch.run(plan.task_id)
        h1.close()

        h2 = TaskHistory(db)
        assert h2.get_task(plan.task_id)["status"] == "completed"
        h2.close()


# ============================================================================== planner integration
class TestPlannerIntegration:
    def test_full_pipeline_plan_to_completion(self, registry, history) -> None:
        good_plan = json.dumps({
            "intent_summary": "get time and confirm readiness",
            "expected_result": "timestamp then READY",
            "steps": [
                {"description": "get current time", "tool_name": "clock",
                 "parameters": {}},
                {"description": "echo ready", "tool_name": "echo",
                 "parameters": {"text": "READY"}},
            ],
        })
        planner = TaskPlanner(FakeProvider([good_plan]), registry)
        orch = Orchestrator(registry, history=history)

        plan = planner.plan("Get the time, then say READY")
        orch.submit(plan)
        result = orch.run(plan.task_id)

        assert result.status == TaskStatus.COMPLETED
        assert result.steps[1].output == "READY"
        assert result.verification["all_steps_completed"] is True

    def test_planner_empty_steps_is_valid_non_executable_plan(self, registry) -> None:
        no_tools = json.dumps({
            "intent_summary": "no tool can format drives",
            "expected_result": "n/a",
            "steps": [],
        })
        planner = TaskPlanner(FakeProvider([no_tools]), registry)
        plan = planner.plan("format my C drive")
        assert plan.steps == []
        assert plan.requires_approval is False

    def test_plan_step_ceiling_enforced(self, registry) -> None:
        many = json.dumps({
            "intent_summary": "x", "expected_result": "y",
            "steps": [{"description": f"step {i}", "tool_name": "echo",
                       "parameters": {"text": str(i)}} for i in range(15)],
        })
        planner = TaskPlanner(FakeProvider([many]), registry)
        with pytest.raises(PlanValidationError):
            planner.plan("do fifteen echo steps")
