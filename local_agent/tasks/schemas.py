# ==============================================================================
# NOVA — Task Execution Schemas (Phase 3)
# ------------------------------------------------------------------------------
# The validated data contract for everything the orchestrator does.
# Model output enters this layer ONLY through the planner's Pydantic
# validation — nothing executes unless it parses into these types.
# ==============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- statuses
class TaskStatus(str, Enum):
    """The 7 master-required task lifecycle states."""
    PENDING = "pending"                        # received, not yet planned
    PLANNING = "planning"                      # planner running
    WAITING_FOR_APPROVAL = "waiting_for_approval"  # paused — needs user consent
    RUNNING = "running"                        # executing a step
    COMPLETED = "completed"                    # all steps done, verified
    FAILED = "failed"                          # a step failed irrecoverably
    CANCELLED = "cancelled"                    # user stopped the task


# Allowed lifecycle transitions — enforced by the orchestrator (no skipping).
VALID_TRANSITIONS: Dict[TaskStatus, frozenset] = {
    TaskStatus.PENDING: frozenset({TaskStatus.PLANNING, TaskStatus.CANCELLED}),
    TaskStatus.PLANNING: frozenset({
        TaskStatus.PENDING,  # planning failed -> replanable
        TaskStatus.RUNNING,  # plan approved or safe -> execute
        TaskStatus.WAITING_FOR_APPROVAL,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.WAITING_FOR_APPROVAL: frozenset({
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.RUNNING: frozenset({
        TaskStatus.WAITING_FOR_APPROVAL,  # next step needs confirmation
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.PENDING}),  # allow retry/replan
    TaskStatus.CANCELLED: frozenset({TaskStatus.PENDING}),
}


# --------------------------------------------------------------------------- plan
class PlanStep(BaseModel):
    """One step in a validated plan.

    Security-critical fields:
      * tool_name MUST exist in the ToolRegistry (planner validates).
      * sensitive steps ALWAYS pause for approval (permission level decides).
    """
    model_config = {"extra": "forbid"}

    step_id: int = Field(..., ge=1, description="1-based execution order")
    description: str = Field(..., description="Human-readable step description")
    tool_name: str = Field(..., description="Registered tool to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("description")
    @classmethod
    def _desc_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("step description must not be empty")
        return v.strip()


class TaskPlan(BaseModel):
    """A full, validated plan for one user request."""
    model_config = {"extra": "forbid"}

    task_id: str
    user_request: str
    intent_summary: str = Field(..., description="What the user wants, plainly")
    expected_result: str = Field(..., description="Success state, plainly")
    steps: List[PlanStep] = Field(default_factory=list)
    requires_approval: bool = Field(
        ..., description="True if ANY step is permission-gated"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("intent_summary", "expected_result", "user_request")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    def sorted_steps(self) -> List[PlanStep]:
        return sorted(self.steps, key=lambda s: s.step_id)


# --------------------------------------------------------------------------- results
class StepResult(BaseModel):
    """Outcome of one step execution. Data only — never instructions."""
    model_config = {"extra": "forbid"}

    step_id: int
    tool_name: str
    status: TaskStatus = Field(..., description="completed | failed | cancelled")
    output: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = Field(default=1, ge=1)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None


class TaskResult(BaseModel):
    """Final outcome of a task run."""
    model_config = {"extra": "forbid"}

    task_id: str
    status: TaskStatus
    steps: List[StepResult] = Field(default_factory=list)
    summary: Optional[str] = None
    error: Optional[str] = None
    verification: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------- errors
class TaskError(Exception):
    """Base for orchestration failures — never a bare Exception."""


class UnknownToolError(TaskError):
    """Plan referenced a tool that is not registered."""


class PermissionDeniedError(TaskError):
    """Tool exists, but its permission level forbids this execution."""


class ToolTimeoutError(TaskError):
    """Tool exceeded its configured timeout."""


class InvalidTransitionError(TaskError):
    """Attempted an illegal task-status transition."""


class PlanValidationError(TaskError):
    """The model's proposed plan failed schema or registry validation."""


class TaskCancelledError(TaskError):
    """Task was cancelled mid-execution."""
