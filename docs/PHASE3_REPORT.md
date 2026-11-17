# NOVA — Phase 3 Report

*Format per master instructions §8.*

## 1. What was implemented

- **Task schemas** — `TaskStatus` with all 7 required states (pending,
  planning, waiting_for_approval, running, completed, failed, cancelled) and
  a validated state machine (`VALID_TRANSITIONS`); `PlanStep`, `TaskPlan`,
  `StepResult`, `TaskResult`; typed task errors.
- **Tool registry** — `ToolSpec` declares name, description, input/output
  schema, `PermissionLevel` (SAFE / NORMAL / SENSITIVE), timeout, handler.
  Explicit registration only; duplicate registration rejected; unknown tools
  raise `UnknownToolError`. This is the allowlist boundary.
- **Task planner** — natural language → validated multi-step plan via the
  provider (replaceable, same abstract interface as Phase 2). Registry gate:
  plans referencing unregistered tools are rejected at planning time. Steps
  renumbered into strict execution order; 12-step ceiling (controlled
  execution, no autonomous loops). Empty-steps outcome is a valid
  "cannot be done with available tools" response.
- **Agent orchestrator** — sequential execution, execution state management,
  bounded retries (retryable errors only), hard per-step timeouts (tool
  handlers run in daemon threads), failure recovery (FAILED → PENDING replan
  path, `approve_and_resume()` for paused tasks), task cancellation (at step
  boundaries), and result verification (every planned step must have a
  COMPLETED result).
- **Human approval** — sensitive tools pause the task in
  WAITING_FOR_APPROVAL. Without a wired approver callback the task simply
  stops — fail-safe default; nothing sensitive ever auto-executes.
  `approve_and_resume()` completes the human loop.
- **Task history** — SQLite ledger of every task and every step result
  (status, output, error, attempts, timestamps).
- **Built-in tools** — only `echo` and `clock` (safe, deterministic), per the
  phase rule: no real desktop/browser tools connected until the orchestrator
  passes its tests.

## 2. Files created / modified

| File | Purpose |
|---|---|
| `local_agent/tasks/schemas.py` | statuses, plans, results, typed errors |
| `local_agent/tasks/registry.py` | ToolSpec + ToolRegistry allowlist |
| `local_agent/tasks/planner.py` | NL → validated plan |
| `local_agent/tasks/orchestrator.py` | the execution engine |
| `local_agent/tasks/history.py` | SQLite task ledger |
| `local_agent/tasks/builtin_tools.py` | echo + clock (safe only) |
| `local_agent/tasks/__init__.py` | subpackage |
| `tests/test_orchestrator.py` | full Phase 3 suite |
| `scripts/verify_orchestrator.py` | live pipeline check (real Ollama) |
| `docs/PHASE3_REPORT.md` | this report |

## 3. Dependencies installed

**None added.** Phase 3 uses only stdlib (threading, sqlite3, json, signal)
plus pydantic/httpx already present. Intentional: the orchestrator must stay
lightweight (8 GB RAM machine) and dependency-light (audit surface).

## 4. Tests performed (assistant side)

- Simple single-step and multi-step tasks (order verified).
- Execution stops at first failure; later steps never run.
- Result verification (`all_steps_completed`) cross-checked.
- Invalid tool calls: unknown tool in plan → `UnknownToolError` at planning;
  wrong parameters → clean step failure; non-JSON planner output →
  `PlanValidationError`; duplicate tool registration rejected.
- Timeouts: hanging tool bounded by its timeout; with retries the whole step
  fails in bounded time (elapsed-time asserted).
- Failures: untyped tool errors fail fast without retry (only timeouts retry).
- Cancellation: pre-run cancel lands in CANCELLED; completed tasks are immune.
- Permission restrictions: sensitive plan pauses without an approver (steps
  never run); approver callback approves/declines; `approve_and_resume()`
  resumes paused tasks; resuming a non-waiting task is illegal.
- Failure recovery: FAILED → PENDING replan transition works; illegal
  transitions raise.
- History: tasks + steps recorded; persists across reopen.
- Planner integration: full NL → plan → execute → verify pipeline; 15-step
  plan rejected by the ceiling; "cannot be done" plans are valid and
  non-executable.

## 5. Test results

**Pending your local run** (`pytest tests/test_orchestrator.py` and the
`scripts\verify_orchestrator.py` live check). Per master rule 14, Phase 3 is
not declared working until you paste green output.

## 6. Known issues

- The orchestrator is single-task-oriented: concurrent `run()` calls on the
  same task are not guarded (fine for Phase 3's one-user-one-assistant model;
  revisit in Phase 7 with the backend).
- Tool handlers that block the GIL (rare, e.g. heavy C extensions) could
  delay cancellation slightly; step-boundary cancellation is the guarantee,
  not instant thread kill.
- The planner trusts the model's step descriptions but validates everything
  structural; a 3B model may produce clumsy-but-valid plans more often than
  wrong-but-invalid ones.

## 7. Security considerations

- Allowlist boundary: the orchestrator can ONLY run registry tools; no string
  evaluation, no dynamic imports, no shell.
- Plans referencing unregistered tools are rejected at PLANNING time —
  prompt-injection through model output cannot introduce new capabilities.
- Sensitive tools always pause for approval; with no approver wired, the
  fail-safe is "do not execute."
- Permission failures are hard, non-retryable stops.
- Every task and step outcome lands in the SQLite history (audit trail).
- Timeouts bound all tool execution; daemon threads cannot hang the process.

## 8. Documentation

This report + docstrings throughout the tasks layer. README roadmap updated.

## 9. Git checkpoint recommendation

After your local run is green:
```
git tag -a v0.3.0-phase3 -m "Phase 3: orchestrator, planner, registry, history"
```

## 10. Readiness assessment for Phase 4 (Safe Tools)

**Ready.** The registry's `ToolSpec` contract is exactly what Phase 4's real
tools (files in approved dirs, web search, terminal allowlist) will
implement. The orchestrator, approval gate, and audit history need zero
changes to accept them — registration is the only integration step. The
permission system (SAFE/NORMAL/SENSITIVE) is already wired for their
permission levels.
