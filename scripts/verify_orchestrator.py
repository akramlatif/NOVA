# ==============================================================================
# NOVA — Phase 3 End-to-End Verification (run on YOUR machine)
# ------------------------------------------------------------------------------
# Proves the full pipeline works with the REAL local Ollama model:
#     user request -> planner (real LLM) -> validated plan -> orchestrator
#     -> echo/clock tools (safe) -> task result -> SQLite history
#
# Prerequisite: Ollama running + model pulled (llama3.2:3b).
# Usage (PowerShell, from D:\NOVA, venv active):
#     python scripts\verify_orchestrator.py
# ==============================================================================

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_agent.config import load_config
from local_agent.llm.ollama_provider import OllamaProvider
from local_agent.tasks.builtin_tools import register_builtin_tools
from local_agent.tasks.history import TaskHistory
from local_agent.tasks.orchestrator import Orchestrator
from local_agent.tasks.planner import TaskPlanner
from local_agent.tasks.registry import ToolRegistry
from local_agent.tasks.schemas import TaskStatus


def main() -> int:
    print("=" * 66)
    print("NOVA — Phase 3 Live Verification (real Ollama + orchestrator)")
    print("=" * 66)

    cfg = load_config()
    provider = OllamaProvider(cfg.llm)
    if not provider.is_available():
        print("[FAIL] Ollama or the model is unavailable. Fix and retry.")
        return 1
    print(f"[OK] Ollama ready with {cfg.llm.model_name}")

    registry = ToolRegistry()
    register_builtin_tools(registry)
    print(f"[OK] Tools registered: {registry.names()}")

    history = TaskHistory(cfg.data_dir / "tasks.db")
    planner = TaskPlanner(provider, registry)
    orch = Orchestrator(registry, history=history)
    print("[OK] Planner + orchestrator wired (no auto-approver -> sensitive "
          "steps pause safely).")

    all_passed = True

    # ---- 1. plan a simple two-step request
    print("\n[1/3] Planning: 'Get the current time, then echo the word READY.'")
    try:
        plan = planner.plan("Get the current time, then echo the word READY.")
    except Exception as e:
        print(f"  [FAIL] Planner error: {e}")
        return 1
    print(f"  intent: {plan.intent_summary}")
    print(f"  steps : {[(s.step_id, s.tool_name) for s in plan.sorted_steps()]}")
    if not plan.steps:
        print("  [WARN] Model proposed no steps — 3B models can be shy. Re-run.")
        all_passed = False
    else:
        # ---- 2. execute it
        status = orch.submit(plan)
        result = orch.run(plan.task_id)
        print(f"  status: {result.status.value}")
        for s in result.steps:
            print(f"    step {s.step_id} ({s.tool_name}) -> {s.status.value}")
        if result.status == TaskStatus.COMPLETED and result.verification:
            ok = result.verification["all_steps_completed"]
            print(f"  verification all_steps_completed={ok}")
            all_passed = all_passed and ok
        else:
            all_passed = False

    # ---- 3. history persistence
    print("\n[3/3] Checking task history persistence...")
    recent = history.list_recent_tasks(5)
    print(f"  tasks recorded: {len(recent)}")
    for t in recent:
        print(f"    {t['id'][:8]}... {t['status']}: {t['user_request'][:60]}")
    all_passed = all_passed and len(recent) >= 1

    history.close()
    print("-" * 66)
    if all_passed:
        print("RESULT: Phase 3 live verification PASSED.")
        return 0
    print("RESULT: See [FAIL]/[WARN] lines above — needs investigation.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
