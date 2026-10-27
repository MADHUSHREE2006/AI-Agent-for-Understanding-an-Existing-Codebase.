"""Content search tool.

Lets the agent grep across a project for patterns such as function calls,
raised exceptions, or business-rule keywords, and see the matching lines with
file and line numbers so it can cite them in its explanation.
"""

from __future__ import annotations

import os
import re
from typing import List

from config import Config

_cfg = Config()


def _norm(p: str) -> str:
    return os.path.normpath(p)


def _is_ignored(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return any(part in _cfg.ignore_dirs for part in parts)


def search_content(path: str, pattern: str, max_results: int = 20) -> str:
    """Search file contents for a regex ``pattern`` across a project.

    Returns up to ``max_results`` matches, each shown as ``file:line: <line>``.
    Only text-like files under supported extensions are searched to keep the
    output focused on source code.
    """
    path = _norm(path)
    if not os.path.isdir(path):
        return f"Error: '{path}' is not a directory."
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"Error: invalid regex '{pattern}': {exc}"

    matches: List[str] = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [
            d for d in dirnames
            if d not in _cfg.ignore_dirs and not d.startswith(".")
        ]
        for fn in filenames:
            # Skip documentation files like README so the agent only cites code,
            # not documentation that restates the rules in prose.
            if fn.upper().startswith("README"):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext and ext not in _cfg.supported_extensions and ext not in (
                ".txt", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini",
            ):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, path).replace("\\", "/")
            if _is_ignored(rel):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            snippet = line.rstrip()
                            if len(snippet) > 200:
                                snippet = snippet[:200] + " …"
                            matches.append(f"{rel}:{lineno}: {snippet}")
                            if len(matches) >= max_results:
                                return (
                                    f"SEARCH RESULTS for /{pattern}/ "
                                    f"({len(matches)} shown, limit reached):\n"
                                    + "\n".join(matches)
                                )
            except OSError:
                continue
    if not matches:
        return f"No matches for /{pattern}/ under '{path}'."
    return f"SEARCH RESULTS for /{pattern}/ ({len(matches)} matches):\n" + "\n".join(matches)


TOOL_SPECS = [
    {
        "name": "search_content",
        "description": "Search file contents across a project for a regex pattern (e.g. 'raise |ValueError', 'def .*validate'). Returns file:line matches.",
        "parameters": {
            "path": "string (search root)",
            "pattern": "string (regex)",
            "max_results": "int (optional, default 20)",
        },
        "func": search_content,
    },
]
