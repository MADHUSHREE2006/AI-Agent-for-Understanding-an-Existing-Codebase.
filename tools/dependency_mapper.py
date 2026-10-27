"""Dependency mapping tool.

Builds a graph of how the files in a project depend on one another. For
Python it reads imports via :mod:`ast` and resolves them to *local* files so
the agent can describe the actual wiring of the codebase, not just bare
``import`` statements. The structured result is reused by the report generator.
"""

from __future__ import annotations

import ast
import os
from typing import Any, Dict, List, Set

from config import Config
from .code_parser import parse_file_structure

_cfg = Config()


def _norm(p: str) -> str:
    return os.path.normpath(p)


def _module_to_path(root: str, module: str) -> List[str]:
    """Convert a dotted module name to candidate local file paths."""
    parts = module.replace(".", "/").lstrip(".")
    candidates = [parts + ".py", os.path.join(parts, "__init__.py")]
    return [os.path.join(root, c) for c in candidates]


def _collect_py_modules(root: str) -> Dict[str, str]:
    """Map dotted module names -> file path for every .py file under root."""
    mapping: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _cfg.ignore_dirs and not d.startswith(".")
        ]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            dotted = rel[:-3].replace("/", ".")
            if dotted.endswith(".__init__"):
                dotted = dotted[:-9]  # package root
            mapping[dotted] = rel
    return mapping


def map_dependencies(path: str) -> Dict[str, Any]:
    """Return a dependency graph for the project at ``path``.

    Keys:
    * ``files``: all analyzed Python files (relative paths).
    * ``edges``: list of ``{from, to, line, module}`` resolved to local files.
    * ``adjacency``: ``{file: [files it depends on]}`` for quick rendering.
    * ``external_imports``: non-local libraries used (third-party deps).
    """
    path = _norm(path)
    if not os.path.isdir(path):
        return {"error": f"'{path}' is not a directory."}

    py_modules = _collect_py_modules(path)
    files = sorted(set(py_modules.values()))
    edges: List[Dict[str, Any]] = []
    external: Set[str] = set()
    adjacency: Dict[str, List[str]] = {f: [] for f in files}

    def _file_package(rel: str) -> str:
        """Dotted package of a file relative to root.

        e.g. ``library`` for ``library/library.py``, ``""`` for top-level ``main.py``.
        """
        d = os.path.dirname(rel).replace("\\", "/")
        return d.replace("/", ".") if d else ""

    for rel in files:
        full = os.path.join(path, rel)
        struct = parse_file_structure(full)
        pkg = _file_package(rel)
        for imp in struct.get("imports", []):
            module = imp["module"]          # bare module name (no leading dots)
            level = imp.get("level", 0)
            kind = imp["kind"]

            # Resolve the import's full dotted name, handling relative imports.
            if kind == "from" and level > 0:
                base_parts = pkg.split(".") if pkg else []
                drop = level - 1
                if drop >= len(base_parts):
                    full_mod = module  # cannot anchor; treat as external later
                else:
                    base = ".".join(base_parts[: len(base_parts) - drop])
                    full_mod = f"{base}.{module}" if module and base else (module or base)
            else:
                full_mod = module
            if not full_mod:
                continue

            # try to resolve to a local file on disk
            resolved = None
            for cand in _module_to_path(path, full_mod):
                if os.path.isfile(cand):
                    resolved = os.path.relpath(cand, path).replace("\\", "/")
                    break
            if resolved is None and full_mod in py_modules:
                resolved = py_modules[full_mod]

            if resolved and resolved != rel:
                edges.append(
                    {"from": rel, "to": resolved, "line": imp["line"], "module": full_mod}
                )
                if resolved not in adjacency[rel]:
                    adjacency[rel].append(resolved)
            elif resolved is None:
                # not local -> external / third-party library
                external.add(full_mod.split(".")[0])

    return {
        "files": files,
        "edges": edges,
        "adjacency": adjacency,
        "external_imports": sorted(external),
    }


# ------------------------------------------------------------------
# Tool wrapper (string output for the agent)
# ------------------------------------------------------------------
def _tool(path: str) -> str:
    data = map_dependencies(path)
    if "error" in data:
        return f"DEPENDENCY MAP ERROR: {data['error']}"
    lines = [f"DEPENDENCY MAP (root={path})"]
    lines.append(f"Python files analyzed: {len(data['files'])}")
    if data["edges"]:
        lines.append("Internal dependencies (file -> local file):")
        for e in data["edges"][:40]:
            lines.append(f"  {e['from']} -> {e['to']}  (import '{e['module']}' @L{e['line']})")
        if len(data["edges"]) > 40:
            lines.append(f"  ... and {len(data['edges']) - 40} more")
    else:
        lines.append("No internal (cross-file) dependencies detected.")
    if data["external_imports"]:
        lines.append("External/third-party libraries: " + ", ".join(data["external_imports"]))
    return "\n".join(lines)


TOOL_SPECS = [
    {
        "name": "map_dependencies",
        "description": "Map how files in a project import/depend on each other plus external libraries. Best for understanding architecture and wiring.",
        "parameters": {"path": "string (project root)"},
        "func": _tool,
    },
]
