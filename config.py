"""Central configuration for the Codebase Understanding Agent.

All settings can be overridden via environment variables, which makes the
agent runnable in three modes:

1. ``ollama``  - locally running LLM through Ollama (preferred, offline-capable).
2. ``openai``  - any OpenAI-compatible API endpoint (OpenAI, Groq, LM Studio, ...).
3. ``simulate`` - no LLM required; uses scripted responses so the agentic
   workflow can be demonstrated anywhere (great for viva demos).

The default backend is ``ollama`` because the brief asks us to prefer locally
running LLMs wherever the hardware supports them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _env(name: str, default: str) -> str:
    """Return an environment variable or its default, stripped of whitespace."""
    val = os.environ.get(name)
    return val.strip() if val and val.strip() else default


@dataclass
class Config:
    """Runtime configuration for the agent."""

    # --- LLM backend -------------------------------------------------------
    # One of: "ollama" | "openai" | "simulate"
    backend: str = field(default_factory=lambda: _env("CBU_BACKEND", "ollama"))

    # Ollama settings (local)
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("CBU_OLLAMA_MODEL", "qwen2.5-coder:7b"))

    # OpenAI-compatible settings (online fallback)
    openai_base_url: str = field(
        default_factory=lambda: _env("CBU_OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: _env("CBU_OPENAI_MODEL", "gpt-4o-mini"))

    # --- Agent behaviour ---------------------------------------------------
    max_iterations: int = field(default_factory=lambda: int(_env("CBU_MAX_ITERATIONS", "15")))
    # Maximum characters of a single file the tools will surface to the LLM,
    # keeping the context window of small local models under control.
    max_file_chars: int = field(default_factory=lambda: int(_env("CBU_MAX_FILE_CHARS", "12000")))
    # How many lines of code context to show around a referenced symbol.
    context_lines: int = field(default_factory=lambda: int(_env("CBU_CONTEXT_LINES", "6")))

    # --- Exploration filters ----------------------------------------------
    # Directories that are almost never useful to explain.
    ignore_dirs: tuple = (
        ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
        "env", ".idea", ".vscode", "dist", "build", ".next", "target",
        ".mypy_cache", ".pytest_cache", "coverage", ".tox", "site-packages",
    )
    # File extensions we know how to parse structurally (Python gets full AST).
    supported_extensions: tuple = (
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".go", ".rb",
        ".php", ".c", ".cpp", ".h", ".hpp",
    )

    # --- Output ------------------------------------------------------------
    output_dir: str = field(default_factory=lambda: _env("CBU_OUTPUT_DIR", "output_reports"))

    # --- Misc --------------------------------------------------------------
    request_timeout: float = field(default_factory=lambda: float(_env("CBU_TIMEOUT", "120")))
    temperature: float = field(default_factory=lambda: float(_env("CBU_TEMPERATURE", "0.2")))


def get_config() -> Config:
    """Build a :class:`Config` from the current environment."""
    return Config()


def is_ignored(path: str, ignore_dirs: tuple) -> bool:
    """True if any path component is in the ignore list (used by tools)."""
    parts = path.replace("\\", "/").split("/")
    return any(part in ignore_dirs for part in parts)
