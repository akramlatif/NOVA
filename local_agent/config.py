# ==============================================================================
# NOVA — Configuration Loader (Phase 2)
# ------------------------------------------------------------------------------
# Loads settings from .env (via python-dotenv). Single source of truth for
# the model name, host, and paths. NOTHING in NOVA hardcodes the model.
#
# Values may also be overridden by real environment variables (standard
# dotenv behavior: real env vars win over .env file values).
# ==============================================================================

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from local_agent.llm.provider import ProviderConfig


@dataclass(frozen=True)
class NovaConfig:
    """Immutable runtime configuration for the local AI brain."""
    llm: ProviderConfig
    data_dir: Path
    logs_dir: Path


def load_config(project_root: Path | None = None) -> NovaConfig:
    """Read .env (if present) and environment variables into NovaConfig.

    Defaults are hardware-appropriate (llama3.2:3b on localhost Ollama),
    so NOVA works out of the box after `ollama pull llama3.2:3b`.
    """
    root = project_root or Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    model_name = os.getenv("NOVA_LLM_MODEL", "llama3.2:3b")
    host = os.getenv("NOVA_OLLAMA_HOST", "http://127.0.0.1:11434")
    timeout = float(os.getenv("NOVA_LLM_TIMEOUT_SECONDS", "120"))
    data_dir = Path(os.getenv("NOVA_DATA_DIR", str(root / "data")))
    logs_dir = Path(os.getenv("NOVA_LOGS_DIR", str(root / "logs")))

    return NovaConfig(
        llm=ProviderConfig(
            model_name=model_name,
            host=host,
            timeout_seconds=timeout,
        ),
        data_dir=data_dir,
        logs_dir=logs_dir,
    )
