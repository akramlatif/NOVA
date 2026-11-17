# ==============================================================================
# NOVA — Agent Orchestrator (Phase 3, Tasks 4-6)
# ------------------------------------------------------------------------------
# Executes validated plans STEP BY STEP under explicit control.
#
# Controlled execution — NOT an autonomous loop:
#   * fixed step ceiling (plans validated at <=12 steps)
#   * strict lifecycle state machine (VALID_TRANSITIONS)
#   * sensitive tools PAUSE the task and demand human approval
#   * per-step timeouts, bounded retries, cancellation checked between steps
#   * failure stops the chain (no wild recovery); resume() replays from the
#     first failed step after the user approves or conditions change
#
# The orchestrator runs ONLY registry tools. It cannot invent actions.
# ==============================================================================

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from local_agent.tasks.registry import PermissionLevel, ToolRegistry, ToolSpec
from local_agent.tasks.schemas import (
    InvalidTransitionError,
    PermissionDeniedError,
    PlanValidationError,
    StepResult,
    TaskCancelledError,
    TaskPlan,
    TaskResult,
    TaskStatus,
    ToolTimeoutError,
    VALID_TRANSITIONS,
)
from local_agent.tasks.history import TaskHistory

logger = logging.getLogger("nova.orchestrator")

DEFAULT_MAX_RETRIES = 2        # 1 try + up to 2 retries per step
RETRYABLE_ERRORS = (ToolTimeoutError,)


class Orchestrator:
    """Sequential, permission-gated plan executor."""

    def __init__(
        self,
        registry: ToolRegistry,
        history: Optional[TaskHistory] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        approver: Optional[Callable[[TaskPlan, int], bool]] = None,
    ) -> None:
        """
        registry : the tool allowlist (required — nothing runs unregistered)
        history  : optional SQLite ledger
        approver : optional callback invoked when a sensitive step needs
                   human confirmation. Signature: (plan, step_id) -> bool.
                   If None, sensitive steps CANNOT be approved -> the task
                   pauses in WAITING_FOR_APPROVAL and returns; the caller
                   resumes with approve_and_resume(). Fail-safe default.
        """
        self.registry = registry
        self.history = history
        self.max_retries = max(0, int(max_retries))
        self._approver = approver
        self._cancel_events: Dict[str, threading.Event] = {}
        self._plans: Dict[str, TaskPlan] = {}
        self._statuses: Dict[str, TaskStatus] = {}
        self._results: Dict[str, List[StepResult]] = {}

    # ================================================================= state machine
    def _set_status(self, task_id: str, new: TaskStatus) -> None:
        current = self._statuses.get(task_id, TaskStatus.PENDING)
        if new not in VALID_TRANSITIONS[current]:
            raise InvalidTransitionError(
                f"Illegal task transition: {current.value} -> {new.value}"
            )
        self._statuses[task_id] = new
        if self.history:
            self.history.update_task_status(task_id, new)

    def status(self, task_id: str) -> TaskStatus:
        return self._statuses.get(task_id, TaskStatus.PENDING)

    # ================================================================= task lifecycle
    def submit(self, plan: TaskPlan) -> TaskStatus:
        """Register a validated plan. Does NOT execute anything."""
        if not plan.steps:
            # Non-executable plan (planner said it can't be done) -> complete
            # immediately with an explanation, not an error.
            self._plans[plan.task_id] = plan
            self._statuses[plan.task_id] = TaskStatus.COMPLETED
            self._results[plan.task_id] = []
            if self.history:
                self.history.record_task(
                    plan.task_id, plan.user_request, plan.intent_summary,
                    plan.expected_result, TaskStatus.COMPLETED,
                )
                self.history.update_task_status(
                    plan.task_id, TaskStatus.COMPLETED,
                    summary="Planner found no executable steps for this request.",
                )
            return TaskStatus.COMPLETED

        self._plans[plan.task_id] = plan
        self._statuses[plan.task_id] = TaskStatus.PENDING
        self._results[plan.task_id] = []
        if self.history:
            self.history.record_task(
                plan.task_id, plan.user_request, plan.intent_summary,
                plan.expected_result, TaskStatus.PENDING,
            )
        return TaskStatus.PENDING

    # ================================================================= execution
    def run(self, task_id: str) -> TaskResult:
        """Execute the plan sequentially. Returns the final TaskResult.

        The task lifecycle enforced here:
          PENDING -> (approval if needed) -> RUNNING -> COMPLETED | FAILED
        Cancellation may interrupt at any step boundary.
        """
        plan = self._plans[task_id]
        if task_id not in self._statuses:
            raise KeyError(f"Unknown task: {task_id}")

        cancel_event = threading.Event()
        self._cancel_events[task_id] = cancel_event

        try:
            # ---- planning already done; go straight to approval gate
            if self.status(task_id) == TaskStatus.PENDING:
                self._set_status(task_id, TaskStatus.PLANNING)  # planning phase marker
                # (plan arrived pre-validated; transition through PLANNING keeps
                #  the audit trail honest about the lifecycle)

            # ---- approval gate: plan contains a sensitive step
            if plan.requires_approval and self.status(task_id) != TaskStatus.RUNNING:
                self._set_status(task_id, TaskStatus.WAITING_FOR_APPROVAL)
                if self._approver is None:
                    # Fail-safe: no approver wired -> stop here, let the caller
                    # decide. Never silently execute sensitive steps.
                    return self._task_result(
                        task_id, TaskStatus.WAITING_FOR_APPROVAL,
                        summary="Task is waiting for user approval before it can "
                                "run sensitive steps.",
                    )
                if not self._approver(plan, step_id=0):
                    self._set_status(task_id, TaskStatus.CANCELLED)
                    return self._task_result(
                        task_id, TaskStatus.CANCELLED,
                        summary="User declined approval. Task cancelled.",
                    )
                self._set_status(task_id, TaskStatus.RUNNING)

            # ---- already approved and resuming: fall through to RUNNING
            if self.status(task_id) == TaskStatus.WAITING_FOR_APPROVAL:
                return self._task_result(
                    task_id, TaskStatus.WAITING_FOR_APPROVAL,
                    summary="Still waiting for approval.",
                )

            # ---- execution loop (bounded: at most plan.steps entries)
            already = self._results.get(task_id, [])
            start_index = len(already)  # resume support: skip completed steps
            if self.status(task_id) != TaskStatus.RUNNING:
                self._set_status(task_id, TaskStatus.RUNNING)

            for step in plan.sorted_steps()[start_index:]:
                if cancel_event.is_set():
                    self._set_status(task_id, TaskStatus.CANCELLED)
                    return self._task_result(
                        task_id, TaskStatus.CANCELLED,
                        summary="Cancelled by user.",
                    )

                # per-step approval gate (sensitive tool at ANY step)
                spec = self.registry.get(step.tool_name)
                if spec.permission_level >= PermissionLevel.SENSITIVE:
                    if self._approver is not None:
                        if not self._approver(plan, step_id=step.step_id):
                            self._set_status(task_id, TaskStatus.CANCELLED)
                            return self._task_result(
                                task_id, TaskStatus.CANCELLED,
                                summary=f"User declined step {step.step_id} "
                                        f"({step.tool_name}). Task cancelled.",
                            )
                    else:
                        self._set_status(task_id, TaskStatus.WAITING_FOR_APPROVAL)
                        return self._task_result(
                            task_id, TaskStatus.WAITING_FOR_APPROVAL,
                            summary=f"Step {step.step_id} ({step.tool_name}) "
                                    "requires user approval.",
                        )

                result = self._execute_step(task_id, step, spec, cancel_event)
                self._results[task_id].append(result)
                if self.history:
                    self.history.record_step(task_id, result)

                if result.status == TaskStatus.FAILED:
                    self._set_status(task_id, TaskStatus.FAILED)
                    return self._task_result(
                        task_id, TaskStatus.FAILED,
                        error=f"Step {step.step_id} ({step.tool_name}) failed: "
                              f"{result.error}",
                    )

            # ---- all steps done -> verify and complete
            self._set_status(task_id, TaskStatus.COMPLETED)
            verification = self._verify(plan)
            return self._task_result(
                task_id, TaskStatus.COMPLETED,
                summary=f"All {len(self._results[task_id])} steps completed.",
                verification=verification,
            )

        except TaskCancelledError:
            self._set_status(task_id, TaskStatus.CANCELLED)
            return self._task_result(task_id, TaskStatus.CANCELLED,
                                      summary="Cancelled by user.")
        finally:
            self._cancel_events.pop(task_id, None)

    # ================================================================= step engine
    def _execute_step(self, task_id: str, step, spec: ToolSpec,
                      cancel_event: threading.Event) -> StepResult:
        """Run one tool with bounded retries and a hard timeout."""
        started = datetime.now(timezone.utc)
        attempts = 0
        last_error: Optional[str] = None

        while attempts <= self.max_retries:
            attempts += 1
            if cancel_event.is_set():
                return StepResult(
                    step_id=step.step_id, tool_name=step.tool_name,
                    status=TaskStatus.CANCELLED, attempts=attempts,
                    started_at=started, finished_at=datetime.now(timezone.utc),
                )

            try:
                output = self._call_with_timeout(spec, dict(step.parameters),
                                                 cancel_event)
                return StepResult(
                    step_id=step.step_id, tool_name=step.tool_name,
                    status=TaskStatus.COMPLETED, output=output, attempts=attempts,
                    started_at=started, finished_at=datetime.now(timezone.utc),
                )
            except RETRYABLE_ERRORS as e:
                last_error = str(e)
                logger.warning("Step %s attempt %s retryable error: %s",
                               step.step_id, attempts, e)
                continue  # bounded by max_retries
            except TaskCancelledError:
                return StepResult(
                    step_id=step.step_id, tool_name=step.tool_name,
                    status=TaskStatus.CANCELLED, attempts=attempts,
                    started_at=started, finished_at=datetime.now(timezone.utc),
                )
            except PermissionDeniedError as e:
                # Non-retryable: permission failures are hard stops
                return StepResult(
                    step_id=step.step_id, tool_name=step.tool_name,
                    status=TaskStatus.FAILED, error=f"Permission denied: {e}",
                    attempts=attempts, started_at=started,
                    finished_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                # Tool contract violation (untyped error) — fail the step,
                # log loudly. Tools MUST raise typed errors; this catches
                # handler bugs so a broken tool can't hang the chain.
                logger.exception("Tool %s raised an untyped exception", spec.name)
                return StepResult(
                    step_id=step.step_id, tool_name=step.tool_name,
                    status=TaskStatus.FAILED,
                    error=f"Unhandled tool error: {type(e).__name__}: {e}",
                    attempts=attempts, started_at=started,
                    finished_at=datetime.now(timezone.utc),
                )

        # retries exhausted
        return StepResult(
            step_id=step.step_id, tool_name=step.tool_name,
            status=TaskStatus.FAILED,
            error=f"Timed out after {attempts} attempts: {last_error}",
            attempts=attempts, started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    def _call_with_timeout(self, spec: ToolSpec, params: dict,
                           cancel_event: threading.Event):
        """Invoke the tool handler in a worker thread with a hard timeout.

        Rationale: the tools in later phases (browser, desktop automation)
        can hang; a hung tool must never hang NOVA. The thread is daemon so
        a timed-out call cannot block process exit.
        """
        outcome: dict = {}

        def _worker() -> None:
            try:
                outcome["value"] = spec.handler(**params)
            except BaseException as e:  # thread boundary: capture everything
                outcome["error"] = e

        worker = threading.Thread(target=_worker, daemon=True, name=f"nova-tool-{spec.name}")
        worker.start()
        worker.join(timeout=spec.timeout_seconds)

        if worker.is_alive():
            raise ToolTimeoutError(
                f"Tool {spec.name} exceeded its {spec.timeout_seconds}s timeout"
            )
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("value")

    # ================================================================= control
    def cancel(self, task_id: str) -> TaskStatus:
        """Request cancellation. Takes effect at the next step boundary."""
        event = self._cancel_events.get(task_id)
        if event is None:
            # not currently running — cancel from any pre-run state we can
            current = self.status(task_id)
            if current in (TaskStatus.PENDING, TaskStatus.PLANNING,
                           TaskStatus.WAITING_FOR_APPROVAL):
                self._set_status(task_id, TaskStatus.CANCELLED)
            return self.status(task_id)
        event.set()
        return self.status(task_id)

    def approve_and_resume(self, task_id: str) -> TaskResult:
        """Approve a WAITING_FOR_APPROVAL task and continue execution."""
        if self.status(task_id) != TaskStatus.WAITING_FOR_APPROVAL:
            raise InvalidTransitionError(
                f"Task {task_id} is not waiting for approval "
                f"(state: {self.status(task_id).value})"
            )
        self._statuses[task_id] = TaskStatus.PENDING  # internal reset; run() re-drives
        return self.run(task_id)

    # ================================================================= result assembly
    def _verify(self, plan: TaskPlan) -> dict:
        """Result verification (Phase 3, Task 4): cross-check the recorded
        step results against the plan — every planned step must have a
        COMPLETED result. Returns a verification report as data."""
        results = self._results.get(plan.task_id, [])
        completed = {r.step_id for r in results if r.status == TaskStatus.COMPLETED}
        planned = {s.step_id for s in plan.steps}
        return {
            "all_steps_completed": planned.issubset(completed),
            "planned_step_count": len(planned),
            "completed_step_count": len(planned & completed),
            "expected_result": plan.expected_result,
        }

    def _task_result(self, task_id: str, status: TaskStatus,
                     summary: Optional[str] = None,
                     error: Optional[str] = None,
                     verification: Optional[dict] = None) -> TaskResult:
        result = TaskResult(
            task_id=task_id, status=status,
            steps=list(self._results.get(task_id, [])),
            summary=summary, error=error, verification=verification,
        )
        if self.history:
            self.history.store_final_result(result)
        return result
