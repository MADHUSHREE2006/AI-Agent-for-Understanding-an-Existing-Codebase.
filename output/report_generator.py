"""Report generator.

Turns an :class:`~agent.core.AgentResult` plus deterministic analysis of the
target project into a single Markdown report. Everything structural (tree,
parsed modules, dependency map, auto-detected rules) comes from real analysis
of the code, so the report is meaningful even when the agent ran in
simulation mode. The agent's natural-language final answer supplies the
narrative explanation of the business rules.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

from agent.core import AgentResult
from config import Config
from tools.code_parser import parse_file_structure, extract_business_rule_candidates
from tools.dependency_mapper import map_dependencies
from tools.file_explorer import get_directory_tree


def _link(file_ref: str, line: int = None, target: str = "") -> str:
    """Render a code reference as a relative path, optionally with :line."""
    ref = file_ref.replace("\\", "/")
    if ref.startswith(target.replace("\\", "/").rstrip("/") + "/"):
        ref = ref[len(target.replace("\\", "/").rstrip("/") + "/"):]
    if line is not None:
        return f"`{ref}:{line}`"
    return f"`{ref}`"


def generate_report(target: str, result: AgentResult, config: Config) -> str:
    """Build the full Markdown explanation report for ``target``."""
    target = os.path.normpath(target)
    name = os.path.basename(target.rstrip("/\\")) or target

    # ---- Deterministic structural analysis -------------------------------
    tree = get_directory_tree(target, max_depth=4)
    deps = map_dependencies(target)
    rule_candidates = extract_business_rule_candidates(target)

    # Parse every source file once, for the module breakdown.
    files_info = []
    for rel in deps.get("files", []):
        files_info.append((rel, parse_file_structure(os.path.join(target, rel))))

    sections: List[str] = []
    sections.append(f"# Codebase Understanding Report — {name}")
    sections.append("")
    sections.append(
        f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    sections.append(f"- **Target project:** `{target}`")
    sections.append(f"- **LLM backend:** {result.backend}")
    sections.append(f"- **Agentic iterations:** {result.iterations}")
    verified = sum(1 for c in result.citations if c.file_exists and c.line_valid)
    sections.append(
        f"- **Citations:** {verified}/{len(result.citations)} verified "
        f"against the real source"
    )
    if result.truncated:
        sections.append("- **Note:** the agent reached the iteration limit.")
    sections.append("")

    # ---- 1. Executive summary ------------------------------------------
    sections.append("## 1. Executive Summary")
    n_files = len(deps.get("files", []))
    n_classes = sum(len(f.get("classes", [])) for _, f in files_info)
    n_funcs = sum(len(f.get("functions", [])) for _, f in files_info)
    sections.append("")
    sections.append(
        f"This project contains **{n_files} Python file(s)** exposing "
        f"**{n_classes} class(es)** and **{n_funcs} top-level function(s)**, "
        f"with **{len(deps.get('edges', []))} internal dependency link(s)**. "
        f"The agent explored the codebase in {result.iterations} agentic "
        f"steps (see the trace in the appendix)."
    )
    sections.append("")

    # ---- 2. Project structure -------------------------------------------
    sections.append("## 2. Project Structure")
    sections.append("")
    sections.append("```")
    sections.append(tree)
    sections.append("```")
    sections.append("")

    # ---- 3. Module breakdown --------------------------------------------
    sections.append("## 3. Module Breakdown")
    sections.append("")
    if not files_info:
        sections.append("_No parseable source files found._")
    for rel, info in files_info:
        sections.append(f"### `{rel}`")
        if info.get("docstring") or info.get("error"):
            pass
        if "error" in info:
            sections.append(f"_Could not parse: {info['error']}_")
            sections.append("")
            continue
        if info.get("imports"):
            sections.append("**Imports:**")
            for imp in info["imports"]:
                dots = "." * imp.get("level", 0)
                names = f" -> {imp['names']}" if imp.get("names") else ""
                sections.append(
                    f"- {_link(rel, imp['line'], target)} "
                    f"`{imp['kind']} {dots}{imp['module']}{names}`"
                )
        if info["classes"]:
            sections.append("**Classes:**")
            for cls in info["classes"]:
                bases = f" extends {', '.join(cls['bases'])}" if cls["bases"] else ""
                doc = f" — {cls['docstring']}" if cls["docstring"] else ""
                sections.append(
                    f"- {_link(rel, cls['line'], target)} "
                    f"`{cls['name']}`{bases}{doc}"
                )
                for meth in cls["methods"]:
                    args = ", ".join(meth["args"])
                    mdoc = f" — {meth['docstring']}" if meth["docstring"] else ""
                    sections.append(
                        f"  - {_link(rel, meth['line'], target)} "
                        f"`{meth['name']}({args})`{mdoc}"
                    )
        if info["functions"]:
            sections.append("**Functions:**")
            for fn in info["functions"]:
                args = ", ".join(fn["args"])
                doc = f" — {fn['docstring']}" if fn["docstring"] else ""
                sections.append(
                    f"- {_link(rel, fn['line'], target)} "
                    f"`{fn['name']}({args})`{doc}"
                )
        if not info["classes"] and not info["functions"] and not info["imports"]:
            sections.append("_No classes, functions, or imports detected._")
        sections.append("")

    # ---- 4. Dependency map ----------------------------------------------
    sections.append("## 4. Dependencies")
    sections.append("")
    edges = deps.get("edges", [])
    if edges:
        sections.append("**Internal wiring (file → imports):**")
        for e in edges:
            sections.append(
                f"- {_link(e['from'], None, target)} → "
                f"{_link(e['to'], None, target)} "
                f"(`{e['module']}` @ line {e['line']})"
            )
        sections.append("")
    else:
        sections.append("_No internal (cross-file) imports detected — the modules are self-contained._")
        sections.append("")
    ext = deps.get("external_imports", [])
    if ext:
        sections.append("**External / third-party libraries:** " + ", ".join(f"`{x}`" for x in ext))
        sections.append("")

    # ---- 5. Business rules (agent narrative) ---------------------------
    sections.append("## 5. Business Rules — Agent Explanation")
    sections.append("")
    if result.final_answer.strip():
        sections.append(result.final_answer.strip())
    else:
        sections.append("_The agent did not produce a narrative answer._")
    sections.append("")

    # ---- 6. Business rules (auto-detected) -----------------------------
    sections.append("## 6. Business Rules — Auto-Detected by Heuristics")
    sections.append("")
    sections.append(
        "These candidates were flagged by static analysis (raises, "
        "comparisons, rule-like names). They give a checkable inventory of "
        "the rules independent of the LLM:"
    )
    sections.append("")
    if rule_candidates:
        sections.append("| File:Line | Function | Category | Evidence |")
        sections.append("|----------|----------|----------|----------|")
        for c in rule_candidates:
            ev = c["evidence"].replace("|", "\\|")
            sections.append(
                f"| {_link(c['file'], c['line'], target)} | "
                f"`{c['function']}` | {c['category']} | `{ev}` |"
            )
        sections.append("")
    else:
        sections.append("_No rule candidates detected._")
        sections.append("")

    # ---- 7. Citation verification --------------------------------------
    sections.append("## 7. Citation Verification (Result Checking)")
    sections.append("")
    if result.citations:
        sections.append("| Citation | File exists | Line valid |")
        sections.append("|----------|:-----------:|:----------:|")
        for c in result.citations:
            ok = "✅" if c.line_valid else "⚠️"
            fe = "✅" if c.file_exists else "❌"
            sections.append(f"| `{c.raw}` | {fe} | {ok} |")
        sections.append("")
        sections.append(
            "The agent's claims are checked against the real source. "
            f"{verified} of {len(result.citations)} referenced locations "
            "were confirmed to exist."
        )
    else:
        sections.append("_No file:line citations were found in the agent's answer._")
    sections.append("")

    # ---- Appendix: agentic trace ---------------------------------------
    sections.append("## Appendix — Agentic Trace")
    sections.append("")
    sections.append(
        "The full ReAct trace showing the agent's reasoning, tool choices, "
        "and observations at each step:"
    )
    sections.append("")
    sections.append("<details><summary>Expand trace</summary>")
    sections.append("")
    sections.append("```")
    sections.append(result.trace_text())
    sections.append("```")
    sections.append("")
    sections.append("</details>")
    sections.append("")

    return "\n".join(sections)


def save_report(report_text: str, target: str, config: Config) -> str:
    """Write the report to the output directory and return its path."""
    os.makedirs(config.output_dir, exist_ok=True)
    base = os.path.basename(os.path.normpath(target).rstrip("/\\")) or "project"
    filename = f"report_{base}.md"
    path = os.path.join(config.output_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    return path
