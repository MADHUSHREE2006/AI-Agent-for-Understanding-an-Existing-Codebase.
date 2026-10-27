"""Agent tools package.

Each tool module exposes:

* a structured implementation function (used by the report generator), and
* a ``TOOL_SPECS`` entry (name, description, parameters, ``func``) used by the
  agent to advertise tools in its prompt and to dispatch calls.

This module aggregates every tool into :data:`TOOL_REGISTRY` and provides
:func:`dispatch` so the agent core can stay backend-agnostic.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from config import Config
from .file_explorer import TOOL_SPECS as _file_specs
from .code_parser import TOOL_SPECS as _parser_specs
from .dependency_mapper import TOOL_SPECS as _dep_specs
from .search import TOOL_SPECS as _search_specs


def build_registry(config: Config) -> Dict[str, Dict[str, Any]]:
    """Return a name -> tool-spec mapping, binding the config to each tool."""
    registry: Dict[str, Dict[str, Any]] = {}
    for spec in (_file_specs + _parser_specs + _dep_specs + _search_specs):
        registry[spec["name"]] = spec
    return registry


def tool_descriptions(registry: Dict[str, Dict[str, Any]]) -> str:
    """Render the available tools as text for the agent system prompt."""
    lines: List[str] = []
    for name, spec in registry.items():
        params = ", ".join(
            f'{pname}: {ptype}' for pname, ptype in spec["parameters"].items()
        )
        lines.append(f"- {name}({params}): {spec['description']}")
    return "\n".join(lines)


def dispatch(registry: Dict[str, Dict[str, Any]], name: str, args: Any) -> str:
    """Execute a tool by name, returning its string output for the agent.

    ``args`` may be a dict already, or a JSON string produced by the LLM.
    Tools are defensive: they return an error string rather than raising, so
    a single bad tool call never crashes the agentic loop.
    """
    spec = registry.get(name)
    if spec is None:
        return f"Error: unknown tool '{name}'. Available: {list(registry)}"
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError as exc:
            return f"Error: could not parse Action Input as JSON: {exc}"
    if not isinstance(args, dict):
        return f"Error: Action Input must be a JSON object, got {type(args).__name__}."
    try:
        return spec["func"](**args)
    except TypeError as exc:
        return f"Error calling tool '{name}': {exc}"
    except Exception as exc:  # noqa: BLE001 - tools must not crash the loop
        return f"Error: tool '{name}' failed: {exc}"
