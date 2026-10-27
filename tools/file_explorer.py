"""File-system exploration tools.

These tools give the agent its "eyes": listing directories, rendering a tree,
finding files by name, and reading file contents. They respect the configured
ignore list so the agent never wastes turns exploring ``node_modules`` or
``__pycache__``.
"""

from __future__ import annotations

import fnmatch
import os
from typing import List

from config import Config

_cfg = Config()


def _norm(p: str) -> str:
    return os.path.normpath(p)


def _is_ignored(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return any(part in _cfg.ignore_dirs for part in parts)


def _walk(root: str) -> List[str]:
    """Yield relative file paths under ``root`` that are not ignored."""
    root = _norm(root)
    results: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in _cfg.ignore_dirs and not d.startswith(".")
        ]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if not _is_ignored(rel):
                results.append(rel.replace("\\", "/"))
    return sorted(results)


# ------------------------------------------------------------------
# Tool implementations (string output for the agent)
# ------------------------------------------------------------------
def list_directory(path: str) -> str:
    """List the immediate contents of a directory."""
    path = _norm(path)
    if not os.path.isdir(path):
        return f"Error: '{path}' is not a directory."
    entries = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        kind = "dir" if os.path.isdir(full) else "file"
        entries.append(f"{kind}\t{name}")
    if not entries:
        return f"'{path}' is empty."
    return "\n".join(entries)


def get_directory_tree(path: str, max_depth: int = 3) -> str:
    """Return an indented tree view of the project up to ``max_depth``.

    The output marks directories with a trailing ``/`` and shows file sizes for
    files, which helps the agent prioritise what to read.
    """
    path = _norm(path)
    if not os.path.isdir(path):
        return f"Error: '{path}' is not a directory."

    lines: List[str] = [f"DIRECTORY TREE (root={path})"]

    def _recurse(dir_path: str, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            names = sorted(os.listdir(dir_path))
        except PermissionError:
            lines.append(f"{prefix}<permission denied>")
            return
        # filter ignored and hidden
        names = [
            n for n in names
            if n not in _cfg.ignore_dirs and not n.startswith(".")
        ]
        for i, name in enumerate(names):
            full = os.path.join(dir_path, name)
            last = i == len(names) - 1
            branch = "└── " if last else "├── "
            if os.path.isdir(full):
                size = ""
                lines.append(f"{prefix}{branch}{name}/")
                _recurse(full, prefix + ("    " if last else "│   "), depth + 1)
            else:
                try:
                    size = f" ({os.path.getsize(full)} bytes)"
                except OSError:
                    size = ""
                lines.append(f"{prefix}{branch}{name}{size}")

    _recurse(path, "", 1)
    return "\n".join(lines)


def find_files(path: str, pattern: str = "*") -> str:
    """Find files whose name matches a glob ``pattern`` (e.g. ``*.py``)."""
    path = _norm(path)
    if not os.path.isdir(path):
        return f"Error: '{path}' is not a directory."
    matches = [f for f in _walk(path) if fnmatch.fnmatch(os.path.basename(f), pattern)]
    if not matches:
        return f"No files matching '{pattern}' found under '{path}'."
    return f"FOUND {len(matches)} FILE(S) MATCHING '{pattern}':\n" + "\n".join(matches)


def read_file(path: str, max_chars: int = None) -> str:
    """Read a file's text content, truncated to a safe size for the model."""
    path = _norm(path)
    if not os.path.isfile(path):
        return f"Error: '{path}' is not a file."
    limit = max_chars or _cfg.max_file_chars
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        return f"Error reading '{path}': {exc}"
    # prefix every line with its 1-based number for precise code linking
    numbered = "\n".join(
        f"{i + 1:4d} | {line}" for i, line in enumerate(content.splitlines())
    )
    if len(content) > limit:
        return f"FILE: {path} (truncated to {limit} chars of {len(content)})\n{numbered[:limit]}\n... [truncated]"
    return f"FILE: {path} ({len(content)} chars, {content.count(chr(10)) + 1} lines)\n{numbered}"


# ------------------------------------------------------------------
# Tool specs (advertised to the agent)
# ------------------------------------------------------------------
TOOL_SPECS = [
    {
        "name": "list_directory",
        "description": "List the immediate files and subdirectories of a directory.",
        "parameters": {"path": "string (directory path)"},
        "func": list_directory,
    },
    {
        "name": "get_directory_tree",
        "description": "Get an indented directory tree of a project up to max_depth. Best first step to understand layout.",
        "parameters": {"path": "string (root directory)", "max_depth": "int (optional, default 3)"},
        "func": get_directory_tree,
    },
    {
        "name": "find_files",
        "description": "Find files whose name matches a glob pattern (e.g. '*.py', '*.js').",
        "parameters": {"path": "string (search root)", "pattern": "string (glob, default '*')"},
        "func": find_files,
    },
    {
        "name": "read_file",
        "description": "Read a file's text content with line numbers. Truncated to a safe size.",
        "parameters": {"path": "string (file path)", "max_chars": "int (optional)"},
        "func": read_file,
    },
]
