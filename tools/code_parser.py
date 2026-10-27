"""Code structure parsing tool.

Extracts the structural skeleton of a source file: imports, classes (with
their methods and base classes), and top-level functions, each annotated with
its line number so explanations can link straight to the code.

Python files get full AST precision via the built-in :mod:`ast` module; other
languages fall back to carefully tuned regex heuristics that still capture the
same shape. The structured result is reused by the report generator.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List

from config import Config

_cfg = Config()


def _norm(p: str) -> str:
    return os.path.normpath(p)


def _doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node)
    if doc:
        first = doc.strip().splitlines()[0]
        return first[:160]
    return ""


def parse_file_structure(path: str) -> Dict[str, Any]:
    """Return a structured description of a source file.

    Keys: ``path``, ``language``, ``imports``, ``classes``, ``functions``.
    Each class/function entry carries ``line`` (start) and ``end`` (end) so
    the report generator can cite exact line ranges.
    """
    path = _norm(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        return _parse_python(path)
    return _parse_regex(path, ext)


def _parse_python(path: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": path, "language": "python",
        "imports": [], "classes": [], "functions": [],
    }
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        result["error"] = f"SyntaxError: {exc}"
        return result
    except OSError as exc:
        result["error"] = str(exc)
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(
                    {"module": alias.name, "line": node.lineno, "kind": "import"}
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = node.level or 0
            names = ", ".join(a.name for a in node.names)
            result["imports"].append(
                {
                    "module": mod,        # bare module name (no leading dots)
                    "level": level,       # number of leading dots for resolution
                    "names": names,
                    "line": node.lineno,
                    "kind": "from",
                }
            )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            result["functions"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end": getattr(node, "end_lineno", node.lineno),
                    "args": args,
                    "docstring": _doc(node),
                    "decorators": [d.__class__.__name__ for d in node.decorator_list],
                }
            )
        elif isinstance(node, ast.ClassDef):
            methods: List[Dict[str, Any]] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(
                        {
                            "name": item.name,
                            "line": item.lineno,
                            "end": getattr(item, "end_lineno", item.lineno),
                            "args": [a.arg for a in item.args.args],
                            "docstring": _doc(item),
                        }
                    )
            result["classes"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end": getattr(node, "end_lineno", node.lineno),
                    "bases": [b.id if isinstance(b, ast.Name) else ast.dump(b) for b in node.bases],
                    "methods": methods,
                    "docstring": _doc(node),
                }
            )
    return result


def _parse_regex(path: str, ext: str) -> Dict[str, Any]:
    """Best-effort structural extraction for non-Python languages."""
    lang_map = {
        ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".java": "java", ".cs": "csharp", ".go": "go",
        ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp", ".h": "c",
        ".hpp": "cpp",
    }
    result: Dict[str, Any] = {
        "path": path, "language": lang_map.get(ext, "unknown"),
        "imports": [], "classes": [], "functions": [],
    }
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        result["error"] = str(exc)
        return result

    class_re = re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)")
    func_re = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:function|func|def|sub)\s+(\w+)\s*\(([^)]*)\)"
    )
    method_re = re.compile(
        r"^\s*(?:public|private|protected|static|async|final|\s)*(\w+)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"
    )
    import_re = re.compile(
        r"^\s*(?:import\s+.*|from\s+[\w.]+\s+import\s+.*|require\(.+\)|#include\s+[<\"][^>\"]+[>\"])"
    )

    in_class = None
    for i, line in enumerate(lines, start=1):
        if import_re.match(line):
            result["imports"].append({"module": line.strip()[:120], "line": i, "kind": "import"})
        m = class_re.match(line)
        if m:
            in_class = m.group(1)
            result["classes"].append(
                {"name": in_class, "line": i, "end": i, "bases": [], "methods": [], "docstring": ""}
            )
            continue
        m = func_re.match(line)
        if m:
            result["functions"].append(
                {"name": m.group(1), "line": i, "end": i,
                 "args": [a.strip() for a in m.group(2).split(",") if a.strip()],
                 "docstring": "", "decorators": []}
            )
            continue
        if in_class:
            m = method_re.match(line)
            if m and m.group(2) not in ("if", "while", "for", "switch", "catch"):
                if result["classes"]:
                    result["classes"][-1]["methods"].append(
                        {"name": m.group(2), "line": i, "end": i, "args": [], "docstring": ""}
                    )
        if re.match(r"^\s*(?:class|func|function|def)\b", line) is None:
            in_class = None
    return result


def extract_business_rule_candidates(root: str) -> List[Dict[str, Any]]:
    """Heuristically flag code that likely encodes a business rule.

    Scans every Python file under ``root`` and returns candidates with the
    file, line, function name, a category, and an evidence snippet. This is
    deterministic analysis that works without an LLM, so the report generator
    can surface rules even in simulation mode.

    Categories:
    * ``validation`` - raises an exception or asserts a precondition.
    * ``condition``  - contains a comparison that gates behaviour.
    * ``computation``- named like a rule/calculation (validate, can_, is_...).
    """
    root = _norm(root)
    candidates: List[Dict[str, Any]] = []
    if not os.path.isdir(root):
        return candidates
    rule_name_re = re.compile(
        r"^(validate|check|is_|can_|has_|ensure|require|compute|calculate|apply|enforce)"
    )
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
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                tree = ast.parse(src, filename=full)
            except (SyntaxError, OSError):
                continue
            lines = src.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                category = None
                evidence = ""
                for child in ast.walk(node):
                    if isinstance(child, ast.Raise):
                        category = "validation"
                        if child.lineno and child.lineno - 1 < len(lines):
                            evidence = lines[child.lineno - 1].strip()
                        break
                    if isinstance(child, (ast.Compare,)) and isinstance(child.ops[0], (ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq)):
                        if category is None:
                            category = "condition"
                            if child.lineno and child.lineno - 1 < len(lines):
                                evidence = lines[child.lineno - 1].strip()
                if category is None and rule_name_re.match(node.name):
                    category = "computation"
                    if node.lineno and node.lineno - 1 < len(lines):
                        evidence = lines[node.lineno - 1].strip()
                if category:
                    candidates.append({
                        "file": rel, "line": node.lineno,
                        "function": node.name, "category": category,
                        "evidence": evidence[:140],
                    })
    candidates.sort(key=lambda c: (c["file"], c["line"]))
    return candidates


# ------------------------------------------------------------------
# Tool wrapper (string output for the agent)
# ------------------------------------------------------------------
def _tool(path: str) -> str:
    data = parse_file_structure(path)
    if "error" in data:
        return f"PARSE ERROR for '{path}': {data['error']}"
    lines = [f"PARSED STRUCTURE: {data['path']} ({data['language']})"]
    if data["imports"]:
        lines.append(f"  Imports ({len(data['imports'])}):")
        for imp in data["imports"]:
            names = f" -> {imp.get('names')}" if imp.get("names") else ""
            dots = "." * imp.get("level", 0)
            lines.append(f"    L{imp['line']}: {imp['kind']} {dots}{imp['module']}{names}")
    for cls in data["classes"]:
        bases = f"({', '.join(cls['bases'])})" if cls["bases"] else ""
        doc = f" — {cls['docstring']}" if cls["docstring"] else ""
        lines.append(f"  Class L{cls['line']}-{cls['end']}: {cls['name']}{bases}{doc}")
        for meth in cls["methods"]:
            args = ", ".join(meth["args"])
            mdoc = f" — {meth['docstring']}" if meth["docstring"] else ""
            lines.append(f"    Method L{meth['line']}-{meth['end']}: {meth['name']}({args}){mdoc}")
    if data["functions"]:
        lines.append(f"  Functions ({len(data['functions'])}):")
        for fn in data["functions"]:
            args = ", ".join(fn["args"])
            doc = f" — {fn['docstring']}" if fn["docstring"] else ""
            lines.append(f"    L{fn['line']}-{fn['end']}: {fn['name']}({args}){doc}")
    if not data["imports"] and not data["classes"] and not data["functions"]:
        lines.append("  (no classes, functions, or imports detected)")
    return "\n".join(lines)


TOOL_SPECS = [
    {
        "name": "parse_file_structure",
        "description": "Extract the structure of a source file: imports, classes with methods, and functions, each with line numbers. Works best on Python (full AST).",
        "parameters": {"path": "string (file path)"},
        "func": _tool,
    },
]
